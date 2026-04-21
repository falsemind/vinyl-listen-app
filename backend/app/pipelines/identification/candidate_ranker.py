from __future__ import annotations

from dataclasses import replace

from app.pipelines.identification.models import ExtractedIdentifiers, IdentifyCandidate


class CandidateRanker:
    _MAX_SCORE = 300.0

    def rank(
        self,
        candidates: list[IdentifyCandidate],
        identifiers: ExtractedIdentifiers,
        *,
        limit: int,
    ) -> list[IdentifyCandidate]:
        ranked_candidates = [self._score_candidate(candidate, identifiers) for candidate in candidates]
        ranked_candidates.sort(
            key=lambda candidate: (
                candidate.confidence,
                candidate.match_source == "local",
                candidate.artist.lower(),
                candidate.title.lower(),
            ),
            reverse=True,
        )
        return ranked_candidates[:limit]

    def _score_candidate(
        self,
        candidate: IdentifyCandidate,
        identifiers: ExtractedIdentifiers,
    ) -> IdentifyCandidate:
        matched_on: list[str] = []
        score = 0

        if candidate.match_source == "local":
            score += 120
            matched_on.append("local_lookup")

        normalized_candidate_barcode = _normalize_barcode(candidate.barcode)
        if normalized_candidate_barcode and normalized_candidate_barcode in {
            _normalize_barcode(barcode) for barcode in identifiers.barcodes
        }:
            score += 100
            matched_on.append("barcode")

        normalized_candidate_catalog_number = _normalize_token(candidate.catalog_number)
        if normalized_candidate_catalog_number and normalized_candidate_catalog_number in {
            _normalize_token(catalog_number) for catalog_number in identifiers.catalog_numbers
        }:
            score += 60
            matched_on.append("catalog_number")

        if identifiers.artist and _normalize_token(candidate.artist) == _normalize_token(identifiers.artist):
            score += 25
            matched_on.append("artist")

        if identifiers.title and _normalize_token(candidate.title) == _normalize_token(identifiers.title):
            score += 25
            matched_on.append("title")

        if identifiers.text_fragments and any(
            _fragment_matches_candidate(fragment, candidate) for fragment in identifiers.text_fragments
        ):
            score += 10
            matched_on.append("text")

        confidence = round(min(score / self._MAX_SCORE, 1.0), 3)
        return replace(candidate, matched_on=tuple(matched_on), confidence=confidence)


def _fragment_matches_candidate(fragment: str, candidate: IdentifyCandidate) -> bool:
    normalized_fragment = _normalize_token(fragment)
    if not normalized_fragment:
        return False

    haystacks = [
        _normalize_token(candidate.artist),
        _normalize_token(candidate.title),
        _normalize_token(candidate.catalog_number),
    ]
    return any(normalized_fragment in haystack for haystack in haystacks if haystack)


def _normalize_barcode(value: str | None) -> str | None:
    if value is None:
        return None

    digits_only = "".join(character for character in value if character.isdigit())
    return digits_only or None


def _normalize_token(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.strip().lower().split())
