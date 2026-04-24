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


def test_identifier_parser_extracts_embedded_catalog_tokens_from_noisy_label_ocr() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "a - LIONCHGX003 -",
                "'- LIONCHGX008",
                "\" '- LIONCHGX003",
                "SUB BASICS 7",
                "A. WALK & SKANK",
                "B. FORWARD",
            ]
        )
    )

    assert identifiers.catalog_numbers == ("LIONCHGX003", "LIONCHGX008")
    assert "SUB BASICS 7" not in identifiers.catalog_numbers
    assert identifiers.artist == "SUB BASICS"
    assert identifiers.title == "WALK & SKANK"
    assert identifiers.text_fragments == ("FORWARD",)


def test_identifier_parser_does_not_promote_track_lines_with_stray_digits_to_catalogs() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "DJ CRISPS",
                "LUMINARY EP",
                "7 PASS IT",
                "JUST FINE",
                "PUT ME DOWN",
            ]
        )
    )

    assert identifiers.catalog_numbers == ()
    assert identifiers.artist == "DJ CRISPS"
    assert identifiers.title == "LUMINARY EP"


def test_identifier_parser_extracts_hash_separated_catalog_number() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "RUFFCUT#2 ©",
                "@",
                "RUFFCUT#2",
                "e",
            ]
        )
    )

    assert identifiers.catalog_numbers == ("RUFFCUT#2",)
    assert identifiers.artist is None
    assert identifiers.title is None


def test_identifier_parser_corrects_catalog_letter_o_before_digits() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse("SYSTMO22")

    assert identifiers.catalog_numbers == ("SYSTMO22", "SYSTM022")
    assert identifiers.artist is None
    assert identifiers.title is None


def test_identifier_parser_strips_lowercase_ocr_prefix_before_catalog_token() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse("sSYSTMO22")

    assert identifiers.catalog_numbers == ("SYSTMO22", "SYSTM022")


def test_identifier_parser_prioritizes_clean_catalog_suffix_over_noisy_prefix() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "GESCSYSTMO22",
                "SYSTMO22",
            ]
        )
    )

    assert identifiers.catalog_numbers[:2] == ("SYSTMO22", "SYSTM022")


def test_identifier_parser_extracts_spaced_label_code_catalog_number() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "JUST JUNGLE",
                "TOVRI 001",
                "45 rpm",
                "A. SKY",
            ]
        )
    )

    assert identifiers.catalog_numbers == ("TOVRI 001",)
