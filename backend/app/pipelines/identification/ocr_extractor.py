from __future__ import annotations

import logging
from io import BytesIO

from PIL import Image

from app.pipelines.identification.models import PreparedImage

logger = logging.getLogger(__name__)

try:
    import pytesseract
    from pytesseract import TesseractNotFoundError
except ImportError:
    pytesseract = None

    class TesseractNotFoundError(RuntimeError):
        """Fallback exception used when pytesseract is unavailable."""


DEFAULT_FAST_CONFIGS = ("--psm 6", "--psm 11")
CATALOG_OCR_WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-./ "
DEFAULT_ESCALATION_CONFIGS = {
    "threshold_low": ("--psm 6", "--psm 11"),
    "sharpened": ("--psm 7", "--psm 13"),
    "inverted_threshold": ("--psm 7", "--psm 13"),
    "upscaled_grayscale": ("--psm 7", "--psm 8", "--psm 13"),
    "upscaled_threshold": (
        "--psm 7",
        "--psm 8",
        "--psm 13",
        f"--psm 7 -c tessedit_char_whitelist={CATALOG_OCR_WHITELIST}",
        f"--psm 8 -c tessedit_char_whitelist={CATALOG_OCR_WHITELIST}",
    ),
}
FAST_VARIANT_NAMES = ("grayscale", "threshold")


class OcrExtractor:
    def __init__(
        self,
        *,
        fast_configs: tuple[str, ...] = DEFAULT_FAST_CONFIGS,
        escalation_configs: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        self._fast_configs = fast_configs
        self._escalation_configs = escalation_configs or DEFAULT_ESCALATION_CONFIGS

    def extract(self, prepared_image: PreparedImage) -> str:
        if pytesseract is None:
            logger.debug("OCR extraction unavailable because pytesseract is not installed.")
            return ""

        extracted_chunks: list[str] = []
        seen: set[str] = set()
        variants_by_name = {variant.name: variant for variant in prepared_image.ocr_variants()}

        for variant_name in FAST_VARIANT_NAMES:
            variant = variants_by_name.get(variant_name)
            if variant is None:
                continue
            if not self._run_variant_passes(
                variant_name=variant.name,
                image_bytes=variant.data,
                configs=self._fast_configs,
                extracted_chunks=extracted_chunks,
                seen=seen,
            ):
                return ""

        if _should_escalate_ocr(extracted_chunks):
            logger.debug("OCR fast path was weak; running escalation passes.")
            for variant_name, configs in self._escalation_configs.items():
                variant = variants_by_name.get(variant_name)
                if variant is None:
                    continue
                if not self._run_variant_passes(
                    variant_name=variant.name,
                    image_bytes=variant.data,
                    configs=configs,
                    extracted_chunks=extracted_chunks,
                    seen=seen,
                ):
                    return ""

        return "\n".join(extracted_chunks)

    def _run_variant_passes(
        self,
        *,
        variant_name: str,
        image_bytes: bytes,
        configs: tuple[str, ...],
        extracted_chunks: list[str],
        seen: set[str],
    ) -> bool:
        with Image.open(BytesIO(image_bytes)) as image:
            for config in configs:
                try:
                    raw_text = self._read_text(image, variant_name=variant_name, config=config)
                except TesseractNotFoundError:
                    logger.info("OCR extraction unavailable because the tesseract binary is not installed.")
                    return False
                except RuntimeError as error:
                    logger.info("OCR extraction failed: %s", error)
                    return False

                cleaned_text = _clean_ocr_text(raw_text)
                if not cleaned_text or cleaned_text in seen:
                    continue

                seen.add(cleaned_text)
                extracted_chunks.append(cleaned_text)

        return True

    def _read_text(self, image: Image.Image, *, variant_name: str, config: str) -> str:
        logger.debug("Running OCR variant=%s config=%s", variant_name, config)
        return pytesseract.image_to_string(image.copy(), config=config)


def _clean_ocr_text(value: str) -> str:
    lines = [line.strip() for line in value.splitlines()]
    non_empty_lines = [line for line in lines if line]
    return "\n".join(non_empty_lines)


def _should_escalate_ocr(extracted_chunks: list[str]) -> bool:
    if not extracted_chunks:
        return True

    extracted_lines = [line for chunk in extracted_chunks for line in chunk.splitlines() if line]
    if len(extracted_lines) >= 3 and any(len(line) >= 10 for line in extracted_lines):
        return False

    combined_text = " ".join(extracted_lines)
    alphanumeric_count = sum(character.isalnum() for character in combined_text)
    return len(extracted_lines) < 2 or alphanumeric_count < 24
