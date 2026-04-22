from __future__ import annotations

from app.pipelines.identification.barcode_detector import BarcodeDetector
from app.pipelines.identification.identifier_parser import IdentifierParser
from app.pipelines.identification.models import ExtractedIdentifiers, PreparedImage
from app.pipelines.identification.ocr_extractor import OcrExtractor


class IdentifierExtractor:
    def __init__(
        self,
        *,
        barcode_detector: BarcodeDetector | None = None,
        ocr_extractor: OcrExtractor | None = None,
        identifier_parser: IdentifierParser | None = None,
    ) -> None:
        self._barcode_detector = barcode_detector or BarcodeDetector()
        self._ocr_extractor = ocr_extractor or OcrExtractor()
        self._identifier_parser = identifier_parser or IdentifierParser()

    def extract(self, prepared_image: PreparedImage) -> ExtractedIdentifiers:
        detected_barcodes = self._barcode_detector.detect(prepared_image)
        raw_text = self._ocr_extractor.extract(prepared_image)
        return self._identifier_parser.parse(raw_text, barcodes=detected_barcodes)
