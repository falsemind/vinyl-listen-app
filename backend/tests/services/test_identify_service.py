from app.pipelines.identification import ExtractedIdentifiers, OcrRoleEvidence
from app.services.identify_service import IdentifyValidationError


def test_identify_service_returns_local_match_before_discogs_lookup(
    releases_repository_factory,
    build_release_stub,
    discogs_service_factory,
    build_identify_service,
) -> None:
    repository = releases_repository_factory(barcode_matches=[build_release_stub()])
    discogs_service = discogs_service_factory(
        payload={"results": [{"id": 999, "title": "Should Not - Be Called", "year": 2000}]}
    )
    service = build_identify_service(
        repository=repository,
        discogs_service=discogs_service,
        identifiers=ExtractedIdentifiers(barcodes=("724384497818",), catalog_numbers=(), artist=None, title=None),
    )

    result = service.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="cover.jpg",
        content_type="image/jpeg",
    )

    assert [candidate.discogs_release_id for candidate in result.candidates] == [123]
    assert result.candidates[0].match_source == "local"
    assert "barcode" in result.candidates[0].matched_on
    assert discogs_service.search_by_barcode_calls == []
    assert discogs_service.search_release_calls == []


def test_identify_service_falls_back_to_discogs_search_in_priority_order(
    releases_repository_factory,
    discogs_service_factory,
    build_identify_service,
) -> None:
    repository = releases_repository_factory()
    discogs_service = discogs_service_factory(
        payload={
            "results": [
                {
                    "id": 456,
                    "title": "Air - Moon Safari",
                    "year": "1998",
                    "label": ["Source"],
                    "catno": "7243 8 44978 1 8",
                    "cover_image": "https://img.discogs.com/external.jpg",
                }
            ]
        }
    )
    service = build_identify_service(
        repository=repository,
        discogs_service=discogs_service,
        identifiers=ExtractedIdentifiers(
            barcodes=("724384497818",),
            catalog_numbers=("7243 8 44978 1 8",),
            artist="Air",
            title="Moon Safari",
        ),
    )

    result = service.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="cover.jpg",
        content_type="image/jpeg",
    )

    assert [candidate.discogs_release_id for candidate in result.candidates] == [456]
    assert result.candidates[0].match_source == "discogs"
    assert result.candidates[0].matched_on == ("catalog_number", "artist", "title")
    assert discogs_service.search_by_barcode_calls == [("724384497818", 5)]
    assert discogs_service.search_release_calls == []


def test_identify_service_rejects_unsupported_image_type(build_identify_service) -> None:
    service = build_identify_service()

    try:
        service.identify(
            db=object(),
            image_bytes=b"fake-image",
            filename="cover.gif",
            content_type="image/gif",
        )
    except IdentifyValidationError as error:
        assert error.status_code == 415
        assert error.code == "unsupported_image_type"
        assert error.message == "Unsupported image type. Supported types: image/jpeg, image/png, image/webp."
    else:
        raise AssertionError("Expected IdentifyValidationError for unsupported media type")


def test_identify_service_returns_empty_candidates_when_no_signals_are_available(
    releases_repository_factory,
    discogs_service_factory,
    build_identify_service,
) -> None:
    repository = releases_repository_factory()
    discogs_service = discogs_service_factory()
    service = build_identify_service(
        repository=repository,
        discogs_service=discogs_service,
        identifiers=ExtractedIdentifiers(),
    )

    result = service.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="cover.png",
        content_type="image/png",
    )

    assert result.candidates == ()
    assert discogs_service.search_by_barcode_calls == []
    assert discogs_service.search_release_calls == []


def test_identify_service_uses_label_fragment_for_free_text_search(
    releases_repository_factory,
    discogs_service_factory,
    build_identify_service,
) -> None:
    repository = releases_repository_factory()
    discogs_service = discogs_service_factory(
        payload={
            "results": [
                {
                    "id": 456,
                    "title": "Artist - Title",
                    "year": "2019",
                    "label": ["Scotch Bonnet Records"],
                    "catno": "SCRUB019",
                }
            ]
        }
    )
    service = build_identify_service(
        repository=repository,
        discogs_service=discogs_service,
        identifiers=ExtractedIdentifiers(
            year=2019,
            label="Scotch Bonnet Records",
            text_fragments=("Scotch Bonnet Records",),
        ),
    )

    result = service.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="label.png",
        content_type="image/png",
    )

    assert [candidate.discogs_release_id for candidate in result.candidates] == [456]
    assert discogs_service.search_by_barcode_calls == []
    assert discogs_service.search_release_calls == [{"limit": 5, "query": "Scotch Bonnet Records"}]


def test_identify_service_tries_trimmed_catalog_variant_after_noisy_catalog_query(
    releases_repository_factory,
    discogs_service_factory,
    build_identify_service,
) -> None:
    repository = releases_repository_factory()
    discogs_service = discogs_service_factory(
        payloads=[
            {"results": []},
            {
                "results": [
                    {
                        "id": 456,
                        "title": "Artist - Title",
                        "year": "2019",
                        "label": ["Scotch Bonnet Records"],
                        "catno": "SCRUB019",
                    }
                ]
            },
        ]
    )
    service = build_identify_service(
        repository=repository,
        discogs_service=discogs_service,
        identifiers=ExtractedIdentifiers(catalog_numbers=("SCRUBO19", "SCRUB019", "SCRUBO19 8")),
    )

    result = service.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="label-crop.png",
        content_type="image/png",
    )

    assert [candidate.discogs_release_id for candidate in result.candidates] == [456]
    assert discogs_service.search_release_calls == [
        {"limit": 5, "catalog_number": "SCRUBO19"},
        {"limit": 5, "catalog_number": "SCRUB019"},
        {"limit": 5, "catalog_number": "SCRUBO19 8"},
    ]


def test_identify_service_ranks_aggregated_non_barcode_discogs_results(
    releases_repository_factory,
    discogs_service_factory,
    build_identify_service,
) -> None:
    repository = releases_repository_factory()
    discogs_service = discogs_service_factory(
        payloads=[
            {
                "results": [
                    {
                        "id": 111,
                        "title": "Wrong Artist - Wrong Title",
                        "catno": "WRONG001",
                    }
                ]
            },
            {
                "results": [
                    {
                        "id": 456,
                        "title": "Sub Basics - Walk & Skank",
                        "label": ["Lion Charge Records"],
                        "catno": "LIONCHGX003",
                    }
                ]
            },
        ]
    )
    service = build_identify_service(
        repository=repository,
        discogs_service=discogs_service,
        identifiers=ExtractedIdentifiers(catalog_numbers=("BAD001", "LIONCHGX003")),
    )

    result = service.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="label-crop.png",
        content_type="image/png",
    )

    assert [candidate.discogs_release_id for candidate in result.candidates] == [456, 111]
    assert discogs_service.search_release_calls == [
        {"limit": 5, "catalog_number": "BAD001"},
        {"limit": 5, "catalog_number": "LIONCHGX003"},
    ]


def test_identify_service_skips_loose_searches_after_catalog_candidates(
    releases_repository_factory,
    discogs_service_factory,
    build_identify_service,
) -> None:
    repository = releases_repository_factory()
    discogs_service = discogs_service_factory(
        payloads=[
            {
                "results": [
                    {
                        "id": 456,
                        "title": "Fire Feeler + Dressback - Harmony & Kid Lib",
                        "catno": "DAT 095",
                    }
                ]
            },
            {"results": []},
        ]
    )
    service = build_identify_service(
        repository=repository,
        discogs_service=discogs_service,
        identifiers=ExtractedIdentifiers(
            catalog_numbers=("DAT 095", "DAT O95"),
            artist="Fire Feeler",
            title="Dressback",
            raw_text="Fire Feeler + Dressback\nFire Feeler written produc Kid Lib",
        ),
    )

    result = service.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="label-crop.png",
        content_type="image/png",
    )

    assert [candidate.discogs_release_id for candidate in result.candidates] == [456]
    assert discogs_service.search_release_calls == [
        {"limit": 5, "catalog_number": "DAT 095"},
        {"limit": 5, "catalog_number": "DAT O95"},
    ]


def test_identify_service_uses_artist_title_when_catalog_candidates_do_not_match_identity(
    releases_repository_factory,
    discogs_service_factory,
    build_identify_service,
) -> None:
    repository = releases_repository_factory()
    discogs_service = discogs_service_factory(
        payloads=[
            {
                "results": [
                    {
                        "id": 111,
                        "title": "Wrong Artist - Wrong Title",
                        "catno": "LIONCHGX008",
                    }
                ]
            },
            {
                "results": [
                    {
                        "id": 456,
                        "title": "Sub Basics - Walk & Skank",
                        "catno": "LIONCHGX003",
                    }
                ]
            },
        ]
    )
    service = build_identify_service(
        repository=repository,
        discogs_service=discogs_service,
        identifiers=ExtractedIdentifiers(
            catalog_numbers=("LIONCHGX008",),
            artist="SUB BASICS",
            title="WALK & SKANK",
        ),
    )

    result = service.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="label-crop.png",
        content_type="image/png",
    )

    assert [candidate.discogs_release_id for candidate in result.candidates] == [456, 111]
    assert discogs_service.search_release_calls == [
        {"limit": 5, "catalog_number": "LIONCHGX008"},
        {"limit": 5, "artist": "SUB BASICS", "title": "WALK & SKANK"},
    ]


def test_identify_service_combines_identity_with_supporting_track_fragment(
    releases_repository_factory,
    discogs_service_factory,
    build_identify_service,
) -> None:
    repository = releases_repository_factory()
    discogs_service = discogs_service_factory(
        payloads=[
            {"results": []},
            {"results": []},
            {"results": []},
            {"results": []},
            {"results": []},
            {
                "results": [
                    {
                        "id": 456,
                        "title": "Sub Basics - Walk & Skank / Forward",
                        "catno": "LIONCHGX003",
                    }
                ]
            },
        ]
    )
    service = build_identify_service(
        repository=repository,
        discogs_service=discogs_service,
        identifiers=ExtractedIdentifiers(
            catalog_numbers=("LIONCHGX008", "LIONCHGX005", "LIONCHEX008"),
            artist="SUB BASICS",
            title="WALK & SKANK",
            text_fragments=("FORWARD", "SN SUB Basics", "CHy", "SIND", "CORDA", "SHS"),
        ),
    )

    result = service.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="label-crop.png",
        content_type="image/png",
    )

    assert [candidate.discogs_release_id for candidate in result.candidates] == [456]
    assert {"limit": 5, "query": "SUB BASICS WALK SKANK FORWARD"} in discogs_service.search_release_calls


def test_identify_service_searches_raw_ocr_context_when_structured_fields_are_wrong(
    releases_repository_factory,
    discogs_service_factory,
    build_identify_service,
) -> None:
    repository = releases_repository_factory()
    discogs_service = discogs_service_factory(
        payloads=[
            {"results": []},
            {
                "results": [
                    {
                        "id": 456,
                        "title": "DJ Kane - Just Jungle",
                        "label": ["Trouble On Vinyl"],
                        "catno": "TOVRI 001",
                    }
                ]
            },
        ]
    )
    service = build_identify_service(
        repository=repository,
        discogs_service=discogs_service,
        identifiers=ExtractedIdentifiers(
            artist="All tracks mixed and produced by",
            title="Justin Richardson at Mixing Lab Studio",
            raw_text="\n".join(
                [
                    "DJ KANE PRESENTS",
                    "JUST JUNGLE",
                    "TOVRI 001",
                    "This Side",
                    "A. SKY",
                    "Other Side",
                    "AA. NEXT SOUND",
                ]
            ),
        ),
    )

    result = service.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="label-crop.png",
        content_type="image/png",
    )

    assert [candidate.discogs_release_id for candidate in result.candidates] == [456]
    assert {
        "limit": 5,
        "artist": "All tracks mixed and produced by",
        "title": "Justin Richardson at Mixing Lab Studio",
    } not in discogs_service.search_release_calls
    assert {"limit": 5, "query": "TOVRI 001 DJ KANE PRESENTS"} in discogs_service.search_release_calls
    assert {"limit": 5, "query": "TOVRI 001 JUST JUNGLE"} in discogs_service.search_release_calls
    assert {
        "limit": 5,
        "query": "DJ KANE PRESENTS All tracks mixed and produced by",
    } not in discogs_service.search_release_calls


def test_identify_service_searches_combined_identity_context_for_noisy_artist_title(
    releases_repository_factory,
    discogs_service_factory,
    build_identify_service,
) -> None:
    repository = releases_repository_factory()
    discogs_service = discogs_service_factory()
    service = build_identify_service(
        repository=repository,
        discogs_service=discogs_service,
        identifiers=ExtractedIdentifiers(
            artist="DJ CRISPS",
            title="LUM NARY FE",
            text_fragments=("DJCRISPS", "LUM NARY", "PASS IT"),
            raw_text="\n".join(["__DJCRISPS", "LUMINAR", "LUM NARY FE", "PASS IT"]),
        ),
    )

    result = service.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="label-crop.png",
        content_type="image/png",
    )

    assert result.candidates == ()
    assert {"limit": 5, "query": "DJ CRISPS LUMINARY EP"} in discogs_service.search_release_calls
    assert {"limit": 5, "query": "PASS IT"} not in discogs_service.search_release_calls


def test_identify_service_filters_credit_lines_from_raw_context_queries(
    releases_repository_factory,
    discogs_service_factory,
    build_identify_service,
) -> None:
    repository = releases_repository_factory()
    discogs_service = discogs_service_factory()
    service = build_identify_service(
        repository=repository,
        discogs_service=discogs_service,
        identifiers=ExtractedIdentifiers(
            artist="Fire Feeler",
            title="Dressback",
            raw_text="\n".join(
                [
                    "Fire Feeler + Dressback",
                    "Fire Feeler written produc Kid Lib",
                    "Dressback written pro",
                ]
            ),
        ),
    )

    result = service.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="label-crop.png",
        content_type="image/png",
    )

    assert result.candidates == ()
    searched_queries = {call["query"].lower() for call in discogs_service.search_release_calls if "query" in call}
    assert all("written" not in query and "produc" not in query for query in searched_queries)
    assert {"limit": 5, "query": "Fire Feeler Dressback"} in discogs_service.search_release_calls


def test_identify_service_searches_catalog_number_with_ocr_role_context(
    releases_repository_factory,
    discogs_service_factory,
    build_identify_service,
) -> None:
    repository = releases_repository_factory()
    discogs_service = discogs_service_factory(
        payloads=[
            {"results": []},
            {"results": []},
            {"results": []},
            {
                "results": [
                    {
                        "id": 456,
                        "title": "Various - Essentials EP",
                        "label": ["Fresh Milk Records"],
                        "catno": "FMR007",
                    }
                ]
            },
        ]
    )
    service = build_identify_service(
        repository=repository,
        discogs_service=discogs_service,
        identifiers=ExtractedIdentifiers(
            catalog_numbers=("FMROO?", "FMR007"),
            ocr_roles=(
                OcrRoleEvidence(role="release_title", text="ESSENTIALS EP", confidence=None, source="tesseract"),
                OcrRoleEvidence(role="label", text="Fresh Milk Records", confidence=None, source="tesseract"),
            ),
        ),
    )

    result = service.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="label-crop.png",
        content_type="image/png",
    )

    assert [candidate.discogs_release_id for candidate in result.candidates] == [456]
    assert {"limit": 5, "query": "FMR007 ESSENTIALS EP"} in discogs_service.search_release_calls
    assert {"limit": 5, "query": "FMR007 Fresh Milk Records"} in discogs_service.search_release_calls
    assert {"limit": 5, "query": "FMROO? ESSENTIALS EP"} not in discogs_service.search_release_calls
    assert {"limit": 5, "query": "A RECORDS"} not in discogs_service.search_release_calls


def test_identify_service_filters_low_quality_text_fragments_before_free_text_search(
    releases_repository_factory,
    discogs_service_factory,
    build_identify_service,
) -> None:
    repository = releases_repository_factory()
    discogs_service = discogs_service_factory()
    service = build_identify_service(
        repository=repository,
        discogs_service=discogs_service,
        identifiers=ExtractedIdentifiers(
            text_fragments=(
                "eat CJ bin",
                "RRM nor govz",
                "Fresh Milk Records",
                "ESSENTIALS EP",
            ),
        ),
    )

    result = service.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="label-crop.png",
        content_type="image/png",
    )

    assert result.candidates == ()
    assert {"limit": 5, "query": "Fresh Milk Records"} in discogs_service.search_release_calls
    assert {"limit": 5, "query": "ESSENTIALS EP"} in discogs_service.search_release_calls
    assert {"limit": 5, "query": "eat CJ bin"} not in discogs_service.search_release_calls
    assert {"limit": 5, "query": "RRM nor govz"} not in discogs_service.search_release_calls


def test_identify_service_uses_credit_names_as_supporting_raw_context(
    releases_repository_factory,
    discogs_service_factory,
    build_identify_service,
) -> None:
    repository = releases_repository_factory()
    discogs_service = discogs_service_factory()
    service = build_identify_service(
        repository=repository,
        discogs_service=discogs_service,
        identifiers=ExtractedIdentifiers(text_fragments=("JEEP", "aif", "JEEP HEA", "rom")),
    )

    result = service.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="label-crop.png",
        content_type="image/png",
    )

    assert result.candidates == ()
    assert {"limit": 5, "query": "JEEP HEA"} in discogs_service.search_release_calls
    assert {"limit": 5, "query": "JEEP"} not in discogs_service.search_release_calls

    leading_by_discogs_service = discogs_service_factory()
    service_with_leading_by_context = build_identify_service(
        repository=repository,
        discogs_service=leading_by_discogs_service,
        identifiers=ExtractedIdentifiers(raw_text="by Kid Lib"),
    )

    service_with_leading_by_context.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="label-crop.png",
        content_type="image/png",
    )

    assert {"limit": 5, "query": "Kid Lib"} in leading_by_discogs_service.search_release_calls

    credit_context_discogs_service = discogs_service_factory()
    service_with_credit_context = build_identify_service(
        repository=repository,
        discogs_service=credit_context_discogs_service,
        identifiers=ExtractedIdentifiers(
            text_fragments=("JEEP HEA",),
            raw_text="Written, mixed & produced by Jeep Head",
        ),
    )

    service_with_credit_context.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="label-crop.png",
        content_type="image/png",
    )

    assert {"limit": 5, "query": "Jeep Head"} in credit_context_discogs_service.search_release_calls


def test_identify_service_continues_to_ocr_role_context_after_catalog_hits(
    releases_repository_factory,
    discogs_service_factory,
    build_identify_service,
) -> None:
    repository = releases_repository_factory()
    discogs_service = discogs_service_factory(
        payloads=[
            {
                "results": [
                    {
                        "id": 111,
                        "title": "World Downfall - Remember",
                        "catno": "T.O.S.007",
                    }
                ]
            },
            {
                "results": [
                    {
                        "id": 456,
                        "title": "Sub Basics - Rooms In Time-Space",
                        "catno": "TOS007",
                    }
                ]
            },
        ]
    )
    service = build_identify_service(
        repository=repository,
        discogs_service=discogs_service,
        identifiers=ExtractedIdentifiers(
            catalog_numbers=("TOS007",),
            ocr_roles=(OcrRoleEvidence(role="release_title", text="ROOMS IN", confidence=None, source="tesseract"),),
        ),
    )

    result = service.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="label-crop.png",
        content_type="image/png",
    )

    assert [candidate.discogs_release_id for candidate in result.candidates] == [456, 111]
    assert discogs_service.search_release_calls == [
        {"limit": 5, "catalog_number": "TOS007"},
        {"limit": 5, "query": "TOS007 ROOMS IN"},
    ]
