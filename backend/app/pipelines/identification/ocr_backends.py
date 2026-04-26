from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from io import BytesIO
from typing import Any, Protocol

from PIL import Image

from app.core.config import settings
from app.pipelines.identification.models import ImageVariant, OcrResult, OcrTextLine, PreparedImage
from app.pipelines.identification.ocr_extractor import OcrExtractor

logger = logging.getLogger(__name__)

DEFAULT_EASYOCR_MAX_IMAGE_DIMENSION = 800
DEFAULT_EASYOCR_VARIANT_NAMES = ("grayscale", "threshold", "threshold_low", "sharpened")
NOISY_TESSERACT_LINE_LIMIT = 40


class OcrBackend(Protocol):
    def extract(self, prepared_image: PreparedImage) -> OcrResult:
        """Extract OCR text from prepared image variants."""


class TesseractOcrBackend:
    def __init__(self, extractor: OcrExtractor | None = None) -> None:
        self._extractor = extractor or OcrExtractor()

    def extract(self, prepared_image: PreparedImage) -> OcrResult:
        raw_text = self._extractor.extract(prepared_image)
        return OcrResult(
            source="tesseract",
            raw_text=raw_text,
            lines=tuple(OcrTextLine(text=line, confidence=None, source="tesseract") for line in _clean_lines(raw_text)),
        )


class EasyOcrBackend:
    def __init__(
        self,
        *,
        languages: tuple[str, ...] = ("en",),
        gpu: bool = False,
        min_confidence: float = 0.35,
        max_image_dimension: int = DEFAULT_EASYOCR_MAX_IMAGE_DIMENSION,
        variant_names: tuple[str, ...] = DEFAULT_EASYOCR_VARIANT_NAMES,
        reader_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._languages = languages
        self._gpu = gpu
        self._min_confidence = min_confidence
        self._max_image_dimension = max_image_dimension
        self._variant_names = variant_names
        self._reader_factory = reader_factory
        self._reader: Any | None = None

    def extract(self, prepared_image: PreparedImage) -> OcrResult:
        reader = self._load_reader()
        if reader is None:
            return OcrResult(source="easyocr", raw_text="")

        lines: list[OcrTextLine] = []
        seen: set[str] = set()
        variants_by_name = {variant.name: variant for variant in prepared_image.ocr_variants()}

        for variant_name in self._variant_names:
            variant = variants_by_name.get(variant_name)
            if variant is None:
                continue
            lines.extend(self._extract_variant_lines(reader, variant, seen=seen))

        return OcrResult(
            source="easyocr",
            raw_text="\n".join(line.text for line in lines),
            lines=tuple(lines),
        )

    def _load_reader(self) -> Any | None:
        if self._reader is not None:
            return self._reader

        if self._reader_factory is not None:
            self._reader = self._reader_factory()
            return self._reader

        try:
            import easyocr
        except ImportError:
            logger.info("EasyOCR fallback requested but easyocr is not installed.")
            return None

        logger.info("Loading EasyOCR reader languages=%s gpu=%s", self._languages, self._gpu)
        self._reader = easyocr.Reader(list(self._languages), gpu=self._gpu)
        return self._reader

    def _extract_variant_lines(self, reader: Any, variant: ImageVariant, *, seen: set[str]) -> tuple[OcrTextLine, ...]:
        image_array = _variant_to_easyocr_input(variant, max_image_dimension=self._max_image_dimension)
        if image_array is None:
            return ()

        try:
            detections = reader.readtext(image_array, detail=1, paragraph=False)
        except RuntimeError as error:
            logger.info("EasyOCR extraction failed variant=%s: %s", variant.name, error)
            return ()

        lines: list[OcrTextLine] = []
        for detection in detections:
            line = _normalize_easyocr_detection(detection)
            if line is None or line.confidence is None or line.confidence < self._min_confidence:
                continue

            key = _normalize_text_key(line.text)
            if not key or key in seen:
                continue

            seen.add(key)
            lines.append(line)

        return tuple(lines)


class OcrCascade:
    def __init__(
        self,
        *,
        primary_backend: OcrBackend,
        fallback_backend: OcrBackend | None = None,
    ) -> None:
        self._primary_backend = primary_backend
        self._fallback_backend = fallback_backend

    def extract(self, prepared_image: PreparedImage, *, detected_barcodes: Iterable[str] = ()) -> OcrResult:
        primary_result = self._primary_backend.extract(prepared_image)
        if self._fallback_backend is None or not _should_run_fallback(primary_result, detected_barcodes):
            return primary_result

        logger.info("Running EasyOCR fallback because Tesseract evidence was weak.")
        fallback_result = self._fallback_backend.extract(prepared_image)
        return merge_ocr_results(primary_result, fallback_result)


def build_default_ocr_cascade(ocr_extractor: OcrExtractor | None = None) -> OcrCascade:
    fallback_backend: OcrBackend | None = None
    if settings.identify_easyocr_enabled:
        fallback_backend = EasyOcrBackend(
            gpu=settings.identify_easyocr_gpu,
            min_confidence=settings.identify_easyocr_min_confidence,
            max_image_dimension=settings.identify_easyocr_max_image_dimension,
        )

    return OcrCascade(
        primary_backend=TesseractOcrBackend(ocr_extractor),
        fallback_backend=fallback_backend,
    )


def merge_ocr_results(*results: OcrResult) -> OcrResult:
    merged_lines: list[OcrTextLine] = []
    seen: set[str] = set()

    for result in results:
        fallback_lines = tuple(
            OcrTextLine(text=line, confidence=None, source=result.source) for line in _clean_lines(result.raw_text)
        )
        for line in result.lines or fallback_lines:
            key = _normalize_text_key(line.text)
            if not key or key in seen:
                continue
            seen.add(key)
            merged_lines.append(line)

    return OcrResult(
        source="+".join(result.source for result in results if result.has_text()) or "none",
        raw_text="\n".join(line.text for line in merged_lines),
        lines=tuple(merged_lines),
    )


def _should_run_fallback(primary_result: OcrResult, detected_barcodes: Iterable[str]) -> bool:
    if tuple(detected_barcodes):
        return False
    if not primary_result.has_text():
        return True

    lines = _clean_lines(primary_result.raw_text)
    if _is_weak_ocr_text(lines):
        return True
    if _is_noisy_tesseract_text(lines):
        return True

    return not any(_looks_like_catalog_evidence(line) for line in lines)


def _is_weak_ocr_text(lines: tuple[str, ...]) -> bool:
    if len(lines) < 2:
        return True
    alphanumeric_count = sum(character.isalnum() for line in lines for character in line)
    return alphanumeric_count < 24


def _is_noisy_tesseract_text(lines: tuple[str, ...]) -> bool:
    return len(lines) > NOISY_TESSERACT_LINE_LIMIT


def _looks_like_catalog_evidence(line: str) -> bool:
    return (
        any(character.isalpha() for character in line)
        and any(character.isdigit() for character in line)
        and sum(character.isalnum() for character in line) >= 4
    )


def _variant_to_easyocr_input(variant: ImageVariant, *, max_image_dimension: int) -> Any | None:
    try:
        import numpy as np
    except ImportError:
        logger.info("EasyOCR fallback requested but numpy is not installed.")
        return None

    with Image.open(BytesIO(variant.data)) as image:
        resized_image = _resize_for_easyocr(image.convert("RGB"), max_image_dimension=max_image_dimension)
        return np.array(resized_image)


def _resize_for_easyocr(image: Image.Image, *, max_image_dimension: int) -> Image.Image:
    if max_image_dimension <= 0:
        return image.copy()

    longest_edge = max(image.width, image.height)
    if longest_edge <= max_image_dimension:
        return image.copy()

    scale = max_image_dimension / float(longest_edge)
    resized_dimensions = (
        max(1, int(image.width * scale)),
        max(1, int(image.height * scale)),
    )
    return image.resize(resized_dimensions, Image.Resampling.LANCZOS)


def _normalize_easyocr_detection(detection: Any) -> OcrTextLine | None:
    try:
        box, text, confidence = detection
    except (TypeError, ValueError):
        return None

    normalized_text = " ".join(str(text).strip().split())
    if not normalized_text:
        return None

    return OcrTextLine(
        text=normalized_text,
        confidence=_coerce_confidence(confidence),
        source="easyocr",
        box=_coerce_box(box),
    )


def _coerce_confidence(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_box(value: Any) -> tuple[tuple[float, float], ...] | None:
    try:
        return tuple((float(point[0]), float(point[1])) for point in value)
    except (TypeError, ValueError, IndexError):
        return None


def _clean_lines(raw_text: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in raw_text.splitlines() if line.strip())


def _normalize_text_key(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())
