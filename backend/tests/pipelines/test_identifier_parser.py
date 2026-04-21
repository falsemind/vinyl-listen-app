from app.pipelines.identification.identifier_parser import IdentifierParser


def test_identifier_parser_extracts_catalog_artist_title_and_text_fragments() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "Artist: Air",
                "Title: Moon Safari",
                "Cat No: 7243 8 44978 1 8",
                "Barcode: 724384497818",
                "Source / Virgin",
            ]
        )
    )

    assert identifiers.barcodes == ("724384497818",)
    assert identifiers.catalog_numbers == ("7243 8 44978 1 8",)
    assert identifiers.artist == "Air"
    assert identifiers.title == "Moon Safari"
    assert identifiers.text_fragments == ("Source / Virgin",)


def test_identifier_parser_can_split_artist_and_title_from_single_line() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse("Boards of Canada - Music Has The Right To Children")

    assert identifiers.artist == "Boards of Canada"
    assert identifiers.title == "Music Has The Right To Children"
