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
