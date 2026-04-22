from app.pipelines.identification import IdentifierExtractor, ImageVariant, PreparedImage
from app.pipelines.identification.identifier_parser import IdentifierParser


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
