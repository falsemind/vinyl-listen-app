from app.pipelines.identification import IdentifierExtractor, ImageVariant, OcrResult, OcrTextLine, PreparedImage
from app.pipelines.identification.identifier_parser import IdentifierParser
from app.pipelines.identification.ocr_backends import OcrCascade


class StubBarcodeDetector:
    def detect(self, _prepared_image: PreparedImage) -> tuple[str, ...]:
        return ("5021603065515",)


class StubOcrExtractor:
    def extract(self, _prepared_image: PreparedImage) -> str:
        return "\n".join(
            [
                "Artist: Boards of Canada",
                "Title: Music Has The Right To Children",
                "Cat No: WARPLP55",
            ]
        )


class StubOcrBackend:
    def __init__(self, result: OcrResult) -> None:
        self.result = result
        self.calls = 0

    def extract(self, _prepared_image: PreparedImage) -> OcrResult:
        self.calls += 1
        return self.result


def test_identifier_extractor_combines_barcode_ocr_and_parser_signals() -> None:
    extractor = IdentifierExtractor(
        barcode_detector=StubBarcodeDetector(),
        ocr_extractor=StubOcrExtractor(),
        identifier_parser=IdentifierParser(),
    )

    identifiers = extractor.extract(_build_prepared_image())

    assert identifiers.barcodes == ("5021603065515",)
    assert identifiers.catalog_numbers == ("WARPLP55",)
    assert identifiers.artist == "Boards of Canada"
    assert identifiers.title == "Music Has The Right To Children"


def test_identifier_extractor_skips_easyocr_fallback_when_barcode_is_available() -> None:
    primary = StubOcrBackend(OcrResult(source="tesseract", raw_text="&", lines=(OcrTextLine("&", None, "tesseract"),)))
    fallback = StubOcrBackend(
        OcrResult(
            source="easyocr",
            raw_text="Cat No: TOVRI 001",
            lines=(OcrTextLine("Cat No: TOVRI 001", 0.91, "easyocr"),),
        )
    )
    extractor = IdentifierExtractor(
        barcode_detector=StubBarcodeDetector(),
        ocr_backend=OcrCascade(primary_backend=primary, fallback_backend=fallback),
        identifier_parser=IdentifierParser(),
    )

    identifiers = extractor.extract(_build_prepared_image())

    assert identifiers.catalog_numbers == ()
    assert [line.source for line in identifiers.ocr_evidence] == ["tesseract"]
    assert primary.calls == 1
    assert fallback.calls == 0


def test_identifier_extractor_runs_easyocr_fallback_without_barcode() -> None:
    class EmptyBarcodeDetector:
        def detect(self, _prepared_image: PreparedImage) -> tuple[str, ...]:
            return ()

    primary = StubOcrBackend(OcrResult(source="tesseract", raw_text="&", lines=(OcrTextLine("&", None, "tesseract"),)))
    fallback = StubOcrBackend(
        OcrResult(
            source="easyocr",
            raw_text="Cat No: TOVRI 001",
            lines=(OcrTextLine("Cat No: TOVRI 001", 0.91, "easyocr"),),
        )
    )
    extractor = IdentifierExtractor(
        barcode_detector=EmptyBarcodeDetector(),
        ocr_backend=OcrCascade(primary_backend=primary, fallback_backend=fallback),
        identifier_parser=IdentifierParser(),
    )

    identifiers = extractor.extract(_build_prepared_image())

    assert identifiers.catalog_numbers == ("TOVRI 001",)
    assert [line.source for line in identifiers.ocr_evidence] == ["easyocr"]
    assert primary.calls == 1
    assert fallback.calls == 1


def _build_prepared_image() -> PreparedImage:
    return PreparedImage(
        filename="cover.jpg",
        content_type="image/jpeg",
        data=b"image-data",
        size_bytes=10,
        digest="digest",
        width=1200,
        height=1200,
        variants=(ImageVariant(name="normalized", data=b"normalized-image"),),
    )
