from app.pipelines.identification.identifier_parser import IdentifierParser


def test_identifier_parser_extracts_catalog_artist_title_and_text_fragments() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "Artist: Air",
                "Title: Moon Safari",
                "Cat No: 7243 8 44978 1 8",
                "Barcode: 4006381333931",
                "Source / Virgin",
            ]
        )
    )

    assert identifiers.barcodes == ("4006381333931",)
    assert identifiers.catalog_numbers == ("7243 8 44978 1 8",)
    assert identifiers.artist == "Air"
    assert identifiers.title == "Moon Safari"
    assert identifiers.year is None
    assert identifiers.label is None
    assert identifiers.text_fragments == ("Source / Virgin",)


def test_identifier_parser_rejects_contact_numbers_as_ocr_barcodes() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "TEL: 020 1234 5678",
                "FAX: 020 8765 4321",
                "INFO: 724384497818",
            ]
        )
    )

    assert identifiers.barcodes == ()


def test_identifier_parser_keeps_detector_barcodes_without_contact_context_filtering() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse("TEL: 020 1234 5678", barcodes=("724384497818",))

    assert identifiers.barcodes == ("724384497818",)


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


def test_identifier_parser_prioritizes_repeated_catalog_reading_over_noisy_variants() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "'- LIONCHGX008",
                "'- LIONCHEX005",
                "a - LIONCHGX003 -",
                '"-LIONCHGX003',
                "A. WALK & SKANK",
                "B. FORWARD",
            ]
        )
    )

    assert identifiers.catalog_numbers[:3] == ("LIONCHGX003", "LIONCHGX008", "LIONCHEX005")


def test_identifier_parser_prefers_full_catalog_over_prefix_dropped_suffix() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "CHEX003",
                "CHGX003",
                "a - LIONCHGX003 -",
                '"- LIONCHGX003',
            ]
        )
    )

    assert identifiers.catalog_numbers[0] == "LIONCHGX003"


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


def test_identifier_parser_recovers_dj_artist_title_from_noisy_label_ocr() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "__DJCRISPS '",
                "LUMINAR |",
                "YOU GET DOWN",
                "PUT ME DOWN",
                "DJ CRIS",
                "JUST FINE",
            ]
        )
    )

    assert identifiers.artist == "DJ CRISPS"
    assert identifiers.title == "LUMINAR"


def test_identifier_parser_rejects_copyright_year_range_as_catalog() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "JUST JUNGLE",
                "TOVRI 001",
                "(c) 1995/1956",
            ]
        )
    )

    assert identifiers.catalog_numbers == ("TOVRI 001",)
    assert identifiers.year == 1995


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


def test_identifier_parser_corrects_confused_catalog_suffixes() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "RUPLDN OO2LP",
                "#TOSOO7",
                "GTOSOO7S",
                "7EVEN06",
            ]
        )
    )

    assert "RUPLDN 002LP" in identifiers.catalog_numbers
    assert "OO2LP" not in identifiers.catalog_numbers
    assert "TOS007" in identifiers.catalog_numbers
    assert "7EVEN06" in identifiers.catalog_numbers


def test_identifier_parser_repairs_edge_confused_catalog_token() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse("A Side y TEVENOG")

    assert identifiers.catalog_numbers == ("7EVEN06",)


def test_identifier_parser_does_not_treat_label_url_text_as_catalog() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "7EVEN RECORDINGS",
                "7even.recordings@gmail.com",
                "www.myspace.com/7evenrecordings",
            ]
        )
    )

    assert identifiers.catalog_numbers == ()


def test_identifier_parser_treats_side_markers_as_track_titles_not_catalogs() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "ROOMS IN",
                "TIME-SPACE",
                "Al. OBSERVATORY",
                "A2.JUNCTION",
                "B1. BUNKER",
                "B2. QUANTUM ZONE",
                "#TOSOO7",
                "SUB BASICS",
            ]
        )
    )

    assert identifiers.catalog_numbers == ("TOSOO7", "TOS007")
    assert "JUNCTION" not in identifiers.catalog_numbers
    assert "A2.JUNCTION" not in identifiers.catalog_numbers
    assert {"OBSERVATORY", "JUNCTION", "BUNKER", "QUANTUM ZONE"}.issubset(identifiers.text_fragments)


def test_identifier_parser_filters_credit_lines_before_artist_title_selection() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "JEEP HEA",
                'A (There) "Jungle Breeze"',
                'B (Here) "Close Encounters"',
                "Written, mixed & produced by Jeep Head",
                "& The Dogs of Core.",
                "Additional production by Roger Johnson.",
            ]
        )
    )

    assert identifiers.artist != "Additional production by Roger Johnson"
    assert identifiers.artist != "M & The Dogs of Core"
    assert "Jungle Breeze" in identifiers.text_fragments or identifiers.title == "Jungle Breeze"


def test_identifier_parser_filters_leading_by_credit_fragments() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "Fire Feeler + Dressback",
                "by Kid Lib",
                "DAT 095",
            ]
        )
    )

    assert "by Kid Lib" not in identifiers.text_fragments


def test_identifier_parser_recovers_terminal_question_mark_catalog_number() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "THE",
                "ESSENTIALS EP",
                "FMROO?",
                "DEE CYPHER memories",
            ]
        )
    )

    assert identifiers.catalog_numbers == ("FMROO?", "FMR007")


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


def test_identifier_parser_validates_and_repairs_ocr_barcode_checksums() -> None:
    parser = IdentifierParser()

    valid_identifiers = parser.parse("4006381333931")
    invalid_identifiers = parser.parse("4006381333932")
    invalid_labeled_identifiers = parser.parse("Barcode: 4006381333932")
    repaired_identifiers = parser.parse("4OO6381333931")
    repaired_with_separator_identifiers = parser.parse("400-638133393S")
    false_positive_identifiers = parser.parse("BOSSBOSS")

    assert valid_identifiers.barcodes == ("4006381333931",)
    assert invalid_identifiers.barcodes == ()
    assert invalid_labeled_identifiers.barcodes == ()
    assert repaired_identifiers.barcodes == ("4006381333931",)
    assert repaired_with_separator_identifiers.barcodes == ("4006381333931",)
    assert false_positive_identifiers.barcodes == ()
