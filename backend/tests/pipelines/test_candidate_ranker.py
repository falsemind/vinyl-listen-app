from app.pipelines.identification import CandidateRanker, ExtractedIdentifiers, IdentifyCandidate, OcrRoleEvidence


def test_candidate_ranker_scores_label_and_year_matches() -> None:
    ranker = CandidateRanker()
    identifiers = ExtractedIdentifiers(
        artist="Air",
        title="Moon Safari",
        year=1998,
        label="Source",
        text_fragments=("Source",),
    )
    candidates = [
        IdentifyCandidate(
            discogs_release_id=123,
            release_id=None,
            artist="Air",
            title="Moon Safari",
            year=1998,
            label="Source",
            catalog_number="7243 8 44978 1 8",
            barcode=None,
            cover_image_url=None,
            match_source="discogs",
        )
    ]

    ranked_candidates = ranker.rank(candidates, identifiers, limit=5)

    assert ranked_candidates[0].matched_on == ("artist", "title", "label", "year", "text")
    assert ranked_candidates[0].confidence > 0.2


def test_candidate_ranker_matches_catalog_numbers_after_ocr_punctuation_cleanup() -> None:
    ranker = CandidateRanker()
    identifiers = ExtractedIdentifiers(catalog_numbers=("'- LIONCHGX003",))
    candidates = [
        IdentifyCandidate(
            discogs_release_id=123,
            release_id=None,
            artist="Sub Basics",
            title="Walk & Skank",
            year=None,
            label="Lion Charge Records",
            catalog_number="LIONCHGX003",
            barcode=None,
            cover_image_url=None,
            match_source="discogs",
        )
    ]

    ranked_candidates = ranker.rank(candidates, identifiers, limit=5)

    assert ranked_candidates[0].matched_on == ("catalog_number",)


def test_candidate_ranker_validates_discogs_candidate_against_raw_ocr_text() -> None:
    ranker = CandidateRanker()
    identifiers = ExtractedIdentifiers(
        artist="All tracks mixed and produced by",
        title="Justin Richardson at Mixing Lab Studio",
        raw_text=(
            "DJ KANE PRESENTS\n" "JUST JUNGLE\n" "TOVRI 001\n" "This Side\n" "A. SKY\n" "Other Side\n" "AA. NEXT SOUND"
        ),
    )
    candidates = [
        IdentifyCandidate(
            discogs_release_id=111,
            release_id=None,
            artist="Wrong Artist",
            title="Wrong Title",
            year=None,
            label=None,
            catalog_number=None,
            barcode=None,
            cover_image_url=None,
            match_source="discogs",
        ),
        IdentifyCandidate(
            discogs_release_id=456,
            release_id=None,
            artist="DJ Kane",
            title="Just Jungle",
            year=None,
            label="Trouble On Vinyl",
            catalog_number="TOVRI 001",
            barcode=None,
            cover_image_url=None,
            match_source="discogs",
        ),
    ]

    ranked_candidates = ranker.rank(candidates, identifiers, limit=5)

    assert [candidate.discogs_release_id for candidate in ranked_candidates] == [456, 111]
    assert "ocr_artist" in ranked_candidates[0].matched_on
    assert "ocr_title" in ranked_candidates[0].matched_on
    assert "discogs_validated_text" in ranked_candidates[0].matched_on


def test_candidate_ranker_uses_ocr_role_evidence_to_break_generic_catalog_ties() -> None:
    ranker = CandidateRanker()
    identifiers = ExtractedIdentifiers(
        catalog_numbers=("FMR007",),
        ocr_roles=(
            OcrRoleEvidence(role="release_title", text="ESSENTIALS EP", confidence=None, source="tesseract"),
            OcrRoleEvidence(role="label", text="Fresh Milk Records", confidence=None, source="tesseract"),
        ),
    )
    candidates = [
        IdentifyCandidate(
            discogs_release_id=111,
            release_id=None,
            artist="Wrong Artist",
            title="Other Record",
            year=None,
            label="Other Label",
            catalog_number="FMR007",
            barcode=None,
            cover_image_url=None,
            match_source="discogs",
        ),
        IdentifyCandidate(
            discogs_release_id=456,
            release_id=None,
            artist="Various",
            title="Essentials EP",
            year=None,
            label="Fresh Milk Records",
            catalog_number="FMR007",
            barcode=None,
            cover_image_url=None,
            match_source="discogs",
        ),
    ]

    ranked_candidates = ranker.rank(candidates, identifiers, limit=5)

    assert [candidate.discogs_release_id for candidate in ranked_candidates] == [456, 111]
    assert "ocr_release_title" in ranked_candidates[0].matched_on
    assert "ocr_layout_label" in ranked_candidates[0].matched_on
