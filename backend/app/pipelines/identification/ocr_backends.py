import logging
from collections.abc import Iterable
from typing import Protocol

from app.pipelines.identification.models import OcrResult, OcrTextLine, PreparedImage
from app.pipelines.identification.ocr_extractor import OcrExtractor

logger = logging.getLogger(__name__)

DEFAULT_PADDLEOCR_MODEL_NAME = "PaddlePaddle/PaddleOCR-VL-1.5"
DEFAULT_PADDLEOCR_TIMEOUT_SECONDS = 30.0
DEFAULT_PADDLEOCR_MAX_IMAGE_DIMENSION = 1280


class OcrBackendError(RuntimeError):
    """Base exception for OCR backend failures that may use fallback routing."""


class OcrBackendUnavailableError(OcrBackendError):
    """Raised when a configured OCR backend cannot run in the current environment."""


class OcrBackendTimeoutError(OcrBackendError):
    """Raised when an OCR backend exceeds its configured time budget."""


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


class PaddleOcrVlBackend:
    def __init__(
        self,
        *,
        device: str = "cpu",
        vl_rec_backend: str | None = None,
        vl_rec_server_url: str | None = None,
        vl_rec_api_model_name: str = DEFAULT_PADDLEOCR_MODEL_NAME,
        timeout_seconds: float = DEFAULT_PADDLEOCR_TIMEOUT_SECONDS,
        max_image_dimension: int = DEFAULT_PADDLEOCR_MAX_IMAGE_DIMENSION,
    ) -> None:
        self._device = device
        self._vl_rec_backend = vl_rec_backend
        self._vl_rec_server_url = vl_rec_server_url
        self._vl_rec_api_model_name = vl_rec_api_model_name
        self._timeout_seconds = timeout_seconds
        self._max_image_dimension = max_image_dimension

    def extract(self, _prepared_image: PreparedImage) -> OcrResult:
        raise OcrBackendUnavailableError("PaddleOCR-VL backend is configured but Phase 2 inference is not implemented.")


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
        del detected_barcodes
        try:
            return self._primary_backend.extract(prepared_image)
        except (OcrBackendError, TimeoutError) as error:
            if self._fallback_backend is None:
                raise

            logger.info("Running OCR fallback because primary backend failed: %s", error)
            return self._fallback_backend.extract(prepared_image)


def build_default_ocr_cascade(ocr_extractor: OcrExtractor | None = None) -> OcrCascade:
    from app.core.config import settings

    backend_name = settings.identify_ocr_backend.strip().lower()
    tesseract_backend = TesseractOcrBackend(ocr_extractor)

    if backend_name == "tesseract":
        return OcrCascade(primary_backend=tesseract_backend)

    if backend_name in {"auto", "paddleocr_vl"}:
        fallback_backend: OcrBackend | None = None
        if settings.identify_ocr_tesseract_fallback_enabled:
            fallback_backend = tesseract_backend

        return OcrCascade(
            primary_backend=PaddleOcrVlBackend(
                device=settings.identify_paddleocr_device,
                vl_rec_backend=settings.identify_paddleocr_vl_rec_backend,
                vl_rec_server_url=settings.identify_paddleocr_vl_rec_server_url,
                vl_rec_api_model_name=settings.identify_paddleocr_vl_rec_api_model_name,
                timeout_seconds=settings.identify_paddleocr_timeout_seconds,
                max_image_dimension=settings.identify_paddleocr_max_image_dimension,
            ),
            fallback_backend=fallback_backend,
        )

    raise ValueError(f"Unsupported OCR backend: {settings.identify_ocr_backend}")


def _clean_lines(raw_text: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in raw_text.splitlines() if line.strip())
