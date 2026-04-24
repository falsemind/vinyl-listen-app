from __future__ import annotations

import logging
import re
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
from app.repositories.releases_repository import ReleasesRepository
from app.services.discogs_service import DiscogsService

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
DEFAULT_MAX_UPLOAD_SIZE_BYTES = 8 * 1024 * 1024
DEFAULT_CANDIDATE_LIMIT = 5
MAX_RAW_CONTEXT_SEARCHES = 8
CATALOG_CONTEXT_LIMIT = 4
PHRASE_CONTEXT_LIMIT = 5
QUERY_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9#./-]+")
CREDIT_PREFIXES = (
    "all tracks",
    "mastered",
    "mixed",
    "produced",
    "written",
    "published",
    "copyright",
    "licensed",
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
                "catalog_numbers=%s has_artist=%s has_title=%s has_year=%s has_label=%s text_fragments=%s"
            ),
            filename,
            len(identifiers.barcodes),
            len(identifiers.catalog_numbers),
            bool(identifiers.artist),
            bool(identifiers.title),
            identifiers.year is not None,
            bool(identifiers.label),
            len(identifiers.text_fragments),
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
            logger.info("Searching Discogs identify strategy=%s", search_step.strategy)
            payload = self._execute_search_step(search_step)
            candidates = self._map_external_candidates(payload.get("results", []))
            if candidates and search_step.strategy == "barcode":
                return candidates

            for candidate in candidates:
                candidate_map.setdefault(candidate.discogs_release_id, candidate)

        return list(candidate_map.values())

    def _rank_candidates(
        self,
        candidates: list[IdentifyCandidate],
        identifiers: ExtractedIdentifiers,
    ) -> list[IdentifyCandidate]:
        return self._ranker.rank(candidates, identifiers, limit=self._candidate_limit)

    def _build_search_plan(self, identifiers: ExtractedIdentifiers) -> list[_SearchStep]:
        search_steps: list[_SearchStep] = []

        for barcode in identifiers.barcodes:
            search_steps.append(_SearchStep(strategy="barcode", params={"barcode": barcode}))

        for catalog_number in identifiers.catalog_numbers:
            search_steps.append(_SearchStep(strategy="catalog_number", params={"catalog_number": catalog_number}))

        if identifiers.artist and identifiers.title:
            search_steps.append(
                _SearchStep(
                    strategy="artist_title",
                    params={"artist": identifiers.artist, "title": identifiers.title},
                )
            )

        for fragment in identifiers.text_fragments:
            normalized_fragment = fragment.strip()
            if normalized_fragment:
                search_steps.append(_SearchStep(strategy="free_text", params={"query": normalized_fragment}))

        for query in _build_raw_context_queries(identifiers):
            search_steps.append(_SearchStep(strategy="raw_context", params={"query": query}))

        return _dedupe_search_steps(search_steps)

    def _execute_search_step(self, search_step: _SearchStep) -> dict[str, Any]:
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
        if line is None or not _has_query_value(line):
            continue
        lines.append(line)

    return _dedupe_strings(lines)


def _clean_query_line(value: str) -> str | None:
    tokens = QUERY_TOKEN_PATTERN.findall(value)
    if not tokens:
        return None

    line = " ".join(tokens).strip(" -./#")
    normalized_line = " ".join(line.split())
    return normalized_line or None


def _has_query_value(line: str) -> bool:
    lowered_line = line.lower()
    if lowered_line in LOW_VALUE_QUERY_LINES:
        return False
    if lowered_line.startswith(CREDIT_PREFIXES):
        return False

    alphanumeric_count = sum(character.isalnum() for character in line)
    return alphanumeric_count >= 4


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

    return not all(len(token) <= 2 for token in tokens)


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
