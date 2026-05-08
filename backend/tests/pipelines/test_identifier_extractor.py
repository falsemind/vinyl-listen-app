from app.pipelines.identification import IdentifierExtractor, ImageVariant, OcrResult, OcrTextLine, PreparedImage
from app.pipelines.identification.identifier_parser import IdentifierParser
from app.pipelines.identification.ocr_backends import OcrBackendUnavailableError, OcrCascade


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


class FailingOcrBackend:
    def __init__(self) -> None:
        self.calls = 0

    def extract(self, _prepared_image: PreparedImage) -> OcrResult:
        self.calls += 1
        raise OcrBackendUnavailableError("primary unavailable")


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


def test_identifier_extractor_uses_primary_result_without_evidence_based_fallback() -> None:
    primary = StubOcrBackend(OcrResult(source="tesseract", raw_text="&", lines=(OcrTextLine("&", None, "tesseract"),)))
    fallback = StubOcrBackend(
        OcrResult(
            source="paddleocr_vl",
            raw_text="Cat No: TOVRI 001",
            lines=(OcrTextLine("Cat No: TOVRI 001", 0.91, "paddleocr_vl"),),
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


def test_identifier_extractor_runs_tesseract_fallback_when_primary_backend_fails() -> None:
    class EmptyBarcodeDetector:
        def detect(self, _prepared_image: PreparedImage) -> tuple[str, ...]:
            return ()

    primary = FailingOcrBackend()
    fallback = StubOcrBackend(
        OcrResult(
            source="tesseract",
            raw_text="Cat No: TOVRI 001",
            lines=(OcrTextLine("Cat No: TOVRI 001", None, "tesseract"),),
        )
    )
    extractor = IdentifierExtractor(
        barcode_detector=EmptyBarcodeDetector(),
        ocr_backend=OcrCascade(primary_backend=primary, fallback_backend=fallback),
        identifier_parser=IdentifierParser(),
    )

    identifiers = extractor.extract(_build_prepared_image())

    assert identifiers.catalog_numbers == ("TOVRI 001",)
    assert [line.source for line in identifiers.ocr_evidence] == ["tesseract"]
    assert identifiers.identifier_evidence[0].value == "TOVRI 001"
    assert identifiers.identifier_evidence[0].source == "tesseract"
    assert identifiers.identifier_evidence[0].confidence is None
    assert primary.calls == 1
    assert fallback.calls == 1


def test_identifier_parser_does_not_use_side_headings_as_identity() -> None:
    identifiers = IdentifierParser().parse(
        "\n".join(
            [
                "HARMONY & KID LIB",
                "33 RPM",
                "THIS SIDE",
                "Future",
                "OTHER SIDE",
                "Fire Feeler · Dressback",
                "Fire Feeler written & produced by Kid Lib",
                "Dressback written & produced by",
                "Future written & produced by",
            ]
        )
    )

    assert identifiers.artist == "HARMONY & KID LIB"
    assert identifiers.title == "Future"
    assert "THIS SIDE" not in identifiers.text_fragments
    assert "OTHER SIDE" not in identifiers.text_fragments


def test_identifier_parser_rejects_edition_and_production_year_noise() -> None:
    identifiers = IdentifierParser().parse(
        "\n".join(
            [
                "Limited Edition",
                "BAILEY",
                "A Shaka",
                "(Nebula Remix)",
                "B1 Shaka",
                "(Double O Remix)",
                "B2 Shaka",
                "(Original Mix)",
                "Written & produced by M. Bailey",
                "for SU Productions 2025",
            ]
        )
    )

    assert identifiers.catalog_numbers == ()
    assert identifiers.artist == "BAILEY"
    assert identifiers.title == "Shaka"
    assert "for SU Productions" not in identifiers.text_fragments


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
