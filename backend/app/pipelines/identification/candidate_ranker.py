import re
from dataclasses import dataclass, replace

from app.pipelines.identification.models import ExtractedIdentifiers, IdentifyCandidate
from app.pipelines.identification.normalization import catalog_numbers_match, normalize_barcode

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
STRONG_IDENTIFIER_EVIDENCE_MIN_CONFIDENCE = 0.7
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
        score_trace: list[str] = []
        score = 0

        if candidate.match_source == "local":
            score += 120
            score_trace.append("+120 local_lookup")
            matched_on.append("local_lookup")

        normalized_candidate_barcode = normalize_barcode(candidate.barcode)
        normalized_identifier_barcodes = {normalize_barcode(barcode) for barcode in identifiers.barcodes}
        normalized_identifier_barcodes.discard(None)
        if normalized_candidate_barcode and normalized_candidate_barcode in {
            normalize_barcode(barcode) for barcode in identifiers.barcodes
        }:
            score += 100
            score_trace.append("+100 barcode")
            matched_on.append("barcode")
        elif (
            normalized_candidate_barcode
            and normalized_identifier_barcodes
            and _has_strong_identifier_evidence(identifiers, "barcode")
        ):
            score -= 80
            score_trace.append("-80 barcode_contradiction")

        if candidate.catalog_number and any(
            catalog_numbers_match(
                candidate.catalog_number,
                catalog_number,
                allow_right_ocr_shadow=True,
            )
            for catalog_number in identifiers.catalog_numbers
        ):
            score += 60
            score_trace.append("+60 catalog_number")
            matched_on.append("catalog_number")
        elif (
            candidate.catalog_number
            and identifiers.catalog_numbers
            and _has_strong_identifier_evidence(identifiers, "catalog_number")
        ):
            score -= 35
            score_trace.append("-35 catalog_number_contradiction")

        if identifiers.artist and _normalize_token(candidate.artist) == _normalize_token(identifiers.artist):
            score += 25
            score_trace.append("+25 artist")
            matched_on.append("artist")

        if identifiers.title and _normalize_token(candidate.title) == _normalize_token(identifiers.title):
            score += 25
            score_trace.append("+25 title")
            matched_on.append("title")

        if "artist" in matched_on and "title" in matched_on:
            score += 20
            score_trace.append("+20 artist_title_pair")

        if identifiers.label and _normalize_token(candidate.label) == _normalize_token(identifiers.label):
            score += 15
            score_trace.append("+15 label")
            matched_on.append("label")
        elif identifiers.label and candidate.label and _has_strong_identifier_evidence(identifiers, "label"):
            score -= 10
            score_trace.append("-10 label_contradiction")

        if identifiers.year is not None and candidate.year == identifiers.year:
            score += 10
            score_trace.append("+10 year")
            matched_on.append("year")
        elif (
            identifiers.year is not None
            and candidate.year is not None
            and _has_strong_identifier_evidence(identifiers, "year")
        ):
            score -= 8
            score_trace.append("-8 year_contradiction")

        if identifiers.text_fragments and any(
            _fragment_matches_candidate(fragment, candidate) for fragment in identifiers.text_fragments
        ):
            score += 10
            score_trace.append("+10 text")
            matched_on.append("text")

        if _role_matches_field(identifiers, role="release_title", value=candidate.title):
            score += 40
            score_trace.append("+40 ocr_release_title")
            matched_on.append("ocr_release_title")

        if _role_matches_field(identifiers, role="label", value=candidate.label):
            score += 20
            score_trace.append("+20 ocr_layout_label")
            matched_on.append("ocr_layout_label")

        evidence_tokens = _identifier_evidence_tokens(identifiers)
        artist_overlap = _field_overlap(candidate.artist, evidence_tokens)
        if artist_overlap.matches and artist_overlap.ratio >= 0.6 and "artist" not in matched_on:
            score += 20
            score_trace.append("+20 ocr_artist")
            matched_on.append("ocr_artist")

        title_overlap = _field_overlap(candidate.title, evidence_tokens)
        if title_overlap.matches and title_overlap.ratio >= 0.6 and "title" not in matched_on:
            score += 35
            score_trace.append("+35 ocr_title")
            matched_on.append("ocr_title")

        label_overlap = _field_overlap(candidate.label, evidence_tokens)
        if label_overlap.matches >= 2 and label_overlap.ratio >= 0.6 and "label" not in matched_on:
            score += 15
            score_trace.append("+15 ocr_label")
            matched_on.append("ocr_label")

        if (
            artist_overlap.matches
            and title_overlap.matches
            and ("artist" not in matched_on or "title" not in matched_on)
        ):
            score += 15
            score_trace.append("+15 discogs_validated_text")
            matched_on.append("discogs_validated_text")

        confidence = round(min(max(score, 0) / self._MAX_SCORE, 1.0), 3)
        return replace(candidate, matched_on=tuple(matched_on), confidence=confidence, score_trace=tuple(score_trace))


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


def _normalize_token(value: str | None) -> str:
    if value is None:
        return ""
    return "".join(character.lower() for character in value if character.isalnum())


def _has_strong_identifier_evidence(identifiers: ExtractedIdentifiers, kind: str) -> bool:
    for evidence in identifiers.identifier_evidence:
        if evidence.kind != kind:
            continue
        if evidence.source == "barcode_detector":
            return True
        if kind == "barcode" and evidence.source == "parser":
            return True
        if evidence.confidence is not None and evidence.confidence >= STRONG_IDENTIFIER_EVIDENCE_MIN_CONFIDENCE:
            return True
    return False


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
        if len(matches) / len(field_tokens) >= 0.6 or len(matches) / len(evidence_tokens) >= 0.8:
            return True

    return False


@dataclass(frozen=True)
class _Overlap:
    matches: int
    ratio: float
