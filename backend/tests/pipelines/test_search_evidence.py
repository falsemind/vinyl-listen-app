from app.pipelines.identification.search_evidence import score_search_evidence


def test_search_evidence_scores_release_and_label_phrases_as_query_worthy() -> None:
    assert score_search_evidence("ESSENTIALS EP").is_query_worthy
    assert score_search_evidence("Fresh Milk Records").is_query_worthy
    assert score_search_evidence("JUST JUNGLE").is_query_worthy
    assert score_search_evidence("DJ KANE PRESENTS").is_query_worthy


def test_search_evidence_rejects_short_token_soup_and_low_value_lines() -> None:
    assert not score_search_evidence("eat CJ bin").is_query_worthy
    assert not score_search_evidence("RRM nor govz").is_query_worthy
    assert not score_search_evidence("THE").is_query_worthy
    assert not score_search_evidence("SIDES").is_query_worthy
    assert not score_search_evidence("ile").is_query_worthy
