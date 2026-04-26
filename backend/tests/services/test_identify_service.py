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
    } in discogs_service.search_release_calls
    assert {"limit": 5, "query": "TOVRI 001 DJ KANE PRESENTS"} in discogs_service.search_release_calls
    assert {"limit": 5, "query": "TOVRI 001 JUST JUNGLE"} in discogs_service.search_release_calls


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
