import re
from dataclasses import dataclass, replace

from app.pipelines.identification.models import ExtractedIdentifiers, IdentifyCandidate

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
STOPWORDS = frozenset(
    {
        "a",
        "aa",
        "and",
        "at",
        "by",
        "cat",
        "catalog",
        "copyright",
        "label",
        "mastered",
        "mixed",
        "music",
        "other",
        "present",
        "presents",
        "produced",
        "record",
        "records",
        "remaster",
        "remasters",
        "rpm",
        "side",
        "the",
        "this",
        "track",
        "tracks",
        "vinyl",
    }
)


class CandidateRanker:
    _MAX_SCORE = 385.0

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

        if identifiers.label and _normalize_token(candidate.label) == _normalize_token(identifiers.label):
            score += 15
            matched_on.append("label")

        if identifiers.year is not None and candidate.year == identifiers.year:
            score += 10
            matched_on.append("year")

        if identifiers.text_fragments and any(
            _fragment_matches_candidate(fragment, candidate) for fragment in identifiers.text_fragments
        ):
            score += 10
            matched_on.append("text")

        if _role_matches_field(identifiers, role="release_title", value=candidate.title):
            score += 40
            matched_on.append("ocr_release_title")

        if _role_matches_field(identifiers, role="label", value=candidate.label):
            score += 20
            matched_on.append("ocr_layout_label")

        evidence_tokens = _identifier_evidence_tokens(identifiers)
        artist_overlap = _field_overlap(candidate.artist, evidence_tokens)
        if artist_overlap.matches and artist_overlap.ratio >= 0.6 and "artist" not in matched_on:
            score += 20
            matched_on.append("ocr_artist")

        title_overlap = _field_overlap(candidate.title, evidence_tokens)
        if title_overlap.matches and title_overlap.ratio >= 0.6 and "title" not in matched_on:
            score += 35
            matched_on.append("ocr_title")

        label_overlap = _field_overlap(candidate.label, evidence_tokens)
        if label_overlap.matches >= 2 and label_overlap.ratio >= 0.6 and "label" not in matched_on:
            score += 15
            matched_on.append("ocr_label")

        if (
            artist_overlap.matches
            and title_overlap.matches
            and ("artist" not in matched_on or "title" not in matched_on)
        ):
            score += 15
            matched_on.append("discogs_validated_text")

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
        _normalize_token(candidate.label),
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
    return "".join(character.lower() for character in value if character.isalnum())


def _identifier_evidence_tokens(identifiers: ExtractedIdentifiers) -> set[str]:
    values = [
        identifiers.raw_text,
        identifiers.artist,
        identifiers.title,
        identifiers.label,
        *identifiers.text_fragments,
        *(role.text for role in identifiers.ocr_roles),
    ]
    return {
        token
        for value in values
        for token in _tokenize(value)
        if token not in STOPWORDS and (len(token) >= 2 or token.isdigit())
    }


def _tokenize(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(match.group(0).lower() for match in TOKEN_PATTERN.finditer(value))


def _field_overlap(value: str | None, evidence_tokens: set[str]) -> "_Overlap":
    field_tokens = [token for token in _tokenize(value) if token not in STOPWORDS and len(token) >= 2]
    if not field_tokens:
        return _Overlap(matches=0, ratio=0.0)

    matches = sum(1 for token in field_tokens if token in evidence_tokens)
    return _Overlap(matches=matches, ratio=matches / len(field_tokens))


def _role_matches_field(identifiers: ExtractedIdentifiers, *, role: str, value: str | None) -> bool:
    if value is None:
        return False

    field_tokens = {token for token in _tokenize(value) if token not in STOPWORDS and len(token) >= 2}
    if not field_tokens:
        return False

    for evidence in identifiers.ocr_roles:
        if evidence.role != role:
            continue

        evidence_tokens = {token for token in _tokenize(evidence.text) if token not in STOPWORDS and len(token) >= 2}
        if not evidence_tokens:
            continue

        matches = field_tokens & evidence_tokens
        if len(matches) / len(field_tokens) >= 0.6:
            return True

    return False


@dataclass(frozen=True)
class _Overlap:
    matches: int
    ratio: float
