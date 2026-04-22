from app.pipelines.identification import CandidateRanker, ExtractedIdentifiers, IdentifyCandidate


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
