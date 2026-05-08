import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.releases import Releases
from app.pipelines.identification import (
    CandidateRanker,
    ExtractedIdentifiers,
    IdentifierExtractor,
    IdentifyCandidate,
    ImageProcessor,
)
from app.pipelines.identification.search_evidence import score_search_evidence
from app.pipelines.identification.search_planner import SearchStep, build_search_plan
from app.repositories.releases_repository import ReleasesRepository
from app.services.discogs_service import DiscogsService

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
DEFAULT_MAX_UPLOAD_SIZE_BYTES = 8 * 1024 * 1024
DEFAULT_CANDIDATE_LIMIT = 5
MAX_RAW_CONTEXT_SEARCHES = 8
CATALOG_CONTEXT_LIMIT = 4
PHRASE_CONTEXT_LIMIT = 5
ROLE_CONTEXT_CATALOG_LIMIT = 1
ROLE_CONTEXT_LABEL_LIMIT = 2
IDENTITY_CONTEXT_LIMIT = 6
QUERY_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9#./-]+")
CREDIT_PREFIXES = (
    "all tracks",
    "additional production",
    "production",
    "mastered",
    "mixed",
    "produced",
    "written",
    "published",
    "copyright",
    "licensed",
)
CREDIT_QUERY_TERMS = (
    " written ",
    " produced ",
    " produc ",
    " production ",
    " mastered ",
    " mixed ",
    " engineered ",
)
LOW_VALUE_QUERY_LINES = {
    "45 rpm",
    "33 rpm",
    "rpm",
    "this side",
    "other side",
    "side a",
    "side b",
}
SIDE_MARKER_PATTERN = r"(?:[A-H]{1,2}|[A-H](?:\d{1,2}|[IL]{1,3}|IV|V))"
TRACK_QUERY_PREFIX_PATTERN = re.compile(rf"^{SIDE_MARKER_PATTERN}[.)]?\s+", re.IGNORECASE)
TRACK_QUERY_DOTTED_PREFIX_PATTERN = re.compile(
    rf"^{SIDE_MARKER_PATTERN}\s*[.),]\s*(?=[A-Za-z0-9])",
    re.IGNORECASE,
)
SIDE_QUALIFIER_PREFIXES = ("there ", "here ")


class IdentifyValidationError(Exception):
    def __init__(self, *, message: str, status_code: int, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


@dataclass(frozen=True)
class IdentifyResult:
    candidates: tuple[IdentifyCandidate, ...]


class IdentifyService:
    def __init__(
        self,
        *,
        discogs_service: DiscogsService | None = None,
        repository: ReleasesRepository | None = None,
        image_processor: ImageProcessor | None = None,
        identifier_extractor: IdentifierExtractor | None = None,
        ranker: CandidateRanker | None = None,
        allowed_content_types: frozenset[str] = DEFAULT_ALLOWED_IMAGE_TYPES,
        max_upload_size_bytes: int = DEFAULT_MAX_UPLOAD_SIZE_BYTES,
        candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
    ) -> None:
        self._discogs_service = discogs_service or DiscogsService()
        self._repository = repository or ReleasesRepository()
        self._image_processor = image_processor or ImageProcessor()
        self._identifier_extractor = identifier_extractor or IdentifierExtractor()
        self._ranker = ranker or CandidateRanker()
        self._allowed_content_types = allowed_content_types
        self._max_upload_size_bytes = max_upload_size_bytes
        self._candidate_limit = candidate_limit

    def identify(
        self,
        db: Session,
        *,
        image_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> IdentifyResult:
        self._validate_upload(
            image_bytes=image_bytes,
            filename=filename,
            content_type=content_type,
        )
        prepared_image = self._image_processor.prepare(
            filename=filename,
            content_type=content_type,
            data=image_bytes,
        )
        logger.info(
            "Identify pipeline prepared image filename=%s width=%s height=%s variants=%s",
            filename,
            prepared_image.width,
            prepared_image.height,
            len(prepared_image.variants),
        )
        identifiers = self._identifier_extractor.extract(prepared_image)

        logger.info(
            (
                "Identify pipeline extracted signals filename=%s barcodes=%s "
                "catalog_numbers=%s has_artist=%s has_title=%s has_year=%s has_label=%s text_fragments=%s evidence=%s"
            ),
            filename,
            len(identifiers.barcodes),
            len(identifiers.catalog_numbers),
            bool(identifiers.artist),
            bool(identifiers.title),
            identifiers.year is not None,
            bool(identifiers.label),
            len(identifiers.text_fragments),
            len(identifiers.identifier_evidence),
        )
        local_candidates = self._find_local_candidates(db, identifiers)
        if local_candidates:
            logger.info("Returning local identify matches filename=%s count=%s", filename, len(local_candidates))
            return IdentifyResult(candidates=tuple(self._rank_candidates(local_candidates, identifiers)))

        external_candidates = self._find_external_candidates(identifiers)
        logger.info("Returning Discogs identify matches filename=%s count=%s", filename, len(external_candidates))
        return IdentifyResult(candidates=tuple(self._rank_candidates(external_candidates, identifiers)))

    def _validate_upload(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> None:
        if not filename.strip():
            raise IdentifyValidationError(
                message="Uploaded image must include a filename.",
                status_code=422,
                code="missing_filename",
            )

        if content_type not in self._allowed_content_types:
            raise IdentifyValidationError(
                message="Unsupported image type. Supported types: image/jpeg, image/png, image/webp.",
                status_code=415,
                code="unsupported_image_type",
            )

        image_size = len(image_bytes)
        if image_size == 0:
            raise IdentifyValidationError(
                message="Uploaded image is empty.",
                status_code=422,
                code="empty_image",
            )

        if image_size > self._max_upload_size_bytes:
            raise IdentifyValidationError(
                message=f"Uploaded image exceeds the {self._max_upload_size_bytes} byte limit.",
                status_code=413,
                code="image_too_large",
            )

    def _find_local_candidates(self, db: Session, identifiers: ExtractedIdentifiers) -> list[IdentifyCandidate]:
        release_map: dict[int, Releases] = {}

        for barcode in identifiers.barcodes:
            for release in self._repository.get_by_barcode(db, barcode):
                release_map.setdefault(release.discogs_release_id, release)

        for catalog_number in identifiers.catalog_numbers:
            for release in self._repository.get_by_catalog_number(db, catalog_number):
                release_map.setdefault(release.discogs_release_id, release)

        if identifiers.artist and identifiers.title:
            for release in self._repository.search_by_artist_and_title(
                db,
                artist=identifiers.artist,
                title=identifiers.title,
                limit=self._candidate_limit,
            ):
                release_map.setdefault(release.discogs_release_id, release)

        return [self._map_local_release(release) for release in release_map.values()]

    def _find_external_candidates(self, identifiers: ExtractedIdentifiers) -> list[IdentifyCandidate]:
        candidate_map: dict[int, IdentifyCandidate] = {}

        for search_step in self._build_search_plan(identifiers):
            if candidate_map and search_step.strategy not in {"catalog_number", "ocr_role_context"}:
                should_continue_to_identity = search_step.strategy in {
                    "artist_title",
                    "identity_context",
                } and not _candidates_contain_identity_context(candidate_map.values(), identifiers)
                if not should_continue_to_identity:
                    logger.info(
                        "Skipping lower-priority Discogs identify strategy=%s after candidate hit",
                        search_step.strategy,
                    )
                    break

            logger.info("Searching Discogs identify strategy=%s", search_step.strategy)
            payload = self._execute_search_step(search_step)
            candidates = self._map_external_candidates(payload.get("results", []))
            if candidates and search_step.strategy == "barcode":
                return candidates

            for candidate in candidates:
                candidate_map.setdefault(candidate.discogs_release_id, candidate)

            if self._has_confident_external_candidate(candidate_map.values(), identifiers):
                logger.info(
                    "Stopping Discogs identify search after confident candidate strategy=%s",
                    search_step.strategy,
                )
                break

        return list(candidate_map.values())

    def _rank_candidates(
        self,
        candidates: list[IdentifyCandidate],
        identifiers: ExtractedIdentifiers,
    ) -> list[IdentifyCandidate]:
        ranked_candidates = self._ranker.rank(candidates, identifiers, limit=self._candidate_limit)
        if ranked_candidates:
            logger.info(
                "Identify top candidate release_id=%s confidence=%s matched_on=%s score_trace=%s",
                ranked_candidates[0].discogs_release_id,
                ranked_candidates[0].confidence,
                ranked_candidates[0].matched_on,
                ranked_candidates[0].score_trace,
            )
        return ranked_candidates

    def _has_confident_external_candidate(
        self,
        candidates: Iterable[IdentifyCandidate],
        identifiers: ExtractedIdentifiers,
    ) -> bool:
        ranked_candidates = self._ranker.rank(list(candidates), identifiers, limit=1)
        if not ranked_candidates:
            return False

        top_candidate = ranked_candidates[0]
        matched_on = set(top_candidate.matched_on)
        if "barcode" in matched_on:
            return True
        if {"artist", "title"}.issubset(matched_on):
            return True
        if {"ocr_artist", "ocr_title"}.issubset(matched_on):
            return True
        if "ocr_title" in matched_on and bool(matched_on & {"label", "ocr_label", "text", "discogs_validated_text"}):
            return True
        return "catalog_number" in matched_on and bool(
            matched_on
            & {
                "artist",
                "title",
                "ocr_artist",
                "ocr_title",
                "ocr_release_title",
                "label",
                "year",
                "text",
            }
        )

    def _build_search_plan(self, identifiers: ExtractedIdentifiers) -> list[SearchStep]:
        return build_search_plan(identifiers)

    def _execute_search_step(self, search_step: SearchStep) -> dict[str, Any]:
        if search_step.strategy == "barcode":
            return self._discogs_service.search_by_barcode(
                str(search_step.params["barcode"]),
                limit=self._candidate_limit,
            )

        return self._discogs_service.search_releases(limit=self._candidate_limit, **search_step.params)

    def _map_local_release(self, release: Releases) -> IdentifyCandidate:
        return IdentifyCandidate(
            discogs_release_id=release.discogs_release_id,
            release_id=release.id,
            artist=release.artist,
            title=release.title,
            year=release.year,
            label=release.label,
            catalog_number=release.catalog_number,
            barcode=release.barcode,
            cover_image_url=release.cover_image_url,
            match_source="local",
        )

    def _map_external_candidates(self, results: list[dict[str, Any]]) -> list[IdentifyCandidate]:
        candidates: list[IdentifyCandidate] = []
        for result in results:
            candidate = self._map_external_candidate(result)
            if candidate is not None:
                candidates.append(candidate)
        return candidates

    def _map_external_candidate(self, result: dict[str, Any]) -> IdentifyCandidate | None:
        discogs_release_id = result.get("id")
        if not isinstance(discogs_release_id, int):
            return None

        artist, title = _parse_discogs_title(_clean_string(result.get("title")))
        if not artist or not title:
            return None

        return IdentifyCandidate(
            discogs_release_id=discogs_release_id,
            release_id=None,
            artist=artist,
            title=title,
            year=_coerce_int(result.get("year")),
            label=_coerce_first_string(result.get("label")),
            catalog_number=_coerce_catalog_number(result.get("catno")),
            barcode=None,
            cover_image_url=_clean_string(result.get("cover_image")) or _clean_string(result.get("thumb")),
            match_source="discogs",
        )


@dataclass(frozen=True)
class _SearchStep:
    strategy: str
    params: dict[str, str]


def _dedupe_search_steps(search_steps: list[_SearchStep]) -> list[_SearchStep]:
    deduped_steps: list[_SearchStep] = []
    seen: set[tuple[str, tuple[tuple[str, str], ...]]] = set()

    for search_step in search_steps:
        key = (search_step.strategy, tuple(sorted(search_step.params.items())))
        if key in seen:
            continue
        seen.add(key)
        deduped_steps.append(search_step)

    return deduped_steps


def _candidates_contain_identity_context(
    candidates: Iterable[IdentifyCandidate],
    identifiers: ExtractedIdentifiers,
) -> bool:
    if not identifiers.artist or not identifiers.title:
        return False

    normalized_artist = _normalize_query_key(identifiers.artist)
    normalized_title = _normalize_query_key(identifiers.title)
    if not normalized_artist or not normalized_title:
        return False

    for candidate in candidates:
        candidate_key = _normalize_query_key(
            " ".join(
                value
                for value in (
                    candidate.artist,
                    candidate.title,
                    candidate.label,
                    candidate.catalog_number,
                )
                if value
            )
        )
        if normalized_artist in candidate_key and normalized_title in candidate_key:
            return True

    return False


def _build_ocr_role_context_queries(identifiers: ExtractedIdentifiers) -> tuple[str, ...]:
    if not identifiers.catalog_numbers or not identifiers.ocr_roles:
        return ()

    title_values = _role_texts(identifiers, "release_title")
    label_values = _role_texts(identifiers, "label")
    if not title_values and not label_values:
        return ()

    queries: list[str] = []
    catalog_numbers = _rank_catalog_context_values(identifiers.catalog_numbers)
    for catalog_number in catalog_numbers[:ROLE_CONTEXT_CATALOG_LIMIT]:
        for title in title_values[:PHRASE_CONTEXT_LIMIT]:
            queries.append(f"{catalog_number} {title}")
        for label in label_values[:ROLE_CONTEXT_LABEL_LIMIT]:
            queries.append(f"{catalog_number} {label}")

    return tuple(_dedupe_strings(queries)[:MAX_RAW_CONTEXT_SEARCHES])


def _build_identity_context_queries(identifiers: ExtractedIdentifiers) -> tuple[str, ...]:
    if not identifiers.artist or not identifiers.title:
        return ()

    raw_lines = [
        line
        for line in _extract_raw_search_lines(identifiers.raw_text)
        if not _looks_like_catalog_query_line(line)
        and not _contains_catalog_value(line, identifiers.catalog_numbers)
        and not _looks_like_credit_query(line)
    ]
    values = [identifiers.artist, identifiers.title, *identifiers.text_fragments, *raw_lines]
    artist_values = _rank_artist_identity_values(
        [value for value in values if _looks_like_artist_variant(value, identifiers.artist)],
        identifiers.artist,
    )
    title_values = _rank_identity_values(_identity_title_values(values, identifiers.title))
    supporting_fragments = _identity_supporting_fragments(
        identifiers.text_fragments,
        artist=identifiers.artist,
        title=identifiers.title,
    )

    queries: list[str] = []
    for artist in artist_values[:3]:
        for title in title_values[:3]:
            if _normalize_query_key(artist) == _normalize_query_key(title):
                continue
            queries.append(f"{artist} {title}")
            for fragment in supporting_fragments[:2]:
                queries.append(f"{artist} {title} {fragment}")
                queries.append(f"{title} {fragment}")

    return tuple(_dedupe_strings(queries)[:IDENTITY_CONTEXT_LIMIT])


def _has_plausible_identity(identifiers: ExtractedIdentifiers) -> bool:
    if not identifiers.artist or not identifiers.title:
        return False
    return not (_looks_like_credit_query(identifiers.artist) or _looks_like_credit_query(identifiers.title))


def _looks_like_credit_query(value: str) -> bool:
    lowered_value = _normalize_credit_query(value)
    stripped_value = lowered_value.strip()
    if stripped_value.startswith(CREDIT_PREFIXES):
        return True
    if stripped_value.endswith(" by"):
        return True
    return any(term in f" {lowered_value} " for term in CREDIT_QUERY_TERMS)


def _normalize_credit_query(value: str) -> str:
    return " ".join(token.lower() for token in QUERY_TOKEN_PATTERN.findall(value))


def _rank_identity_values(values: list[str]) -> list[str]:
    return sorted(_dedupe_strings(values), key=lambda value: (-len(_normalize_query_key(value)), value))


def _rank_artist_identity_values(values: list[str], artist: str) -> list[str]:
    normalized_artist = _normalize_query_key(artist)
    return sorted(
        _dedupe_strings(values),
        key=lambda value: (
            _normalize_query_key(value) != normalized_artist,
            -len(_normalize_query_key(value)),
            value,
        ),
    )


def _contains_catalog_value(value: str, catalog_numbers: tuple[str, ...]) -> bool:
    normalized_value = _normalize_query_key(value)
    return any(_normalize_query_key(catalog_number) in normalized_value for catalog_number in catalog_numbers)


def _identity_title_values(values: list[str | None], title: str) -> list[str]:
    release_type = _extract_release_type_hint(values)
    title_values: list[str] = []
    for value in values:
        if not _looks_like_title_variant(value, title):
            continue
        title_values.extend(_title_search_variants(value, release_type=release_type))
    return title_values


def _identity_supporting_fragments(
    values: tuple[str, ...],
    *,
    artist: str,
    title: str,
) -> list[str]:
    fragments: list[str] = []
    for value in values:
        line = _clean_query_line(value)
        if line is None:
            continue
        if _looks_like_credit_query(line) or _looks_like_catalog_query_line(line):
            continue
        if _looks_like_artist_variant(line, artist) or _looks_like_title_variant(line, title):
            continue
        if not _looks_like_identity_supporting_fragment(line):
            continue
        fragments.append(line)

    return _rank_identity_values(fragments)


def _looks_like_identity_supporting_fragment(value: str) -> bool:
    tokens = QUERY_TOKEN_PATTERN.findall(value)
    if not (1 <= len(tokens) <= 3):
        return False
    if any(token.isdigit() for token in tokens):
        return False
    if len(tokens) == 1:
        token = tokens[0]
        return len(token) >= 5 and token.upper() == token
    return score_search_evidence(value).score >= 2


def _title_search_variants(value: str | None, *, release_type: str | None) -> tuple[str, ...]:
    line = _clean_query_line(value or "")
    if line is None:
        return ()

    variants = [line]
    tokens = line.split()
    if tokens and _release_type_from_token(tokens[-1]) is not None:
        tokens[-1] = _release_type_from_token(tokens[-1]) or tokens[-1]
        variants.append(" ".join(tokens))

    if len(tokens) == 1 and len(tokens[0]) >= 5 and tokens[0].isupper() and not tokens[0].lower().endswith("y"):
        variants.append(f"{tokens[0]}Y")

    if release_type is not None and all(token.upper() not in {"EP", "LP"} for token in tokens):
        variants.extend(f"{variant} {release_type}" for variant in tuple(variants))

    return tuple(_dedupe_strings(variants))


def _extract_release_type_hint(values: list[str | None]) -> str | None:
    for value in values:
        tokens = QUERY_TOKEN_PATTERN.findall(value or "")
        if not tokens:
            continue

        release_type = _release_type_from_token(tokens[-1])
        if release_type is not None:
            return release_type

    return None


def _release_type_from_token(value: str) -> str | None:
    normalized_value = value.upper()
    if normalized_value in {"EP", "LP"}:
        return normalized_value
    if normalized_value in {"FE", "EF", "EIP"}:
        return "EP"
    return None


def _looks_like_artist_variant(value: str | None, artist: str) -> bool:
    if value is None:
        return False

    normalized_artist = _normalize_query_key(artist)
    normalized_value = _normalize_query_key(value)
    if not normalized_artist or not normalized_value:
        return False
    if normalized_value.startswith("dj") and normalized_artist.startswith("dj"):
        return True
    return normalized_artist in normalized_value or normalized_value in normalized_artist


def _looks_like_title_variant(value: str | None, title: str) -> bool:
    if value is None:
        return False

    normalized_title = _normalize_query_key(title)
    normalized_value = _normalize_query_key(value)
    if len(normalized_title) < 4 or len(normalized_value) < 4:
        return False
    if normalized_title in normalized_value or normalized_value in normalized_title:
        return True
    return _common_prefix_length(normalized_title, normalized_value) >= 3


def _common_prefix_length(left: str, right: str) -> int:
    count = 0
    for left_character, right_character in zip(left, right, strict=False):
        if left_character != right_character:
            break
        count += 1
    return count


def _role_texts(identifiers: ExtractedIdentifiers, role: str) -> list[str]:
    return _dedupe_strings([evidence.text for evidence in identifiers.ocr_roles if evidence.role == role])


def _rank_catalog_context_values(catalog_numbers: tuple[str, ...]) -> list[str]:
    return sorted(catalog_numbers, key=_catalog_context_sort_key)


def _catalog_context_sort_key(value: str) -> tuple[int, int, int, str]:
    digit_count = sum(character.isdigit() for character in value)
    suspicious_count = sum(character in "?|" for character in value)
    return suspicious_count, -digit_count, len(value), value


def _build_raw_context_queries(identifiers: ExtractedIdentifiers) -> tuple[str, ...]:
    if not identifiers.raw_text.strip():
        return ()

    raw_lines = _extract_raw_search_lines(identifiers.raw_text)
    if not raw_lines:
        return ()

    catalog_lines = _dedupe_strings(
        [
            *identifiers.catalog_numbers,
            *(line for line in raw_lines if _looks_like_catalog_query_line(line)),
        ]
    )
    phrase_lines = _dedupe_strings(
        [line for line in raw_lines if not _looks_like_catalog_query_line(line) and _looks_like_context_phrase(line)]
    )

    queries: list[str] = []
    for catalog_line in catalog_lines[:CATALOG_CONTEXT_LIMIT]:
        for phrase in phrase_lines[:PHRASE_CONTEXT_LIMIT]:
            if _normalize_query_key(catalog_line) == _normalize_query_key(phrase):
                continue
            queries.append(f"{catalog_line} {phrase}")

    for left, right in zip(phrase_lines, phrase_lines[1:], strict=False):
        queries.append(f"{left} {right}")

    queries.extend(phrase_lines[:PHRASE_CONTEXT_LIMIT])
    return tuple(_dedupe_strings(queries)[:MAX_RAW_CONTEXT_SEARCHES])


def _extract_raw_search_lines(raw_text: str) -> list[str]:
    lines: list[str] = []

    for raw_line in raw_text.splitlines():
        line = _clean_query_line(raw_line)
        if line is not None and _has_query_value(line):
            lines.append(line)

        for credit_name in _extract_credit_name_queries(raw_line):
            if _has_query_value(credit_name):
                lines.append(credit_name)

    return _dedupe_strings(lines)


def _clean_query_line(value: str) -> str | None:
    tokens = QUERY_TOKEN_PATTERN.findall(value)
    if not tokens:
        return None

    line = " ".join(tokens).strip(" -./#")
    line = _strip_track_query_prefix(line)
    lowered_line = line.lower()
    for prefix in SIDE_QUALIFIER_PREFIXES:
        if lowered_line.startswith(prefix) and len(line.split()) > 1:
            line = line[len(prefix) :].strip()
            lowered_line = line.lower()
    normalized_line = " ".join(line.split())
    return normalized_line or None


def _has_query_value(line: str) -> bool:
    lowered_line = line.lower()
    if lowered_line in LOW_VALUE_QUERY_LINES:
        return False
    if _looks_like_credit_query(line):
        return False

    alphanumeric_count = sum(character.isalnum() for character in line)
    return alphanumeric_count >= 4


def _should_search_free_text_fragment(fragment: str) -> bool:
    line = _clean_query_line(fragment)
    if line is None or not _has_query_value(line):
        return False
    if not _looks_like_context_phrase(line):
        return False
    return score_search_evidence(line).is_query_worthy


def _free_text_fragment_queries(fragment: str) -> tuple[str, ...]:
    line = _clean_query_line(fragment)
    if line is None or not _should_search_free_text_fragment(line):
        return ()

    return (line,)


def _extract_credit_name_queries(value: str) -> tuple[str, ...]:
    line = _clean_query_line(value)
    if line is None or " by " not in f" {line.lower()} ":
        return ()

    lowered_line = line.lower()
    if lowered_line.startswith("by "):
        original_credit_value = line[len("by ") :]
    elif " by " in lowered_line:
        _, credit_value = lowered_line.split(" by ", maxsplit=1)
        original_start = len(line) - len(credit_value)
        original_credit_value = line[original_start:]
    else:
        return ()

    names = re.split(r"\s+(?:and|&|x)\s+|,", original_credit_value)

    queries: list[str] = []
    for name in names:
        cleaned_name = _clean_query_line(name)
        if cleaned_name is None or _looks_like_credit_query(cleaned_name):
            continue
        if _looks_like_context_phrase(cleaned_name):
            queries.append(cleaned_name)

    return tuple(_dedupe_strings(queries))


def _looks_like_catalog_query_line(line: str) -> bool:
    if not any(character.isalpha() for character in line) or not any(character.isdigit() for character in line):
        return False

    tokens = line.split()
    if len(tokens) > 3:
        return False

    return not (len(tokens) == 2 and tokens[1].isdigit() and len(tokens[1]) == 4)


def _looks_like_context_phrase(line: str) -> bool:
    if any(character.isdigit() for character in line):
        return False

    tokens = [token for token in line.split() if token]
    if not (1 <= len(tokens) <= 5):
        return False

    return not all(len(token) <= 2 for token in tokens) and score_search_evidence(line).is_query_worthy


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        key = _normalize_query_key(value)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped_values.append(value)

    return deduped_values


def _normalize_query_key(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _strip_track_query_prefix(value: str) -> str:
    stripped_value = value.strip()
    for pattern in (TRACK_QUERY_DOTTED_PREFIX_PATTERN, TRACK_QUERY_PREFIX_PATTERN):
        match = pattern.match(stripped_value)
        if match is not None:
            return stripped_value[match.end() :].strip(" -./#")
    return stripped_value


def _parse_discogs_title(value: str | None) -> tuple[str | None, str | None]:
    if value is None:
        return None, None

    parts = [part.strip() for part in value.split(" - ", maxsplit=1)]
    if len(parts) != 2:
        return None, value

    artist, title = parts
    return artist or None, title or None


def _clean_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    cleaned = value.strip()
    return cleaned or None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _coerce_first_string(value: Any) -> str | None:
    if isinstance(value, str):
        return _clean_string(value)
    if isinstance(value, list):
        for item in value:
            cleaned = _clean_string(item)
            if cleaned:
                return cleaned
    return None


def _coerce_catalog_number(value: Any) -> str | None:
    if isinstance(value, list):
        return _coerce_first_string(value)
    return _clean_string(value)
