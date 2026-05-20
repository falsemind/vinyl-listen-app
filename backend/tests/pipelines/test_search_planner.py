from app.pipelines.identification.models import (
    ExtractedIdentifiers,
    IdentifierEvidence,
    IdentifyCandidate,
    OcrRoleEvidence,
)
from app.pipelines.identification.search_planner import build_search_plan, candidates_contain_identity_context


def test_search_plan_prioritizes_barcode_and_catalog_before_context() -> None:
    identifiers = ExtractedIdentifiers(
        barcodes=("5021603065515",),
        catalog_numbers=("WARPLP55",),
        ocr_roles=(
            OcrRoleEvidence(
                role="release_title",
                text="Music Has The Right To Children",
                confidence=0.9,
                source="paddleocr_vl",
            ),
        ),
    )

    search_steps = build_search_plan(identifiers)

    assert [(step.strategy, step.params) for step in search_steps[:3]] == [
        ("barcode", {"barcode": "5021603065515"}),
        ("catalog_number", {"catalog_number": "WARPLP55"}),
        ("ocr_role_context", {"query": "WARPLP55 Music Has The Right To Children"}),
    ]


def test_search_plan_skips_loose_text_when_paddleocr_has_strong_identity_evidence() -> None:
    identifiers = ExtractedIdentifiers(
        catalog_numbers=("WARPLP55",),
        text_fragments=("Skam Records", "Music Has The Right To Children"),
        raw_text="WARPLP55\nSkam Records\nMusic Has The Right To Children",
        identifier_evidence=(
            IdentifierEvidence(
                kind="catalog_number",
                value="WARPLP55",
                source="paddleocr_vl",
                confidence=0.94,
            ),
        ),
    )

    search_steps = build_search_plan(identifiers)

    assert [step.strategy for step in search_steps] == ["catalog_number"]


def test_search_plan_keeps_loose_text_without_strong_paddleocr_evidence() -> None:
    identifiers = ExtractedIdentifiers(
        catalog_numbers=("WARPLP55",),
        text_fragments=("Skam Records",),
        raw_text="WARPLP55\nSkam Records",
        identifier_evidence=(
            IdentifierEvidence(
                kind="catalog_number",
                value="WARPLP55",
                source="parser",
                confidence=None,
            ),
        ),
    )

    search_steps = build_search_plan(identifiers)

    assert ("catalog_number", {"catalog_number": "WARPLP55"}) in [(step.strategy, step.params) for step in search_steps]
    assert any(step.strategy in {"raw_context", "free_text"} for step in search_steps)


def test_search_plan_uses_catalog_artist_context_before_noisy_identity() -> None:
    identifiers = ExtractedIdentifiers(
        catalog_numbers=("PLANTPOWER012", "PLANTPOWER 012"),
        artist="FOAMPLATE",
        title="SUBNORMAL PLATEAU",
        raw_text="\n".join(
            [
                "PLANTPOWER",
                "012",
                "FOAMPLATE",
                "THIS SIDE",
                "SUBNORMAL PLATEAU",
                "ROTOSCOPE QUAVE STEPPA",
            ]
        ),
    )

    search_steps = build_search_plan(identifiers)

    assert [(step.strategy, step.params) for step in search_steps[:3]] == [
        ("catalog_number", {"catalog_number": "PLANTPOWER012"}),
        ("catalog_number", {"catalog_number": "PLANTPOWER 012"}),
        ("catalog_identity_context", {"query": "PLANTPOWER012 FOAMPLATE"}),
    ]


def test_search_plan_promotes_vlm_discogs_query_before_loose_text() -> None:
    identifiers = ExtractedIdentifiers(
        catalog_numbers=("DAT 095",),
        raw_text="\n".join(
            [
                "DEEP",
                "UNGLLE",
                "Catalog Number: DAT 095",
                "Discogs Query: HARMONY KID LIB DAT 095",
            ]
        ),
    )

    search_steps = build_search_plan(identifiers)

    assert [(step.strategy, step.params) for step in search_steps[:2]] == [
        ("catalog_number", {"catalog_number": "DAT 095"}),
        ("vlm_discogs_query", {"query": "HARMONY KID LIB DAT 095"}),
    ]


def test_search_plan_skips_low_value_identity_pair() -> None:
    identifiers = ExtractedIdentifiers(
        artist="Limited Edition",
        title="BAILEY",
        raw_text="\n".join(["Limited Edition", "BAILEY", "A Shaka", "for SU Productions 2025"]),
    )

    search_steps = build_search_plan(identifiers)

    assert ("artist_title", {"artist": "Limited Edition", "title": "BAILEY"}) not in [
        (step.strategy, step.params) for step in search_steps
    ]
    assert all(step.params.get("query") != "Limited Edition BAILEY" for step in search_steps)


def test_search_plan_prefers_exact_title_before_track_mix_variants() -> None:
    identifiers = ExtractedIdentifiers(
        artist="BAILEY",
        title="Shaka",
        raw_text="\n".join(["BAILEY", "A Shaka", "81 Shaka (Double O Remix)", "82 Shaka (Original Mix)"]),
    )

    search_steps = build_search_plan(identifiers)

    identity_queries = [step.params["query"] for step in search_steps if step.strategy == "identity_context"]
    assert identity_queries[:3] == [
        "BAILEY Shaka",
        "BAILEY Shaka Double O Remix",
        "BAILEY Shaka Original Mix",
    ]


def test_search_plan_pairs_title_with_context_phrases_when_artist_is_missing() -> None:
    identifiers = ExtractedIdentifiers(
        title="TOOLATE",
        raw_text="\n".join(
            [
                "A.SIDE TOOLATE 06:38",
                "[DEEP VOCAL MIX]",
                "Written by Carroll Thompson",
                "Produced by Daryl B & Matt Coleman",
                "B.SIDE TOOLATE 06:56",
                "[UNDERGROUND DUB]",
            ]
        ),
    )

    search_steps = build_search_plan(identifiers)

    assert [(step.strategy, step.params) for step in search_steps[:2]] == [
        ("title_context", {"query": "TOOLATE DEEP VOCAL MIX"}),
        ("title_context", {"query": "TOOLATE UNDERGROUND DUB"}),
    ]


def test_search_plan_compacts_split_track_title_before_context_queries() -> None:
    identifiers = ExtractedIdentifiers(
        title="TOOL LATE",
        raw_text="\n".join(
            [
                "A.SIDE TOOL LATE 06:38",
                "[DEEP VOCAL MIX]",
                "B.SIDE TOOL LATE 06:56",
                "[UNDERGROUND DUB]",
            ]
        ),
        ocr_roles=(
            OcrRoleEvidence(role="release_title", text="[DEEP VOCAL MIX]", confidence=None, source="mlx_vlm"),
            OcrRoleEvidence(role="release_title", text="[UNDERGROUND DUB]", confidence=None, source="mlx_vlm"),
        ),
    )

    search_steps = build_search_plan(identifiers)

    assert [(step.strategy, step.params) for step in search_steps[:2]] == [
        ("title_context", {"query": "TOOLATE DEEP VOCAL MIX"}),
        ("title_context", {"query": "TOOLATE UNDERGROUND DUB"}),
    ]


def test_search_plan_skips_malformed_bracket_raw_lines() -> None:
    identifiers = ExtractedIdentifiers(
        title="TOOL LATE",
        raw_text="\n".join(
            [
                "A.SIDE TOOL LATE 06:38",
                "[DEEP VOCAL MIX]",
                "[UNDERGROUND DUB]",
                "©2023 South Street",
                "NDERGROUND DUB]",
            ]
        ),
        ocr_roles=(
            OcrRoleEvidence(role="release_title", text="[DEEP VOCAL MIX]", confidence=None, source="mlx_vlm"),
            OcrRoleEvidence(role="release_title", text="[UNDERGROUND DUB]", confidence=None, source="mlx_vlm"),
        ),
    )

    search_steps = build_search_plan(identifiers)
    searched_queries = [step.params.get("query") for step in search_steps]

    assert all(not (query or "").startswith("NDERGROUND") for query in searched_queries)
    assert all(" NDERGROUND" not in (query or "") for query in searched_queries)


def test_search_plan_filters_ocr_variant_boilerplate_from_raw_queries() -> None:
    identifiers = ExtractedIdentifiers(
        raw_text="\n".join(
            [
                "Image variant: normalized.",
                "ORCERER",
                "A1. Take Me Higher",
                "Clouds",
            ]
        ),
        text_fragments=("Take Me Higher", "Clouds"),
    )

    search_steps = build_search_plan(identifiers)
    searched_queries = [step.params.get("query") for step in search_steps]

    assert all("Image variant" not in (query or "") for query in searched_queries)


def test_search_plan_filters_credit_prose_from_stamped_label_queries() -> None:
    identifiers = ExtractedIdentifiers(
        catalog_numbers=("RNVO3", "RNV03"),
        artist="DJ Perception",
        title="Phenomenal EP",
        text_fragments=("RHYTHM NVIBE",),
        raw_text="\n".join(
            [
                "RHYTHM NVIBE",
                "RNVO3/DJ Perception/Phenomenal EP",
                "Written & produced by Cameron Phillips.",
                "Manufactured in the UK, Distributed by Juno.",
                "A&R Marc Cotterell // Plastik People Recordings 2019.",
            ]
        ),
    )

    search_steps = build_search_plan(identifiers)
    searched_queries = [step.params.get("query") for step in search_steps]

    assert ("artist_title", {"artist": "DJ Perception", "title": "Phenomenal EP"}) in [
        (step.strategy, step.params) for step in search_steps
    ]
    assert "DJ Perception Phenomenal EP" in searched_queries
    assert all("Manufactured" not in (query or "") for query in searched_queries)
    assert all("Marc Cotterell" not in (query or "") for query in searched_queries)
    assert all("RNVO3/DJ" not in (query or "") for query in searched_queries)


def test_search_plan_builds_tracklist_context_when_only_track_titles_are_known() -> None:
    identifiers = ExtractedIdentifiers(
        text_fragments=("Organix", "Wolpha", "Encoded", "Neurotikum"),
        raw_text="\n".join(["WZ", "A1. Organix", "A2. Wolpha", "B1. Encoded", "B2. Neurotikum"]),
    )

    search_steps = build_search_plan(identifiers)

    assert [(step.strategy, step.params) for step in search_steps[:4]] == [
        ("tracklist_context", {"query": "WZ Organix Wolpha Encoded Neurotikum"}),
        ("tracklist_context", {"query": "WZ Organix Wolpha Encoded"}),
        ("tracklist_context", {"query": "Organix Wolpha Encoded Neurotikum"}),
        ("tracklist_context", {"query": "Organix Wolpha Encoded"}),
    ]


def test_search_plan_does_not_extract_credit_names_from_credit_prose() -> None:
    identifiers = ExtractedIdentifiers(
        text_fragments=("Organix", "Wolpha", "Encoded", "Neurotikum"),
        raw_text="\n".join(
            [
                "All tracks written and produced by David Michela, Mastered @ The Exchange. © Model.",
                "WZ",
                "A1. Organix",
                "A2. Wolpha",
                "B1. Encoded",
                "B2. Neurotikum",
            ]
        ),
    )

    search_steps = build_search_plan(identifiers)

    searched_queries = [step.params.get("query") for step in search_steps]
    assert "David Michela Mastered The Exchange Model" not in searched_queries
    assert searched_queries[:2] == [
        "WZ Organix Wolpha Encoded Neurotikum",
        "WZ Organix Wolpha Encoded",
    ]


def test_candidates_contain_identity_context_matches_artist_and_title() -> None:
    identifiers = ExtractedIdentifiers(artist="Boards of Canada", title="Hi Scores")
    candidates = [
        IdentifyCandidate(
            discogs_release_id=123,
            release_id=None,
            artist="Boards Of Canada",
            title="Hi Scores",
            year=1996,
            label="Skam",
            catalog_number="SKA008",
            barcode=None,
            cover_image_url=None,
            match_source="discogs",
        )
    ]

    assert candidates_contain_identity_context(candidates, identifiers)
