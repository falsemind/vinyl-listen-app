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
    assert identifiers.year is None
    assert identifiers.label is None
    assert identifiers.text_fragments == ("Source / Virgin",)


def test_identifier_parser_can_split_artist_and_title_from_single_line() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse("Boards of Canada - Music Has The Right To Children")

    assert identifiers.artist == "Boards of Canada"
    assert identifiers.title == "Music Has The Right To Children"


def test_identifier_parser_adds_corrected_catalog_variant_for_common_ocr_confusion() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse("Cat No: SCRUBO19")

    assert identifiers.catalog_numbers == ("SCRUBO19", "SCRUB019")


def test_identifier_parser_extracts_year_and_combined_label_from_screenshot_style_ocr() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "SCRUBO19",
                "B© 2019*",
                "SCOTCH BONNET",
                "RECORDS",
            ]
        )
    )

    assert identifiers.catalog_numbers == ("SCRUBO19", "SCRUB019")
    assert identifiers.artist is None
    assert identifiers.title is None
    assert identifiers.year == 2019
    assert identifiers.label == "SCOTCH BONNET RECORDS"
    assert identifiers.text_fragments == ("SCOTCH BONNET RECORDS",)


def test_identifier_parser_discards_trailing_catalog_junk_and_ocr_garbage_metadata() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "SCRUBO19 8",
                "ee 2 i a Re ? ee",
                "MASTERED BYBEAU Ss. °°",
                "SCOTCH BONNET",
                "RECORDS",
            ]
        )
    )

    assert identifiers.catalog_numbers == ("SCRUBO19", "SCRUB019", "SCRUBO19 8", "SCRUB019 8")
    assert identifiers.artist is None
    assert identifiers.title is None
    assert identifiers.label == "SCOTCH BONNET RECORDS"
    assert identifiers.text_fragments == ("SCOTCH BONNET RECORDS",)


def test_identifier_parser_rejects_symbol_led_short_metadata_noise() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "Scrupeig- = so f* See",
                "— amo",
                "SCOTCH BONNET",
                "RECORDS",
            ]
        )
    )

    assert identifiers.artist is None
    assert identifiers.title is None
    assert identifiers.label == "SCOTCH BONNET RECORDS"
