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


DEFAULT_OCR_CONFIGS = ("--psm 6", "--psm 11")


class OcrExtractor:
    def __init__(self, *, configs: tuple[str, ...] = DEFAULT_OCR_CONFIGS) -> None:
        self._configs = configs

    def extract(self, prepared_image: PreparedImage) -> str:
        if pytesseract is None:
            logger.debug("OCR extraction unavailable because pytesseract is not installed.")
            return ""

        extracted_chunks: list[str] = []
        seen: set[str] = set()

        for variant in prepared_image.ocr_variants():
            with Image.open(BytesIO(variant.data)) as image:
                for config in self._configs:
                    try:
                        raw_text = pytesseract.image_to_string(image.copy(), config=config)
                    except TesseractNotFoundError:
                        logger.info("OCR extraction unavailable because the tesseract binary is not installed.")
                        return ""
                    except RuntimeError as error:
                        logger.info("OCR extraction failed: %s", error)
                        return ""

                    cleaned_text = _clean_ocr_text(raw_text)
                    if not cleaned_text or cleaned_text in seen:
                        continue

                    seen.add(cleaned_text)
                    extracted_chunks.append(cleaned_text)

        return "\n".join(extracted_chunks)


def _clean_ocr_text(value: str) -> str:
    lines = [line.strip() for line in value.splitlines()]
    non_empty_lines = [line for line in lines if line]
    return "\n".join(non_empty_lines)
