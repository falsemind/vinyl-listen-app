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


def test_identifier_parser_adds_known_label_catalog_prefix_variant() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "SYSTEM",
                "MUSIC",
                "SYSTEM022",
                "SLEEPER",
                "A. ORAM MODE",
                "B. LEVEL UP",
                "Written & produced by A. Fox",
                "Mastered by Beau Thomas at Ten Eight Seven Mastering © System Music 2016",
                "Mastered by Beau Thomas at Ten Eight Seven Mastering © System Music 2018",
            ]
        )
    )

    assert identifiers.catalog_numbers == ("SYSTEM022", "SYSTM022")
    assert identifiers.artist == "SLEEPER"
    assert identifiers.title == "ORAM MODE"
    assert "LEVEL UP" in identifiers.text_fragments


def test_identifier_parser_combines_known_prefix_and_suffix_catalog_repairs() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse("SYSTEMO22")

    assert identifiers.catalog_numbers == ("SYSTEMO22", "SYSTEM022", "SYSTM022")


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


def test_identifier_parser_does_not_promote_numbered_track_suffix_to_catalog() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "ThieveryCorporation",
                "Treasures from the Temple",
                "A",
                "an San Rock 01",
                "History 02",
                "Music to Make You Stagger 03",
            ]
        )
    )

    assert identifiers.catalog_numbers == ()
    assert identifiers.artist == "ThieveryCorporation"
    assert identifiers.title == "Treasures from the Temple"
    assert identifiers.text_fragments == ("San Rock", "History", "Music to Make You Stagger")


def test_identifier_parser_does_not_promote_track_duration_to_catalog_number() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "A.SIDE TOOLATE 06:38",
                "[DEEP VOCAL MIX]",
                "Written by Carroll Thompson",
                "Produced by Daryl B & Matt Coleman",
                "Licenced courtesy of Daryl B & Pointblank Records",
                "B.SIDE TOOLATE 06:56",
                "[UNDERGROUND DUB]",
                "©2023 South Street",
                "tree",
            ]
        )
    )

    assert identifiers.catalog_numbers == ()
    assert identifiers.artist is None
    assert identifiers.title == "TOOLATE"
    assert identifiers.label is None
    assert identifiers.text_fragments == ()


def test_identifier_parser_uses_repeated_side_title_over_credit_and_band_noise() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "A.SIDE TOOLATE 06:38",
                "(DEEP VOCAL MIX)",
                "Written by Carroll Thompson",
                "Produced by Daryl B & Matt Coleman",
                "Licensed courtesy of Daryl B & Matt Coleman",
                "B.SIDE TOOLATE 06:56",
                "(UNDERGROUND DUB)",
                "Licensed courtesy of Daryl B & Pointblank Records",
                "©2023 South Street",
                "Youth Street",
                "B.SIDE",
                "TOOLATE",
                "06:56",
                "CLINICGROUNDLING",
            ]
        )
    )

    assert identifiers.catalog_numbers == ()
    assert identifiers.artist is None
    assert identifiers.title == "TOOLATE"
    assert identifiers.label is None
    assert "B.SIDE" not in identifiers.text_fragments
    assert all(not value.startswith("Licensed courtesy") for value in identifiers.text_fragments)


def test_identifier_parser_does_not_promote_fragmented_band_ocr_to_identity() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "A.SIDE TOOL LATE 06:38",
                "[DEEP VOCAL MIX]",
                "Written by Carroll Thompson",
                "Produced by Daryl B & Matt Coleman",
                "[UNDERGROUND DUB]",
                "Licensed courtesy of Daryl B & Pointblank Records",
                "©2023 South Street",
                "B",
                "45",
                "so",
                "SIDE",
                "TOOLATE",
                "06:56",
                "NDERGROUND DUB]",
            ]
        )
    )

    assert identifiers.artist is None
    assert identifiers.title == "TOOL LATE"
    assert identifiers.label is None
    assert "SIDE" not in identifiers.text_fragments
    assert "NDERGROUND DUB]" not in identifiers.text_fragments


def test_identifier_parser_reads_top_stacked_artist_title_before_side_tracks() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "WARLOK",
                "DARKSIDE SWING",
                "EP",
                "THIS SIDE",
                "FEELINGS",
                "IN LOVE WITH THE RHYTHM",
                "THAT SIDE",
                "READY FOR YOUR LOVE",
                "BANSHEE",
                "N LOVE WITH THE RHYTHM",
            ]
        )
    )

    assert identifiers.artist == "WARLOK"
    assert identifiers.title == "DARKSIDE SWING EP"
    assert "THAT SIDE" not in identifiers.text_fragments


def test_identifier_parser_keeps_catalog_number_near_side_marker() -> None:
    parser = IdentifierParser()

    compact_identifiers = parser.parse("B 45RPM SOUTH011")
    spaced_identifiers = parser.parse("B 45RPM SOUTH 011")

    assert compact_identifiers.catalog_numbers == ("SOUTH011",)
    assert spaced_identifiers.catalog_numbers == ("SOUTH 011",)


def test_identifier_parser_splits_stamped_catalog_artist_title_line() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "RHYTHM NVIBE",
                "RNVO3/DJ Perception/Phenomenal EP",
                "Written & produced by Cameron Phillips.",
                "Manufactured in the UK, Distributed by Juno.",
                "A&R Marc Cotterell // Plastik People Recordings 2019.",
            ]
        )
    )

    assert identifiers.catalog_numbers == ("RNVO3", "RNV03")
    assert identifiers.artist == "DJ Perception"
    assert identifiers.title == "Phenomenal EP"
    assert identifiers.label is None
    assert "Manufactured in the UK, Distributed by Juno" not in identifiers.text_fragments


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


def test_identifier_parser_rejects_copyright_imprint_year_as_catalog() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "Dwarde",
                "A. Piper [5:29]",
                "B. Piper (DJ Chromz Remix) [5:46]",
                "All tracks written & produced by D. Warde",
                "Additional remix production by M. Woldag",
                "© Future Retro London 2023",
            ]
        )
    )

    assert identifiers.catalog_numbers == ()
    assert identifiers.year == 2023
    assert identifiers.text_fragments == (
        "Piper [5:29]",
        "Piper (DJ Chromz Remix) [5:46]",
        "Dwarde",
    )


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


def test_identifier_parser_extracts_spaced_catalog_suffix_without_track_identity() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "A1. FIRM MEDITATION",
                "A2. REPATRIATION FT THEORY",
                "B1. STRETCHY BIZZ",
                "B2. CORSICA GROOVE",
                "RUPLDN 002LP",
                "A1. FIRM MEDITATION REPATRIATION FT THEOF",
            ]
        )
    )

    assert identifiers.catalog_numbers == ("RUPLDN 002LP",)
    assert identifiers.artist is None
    assert identifiers.title is None
    assert "CORSICA GROOVE" in identifiers.text_fragments


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


def test_identifier_parser_rejects_contact_lines_as_title_candidates() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "STORMING DUB",
                "RECORDS",
                "SIDE A",
                "45 rpm",
                "P© 2022",
                "PRODUCED BY",
                "KING ALPHA",
                "FOR STORMING DUB",
                "SDR75",
                "HORNS OF JERICHO",
                "stormingdub@gmail.com",
                "www.stormingdub.com",
                "info@onandler.com",
            ]
        )
    )

    assert identifiers.catalog_numbers == ("SDR75",)
    assert identifiers.artist == "KING ALPHA"
    assert identifiers.title == "HORNS OF JERICHO"
    assert "stormingdub@gmail.com" not in identifiers.text_fragments
    assert "info@onandler.com" not in identifiers.text_fragments


def test_identifier_parser_filters_credit_tail_from_title_first_label_layout() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "Yi Mds Gdn",
                "Records",
                "We Are The Generation",
                "Daba Makourejah",
                "Compose & Mix",
                "by Rootical 45",
                "EXECUTIVE PRODUCER YANNICK DAVENEL",
            ]
        )
    )

    assert identifiers.catalog_numbers == ()
    assert identifiers.artist == "Daba Makourejah"
    assert identifiers.title == "We Are The Generation"
    assert identifiers.label == "Yi Mds Gdn Records"
    assert "Rootical 45" not in identifiers.text_fragments
    assert "EXECUTIVE PRODUCER YANNICK DAVENEL" not in identifiers.text_fragments


def test_identifier_parser_suppresses_catalogs_from_noisy_tesseract_fallback_text() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "a = C23,",
                "wD a",
                "a as Mas G dQ AX a",
                "epee",
                "HDA RSS ESS",
                "Y > > Daba Makourejah kK",
                "Ne Compose & Mix <éS",
                "by Rootical 45 My yw",
                "YANNICK DAVENEL",
                "C2",
                "A",
                "We Are The Generation",
                "Daba Makourejah",
                "Compose & Mix",
                "by Rootical 45",
                "YANNICK DAVENEL",
                "JB as Records nkX a",
                "WOE 46 WAY",
                "oN We Are The Generation 437% mS",
                "Daba Makourejah q",
                "Compose & Mix SS",
                "by Rootical 45 no) Y",
                "Yg O40 5",
                "Records “2K",
                "We Are The Generation",
                "se & Mix",
                "Rootical 45",
                "YANNICK DAVENEL",
            ]
        )
    )

    assert identifiers.catalog_numbers == ()
    assert identifiers.artist == "Daba Makourejah"
    assert identifiers.title == "We Are The Generation"


def test_identifier_parser_does_not_promote_track_title_year_suffix_to_catalog() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "RUFF GUIDANCE",
                "RECORDS RECORDS",
                "REMASTERED",
                "BAY B KANE",
                "The Rise Of The Phoenix EP",
                "A1. Jungle Warriors 95",
                "A2. Seconds & Hours",
                "B1. The Breeze",
                "B2. If You Believe 95",
                "All Tracks Written & Produced By Bay B Kane",
                "Licensed With Thanks By Kniteforce Records",
                "www.kniteforcerevolution.com",
                "www.kniteforce-radio.com",
                "33RPM",
                "KRG01",
                "UNAUTHORIZED PUBLIC PERFORMANCE, BROADCASTING, COPYING AND RENTAL OF THIS RECORD PROHIBITED.",
            ]
        )
    )

    assert identifiers.catalog_numbers == ("KRG01",)
    assert identifiers.artist == "BAY B KANE"
    assert identifiers.title == "The Rise Of The Phoenix EP"
    assert "Warriors 95" not in identifiers.catalog_numbers
    assert "Believe 95" not in identifiers.catalog_numbers


def test_identifier_parser_strips_colon_side_markers_and_reads_catalog_before_credit() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "Infra Ltd 026 / Written and Produced by D.Hook P + C Infrared Records 2023",
                "A: Empires Of The Future",
                "AA: Above and Beyond / Immortal",
            ]
        )
    )

    assert identifiers.catalog_numbers == ("Infra Ltd 026",)
    assert identifiers.artist is None
    assert identifiers.title is None
    assert {"Empires Of The Future", "Above and Beyond / Immortal"}.issubset(identifiers.text_fragments)


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


def test_identifier_parser_merges_adjacent_label_code_and_number_catalog() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "PLANTPOWER",
                "012",
                "FOAMPLATE",
                "THIS SIDE",
                "SUBNORMAL PLATEAU",
                "ROTOSCOPE QUAVE STEPPA",
                "RESTORE",
            ]
        )
    )

    assert identifiers.catalog_numbers[:2] == ("PLANTPOWER012", "PLANTPOWER 012")
    assert identifiers.artist == "FOAMPLATE"
    assert identifiers.title == "SUBNORMAL PLATEAU"
    assert "ROTOSCOPE QUAVE STEPPA" in identifiers.text_fragments


def test_identifier_parser_ignores_legal_rim_text_when_selecting_identity() -> None:
    parser = IdentifierParser()

    identifiers = parser.parse(
        "\n".join(
            [
                "ALL RIGHTS RESERVED. UNAUTHORISED.",
                "DEEP ORMANCE & BROADCASTING OF THE",
                "JUNGLE",
                "HARMONY",
                "& KID LIB",
                "33 RPM",
                "THIS SIDE",
                "Future",
                "OTHER SIDE",
                "Fire Feeler · Dressback",
                "Fire Feeler written & produced by Kid Lib",
                "Dressback written & produced by",
                "Harmony & Kid Lib",
                "Future written & produced by",
                "DURING ALL RIGHTS RESERVED. UNAUTHORISED.",
                "DURING ALL RIGHTS RESERVED. UNA",
            ]
        )
    )

    assert identifiers.artist == "Harmony & Kid Lib"
    assert identifiers.title == "Future"
    assert "DURING ALL RIGHTS RESERVED. UNAUTHORISED" not in identifiers.text_fragments


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
