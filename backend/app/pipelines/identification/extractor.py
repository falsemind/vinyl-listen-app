from __future__ import annotations

from dataclasses import replace

from app.pipelines.identification.barcode_detector import BarcodeDetector
from app.pipelines.identification.identifier_parser import IdentifierParser
from app.pipelines.identification.models import ExtractedIdentifiers, PreparedImage
from app.pipelines.identification.ocr_backends import OcrCascade, build_default_ocr_cascade
from app.pipelines.identification.ocr_extractor import OcrExtractor
from app.pipelines.identification.ocr_layout_analyzer import analyze_ocr_layout


class IdentifierExtractor:
    def __init__(
        self,
        *,
        barcode_detector: BarcodeDetector | None = None,
        ocr_extractor: OcrExtractor | None = None,
        ocr_backend: OcrCascade | None = None,
        identifier_parser: IdentifierParser | None = None,
    ) -> None:
        self._barcode_detector = barcode_detector or BarcodeDetector()
        self._ocr_backend = ocr_backend or build_default_ocr_cascade(ocr_extractor)
        self._identifier_parser = identifier_parser or IdentifierParser()

    def extract(self, prepared_image: PreparedImage) -> ExtractedIdentifiers:
        detected_barcodes = self._barcode_detector.detect(prepared_image)
        ocr_result = self._ocr_backend.extract(prepared_image, detected_barcodes=detected_barcodes)
        identifiers = self._identifier_parser.parse(ocr_result.raw_text, barcodes=detected_barcodes)
        return replace(
            identifiers,
            ocr_evidence=ocr_result.lines,
            ocr_roles=analyze_ocr_layout(ocr_result.lines),
        )
