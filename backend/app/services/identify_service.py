from __future__ import annotations

import logging
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
                "catalog_numbers=%s has_artist=%s has_title=%s text_fragments=%s"
            ),
            filename,
            len(identifiers.barcodes),
            len(identifiers.catalog_numbers),
            bool(identifiers.artist),
            bool(identifiers.title),
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
        for search_step in self._build_search_plan(identifiers):
            logger.info("Searching Discogs identify strategy=%s", search_step.strategy)
            payload = self._execute_search_step(search_step)
            candidates = self._map_external_candidates(payload.get("results", []))
            if candidates:
                return candidates

        return []

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

        return search_steps

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
