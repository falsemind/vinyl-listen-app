import json
import logging
import ssl
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic, sleep
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import certifi
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.discogs_release_cache import DiscogsReleaseCache
from app.repositories.discogs_release_repository import DiscogsReleaseRepository

logger = logging.getLogger(__name__)


class DiscogsServiceError(Exception):
    """Base error for Discogs integration failures."""


class DiscogsConfigurationError(DiscogsServiceError):
    """Raised when the Discogs integration is misconfigured."""


class DiscogsClientError(DiscogsServiceError):
    """Raised when the Discogs API returns an error or cannot be reached."""


@dataclass(frozen=True)
class DiscogsRateLimitState:
    limit: int | None
    used: int | None
    remaining: int | None
    observed_at: float


@dataclass(frozen=True)
class DiscogsApiConfig:
    base_url: str
    token: str | None
    user_agent: str
    timeout_seconds: float

    @classmethod
    def from_token(cls, token: str) -> "DiscogsApiConfig":
        if not token.strip():
            raise DiscogsConfigurationError("Discogs token is not configured.")

        return cls(
            base_url=settings.discogs_base_url.rstrip("/"),
            token=token,
            user_agent=settings.discogs_user_agent,
            timeout_seconds=settings.discogs_request_timeout_seconds,
        )

    @classmethod
    def unauthenticated(cls) -> "DiscogsApiConfig":
        return cls(
            base_url=settings.discogs_base_url.rstrip("/"),
            token=None,
            user_agent=settings.discogs_user_agent,
            timeout_seconds=settings.discogs_request_timeout_seconds,
        )

    def build_headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        if self.token:
            headers["Authorization"] = f"Discogs token={self.token}"
        return headers


@dataclass(frozen=True)
class DiscogsResponse:
    payload: dict[str, Any]
    headers: Mapping[str, str]


class DiscogsRateLimiter:
    """Process-local limiter backed by observed Discogs quota headers."""

    def __init__(
        self,
        requests_per_minute: int,
        sleep_func: Callable[[float], None] = sleep,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")

        self._requests_per_minute = requests_per_minute
        self._sleep = sleep_func
        self._clock = clock
        self._lock = threading.Lock()
        self._last_request_started_at: float | None = None
        self._rate_limit_state: DiscogsRateLimitState | None = None

    @property
    def rate_limit_state(self) -> DiscogsRateLimitState | None:
        with self._lock:
            return self._rate_limit_state

    def wait(self) -> None:
        with self._lock:
            now = self._clock()
            if self._last_request_started_at is None:
                quota_wait_seconds = self._quota_wait_seconds(now)
                if quota_wait_seconds > 0:
                    self._sleep(quota_wait_seconds)
                    now = self._clock()
                self._last_request_started_at = now
                return

            elapsed = now - self._last_request_started_at
            spacing_wait_seconds = self._minimum_interval_seconds() - elapsed
            quota_wait_seconds = self._quota_wait_seconds(now)
            wait_seconds = max(spacing_wait_seconds, quota_wait_seconds)

            if wait_seconds > 0:
                self._sleep(wait_seconds)
                now = self._clock()

            self._last_request_started_at = now

    def observe_response_headers(self, headers: Mapping[str, str] | None) -> None:
        if not headers:
            return

        limit = _parse_header_int(headers, "X-Discogs-Ratelimit")
        used = _parse_header_int(headers, "X-Discogs-Ratelimit-Used")
        remaining = _parse_header_int(headers, "X-Discogs-Ratelimit-Remaining")
        if limit is None and used is None and remaining is None:
            return

        state = DiscogsRateLimitState(
            limit=limit,
            used=used,
            remaining=remaining,
            observed_at=self._clock(),
        )
        with self._lock:
            self._rate_limit_state = state

        logger.info(
            "Observed Discogs rate limit limit=%s used=%s remaining=%s",
            state.limit,
            state.used,
            state.remaining,
        )

    def _minimum_interval_seconds(self) -> float:
        requests_per_minute = self._requests_per_minute
        if self._rate_limit_state and self._rate_limit_state.limit and self._rate_limit_state.limit > 0:
            requests_per_minute = min(requests_per_minute, self._rate_limit_state.limit)
        return 60.0 / requests_per_minute

    def _quota_wait_seconds(self, now: float) -> float:
        if not self._rate_limit_state or self._rate_limit_state.remaining is None:
            return 0.0
        if self._rate_limit_state.remaining > 0:
            return 0.0
        return max(0.0, self._rate_limit_state.observed_at + 60.0 - now)


class DiscogsClient:
    """Thin client for authenticated Discogs API GET requests."""

    def __init__(
        self,
        config: DiscogsApiConfig,
        rate_limiter: DiscogsRateLimiter | None = None,
        transport: Callable[[str, dict[str, str], float], dict[str, Any] | DiscogsResponse] | None = None,
    ) -> None:
        self._config = config
        self._rate_limiter = rate_limiter or DiscogsRateLimiter(settings.api_rate_limit_per_minute)
        self._transport = transport or self._default_transport

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._rate_limiter.wait()
        url = self._build_url(path, params)
        logger.info("Requesting Discogs resource path=%s", path)
        logger.debug("Discogs request url=%s params=%s", url, params)

        try:
            response = self._coerce_response(
                self._transport(
                    url=url,
                    headers=self._config.build_headers(),
                    timeout=self._config.timeout_seconds,
                )
            )
            self._rate_limiter.observe_response_headers(response.headers)
            rate_limit_state = self._rate_limiter.rate_limit_state
            logger.info(
                "Discogs request succeeded path=%s rate_limit_remaining=%s",
                path,
                rate_limit_state.remaining if rate_limit_state else None,
            )
            return response.payload
        except HTTPError as error:
            self._rate_limiter.observe_response_headers(error.headers)
            logger.warning("Discogs request failed with status path=%s status=%s", path, error.code)
            raise DiscogsClientError(self._parse_error_response(error)) from error
        except URLError as error:
            logger.warning("Discogs request failed path=%s reason=%s", path, error.reason)
            raise DiscogsClientError(f"Unable to reach Discogs API: {error.reason}") from error

    def _coerce_response(self, response: dict[str, Any] | DiscogsResponse) -> DiscogsResponse:
        if isinstance(response, DiscogsResponse):
            return response
        return DiscogsResponse(payload=response, headers={})

    def _build_url(self, path: str, params: dict[str, Any] | None = None) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        url = f"{self._config.base_url}{normalized_path}"

        if not params:
            return url

        filtered_params = {key: value for key, value in params.items() if value is not None and value != ""}
        query_string = urlencode(filtered_params)
        if not query_string:
            return url

        return f"{url}?{query_string}"

    def _default_transport(self, url: str, headers: dict[str, str], timeout: float) -> DiscogsResponse:
        request = Request(url=url, headers=headers, method="GET")
        with urlopen(request, timeout=timeout, context=self._build_ssl_context()) as response:
            payload = response.read().decode("utf-8")
            response_headers = dict(response.headers.items())
        return DiscogsResponse(payload=json.loads(payload), headers=response_headers)

    def _build_ssl_context(self) -> ssl.SSLContext:
        return ssl.create_default_context(cafile=certifi.where())

    def _parse_error_response(self, error: HTTPError) -> str:
        try:
            body = error.read().decode("utf-8")
            payload = json.loads(body)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            payload = None

        if isinstance(payload, dict):
            message = payload.get("message") or payload.get("error") or payload.get("detail")
            if message:
                return f"Discogs API error ({error.code}): {message}"

        return f"Discogs API error ({error.code})"


def _parse_header_int(headers: Mapping[str, str], name: str) -> int | None:
    for header_name, value in headers.items():
        if header_name.lower() != name.lower():
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def _coerce_positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            return None
        return parsed if parsed > 0 else None
    return None


class DiscogsService:
    """Service facade for search and release-metadata access."""

    def __init__(
        self,
        client: DiscogsClient,
        repository: DiscogsReleaseRepository | None = None,
        cache_ttl: timedelta | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._repository = repository or DiscogsReleaseRepository()
        self._cache_ttl = cache_ttl or timedelta(seconds=settings.discogs_cache_ttl_seconds)
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self._search_cache: dict[tuple[tuple[str, Any], ...], tuple[datetime, dict[str, Any]]] = {}

    def search_by_barcode(self, barcode: str, *, limit: int = 10, offset: int = 0) -> dict[str, Any]:
        return self.search_releases(barcode=barcode, limit=limit, offset=offset)

    def search_releases(
        self,
        *,
        artist: str | None = None,
        title: str | None = None,
        catalog_number: str | None = None,
        barcode: str | None = None,
        year: int | None = None,
        query: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        query_params = {
            "type": "release",
            "artist": artist,
            "release_title": title,
            "catno": catalog_number,
            "barcode": barcode,
            "year": year,
            "q": query,
        }
        cache_key = self._search_cache_key(query_params, limit=limit, offset=offset)
        cached_payload = self._get_cached_search_payload(cache_key)
        if cached_payload is not None:
            logger.info("Using cached Discogs search results limit=%s offset=%s", limit, offset)
            return cached_payload

        logger.info("Fetching Discogs search results limit=%s offset=%s", limit, offset)
        payload = self._fetch_search_results(query_params, limit=limit, offset=offset)
        self._search_cache[cache_key] = (self._now_provider(), payload)
        return payload

    def fetch_release(
        self,
        db: Session,
        discogs_release_id: int,
        *,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        cache_entry = self._repository.get_by_discogs_release_id(db, discogs_release_id)
        if not force_refresh and self._is_fresh(cache_entry):
            logger.info("Using cached Discogs release discogs_release_id=%s", discogs_release_id)
            self._repository.touch(db, cache_entry)
            return cache_entry.raw_discogs_json

        logger.info(
            "Fetching Discogs release discogs_release_id=%s force_refresh=%s",
            discogs_release_id,
            force_refresh,
        )
        payload = self._client.get(f"/releases/{discogs_release_id}")
        self._repository.upsert(
            db,
            discogs_release_id=discogs_release_id,
            raw_discogs_json=payload,
        )
        logger.info("Stored Discogs release in cache discogs_release_id=%s", discogs_release_id)
        return payload

    def fetch_collection_releases(
        self,
        *,
        username: str | None = None,
        folder_id: int = 0,
        per_page: int = 50,
        sort: str = "added",
        sort_order: str = "desc",
    ) -> list[dict[str, Any]]:
        resolved_username = (username or "").strip()
        if not resolved_username:
            raise DiscogsConfigurationError("Discogs username is not configured.")

        releases: list[dict[str, Any]] = []
        page = 1
        total_pages = 1

        while page <= total_pages:
            payload = self.fetch_collection_page(
                username=resolved_username,
                folder_id=folder_id,
                page=page,
                per_page=per_page,
                sort=sort,
                sort_order=sort_order,
            )
            page_releases = payload.get("releases")
            if not isinstance(page_releases, list):
                raise DiscogsClientError("Discogs collection response is missing releases.")

            releases.extend(item for item in page_releases if isinstance(item, dict))
            pagination = payload.get("pagination")
            total_pages = (
                _coerce_positive_int(pagination.get("pages") if isinstance(pagination, dict) else None) or page
            )
            page += 1

        return releases

    def fetch_collection_folders(self, *, username: str | None = None) -> list[dict[str, Any]]:
        resolved_username = (username or "").strip()
        if not resolved_username:
            raise DiscogsConfigurationError("Discogs username is not configured.")

        safe_username = quote(resolved_username, safe="")
        payload = self._client.get(f"/users/{safe_username}/collection/folders")
        folders = payload.get("folders")
        if not isinstance(folders, list):
            raise DiscogsClientError("Discogs collection folders response is missing folders.")

        return [folder for folder in folders if isinstance(folder, dict)]

    def fetch_collection_page(
        self,
        *,
        username: str,
        folder_id: int = 0,
        page: int = 1,
        per_page: int = 50,
        sort: str = "added",
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        if not username.strip():
            raise DiscogsConfigurationError("Discogs username is not configured.")

        safe_username = quote(username.strip(), safe="")
        return self._client.get(
            f"/users/{safe_username}/collection/folders/{folder_id}/releases",
            params={
                "page": page,
                "per_page": per_page,
                "sort": sort,
                "sort_order": sort_order,
            },
        )

    def _is_fresh(self, cache_entry: DiscogsReleaseCache | None) -> bool:
        if cache_entry is None:
            return False

        cached_at = cache_entry.cached_at
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=UTC)

        return (self._now_provider() - cached_at) <= self._cache_ttl

    def _fetch_search_results(
        self,
        query_params: dict[str, Any],
        *,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        page = (offset // limit) + 1
        intra_page_offset = offset % limit

        payload = self._client.get(
            "/database/search",
            params={**query_params, "per_page": limit, "page": page},
        )
        results = list(payload.get("results", []))

        while len(results) - intra_page_offset < limit and results:
            if len(results) % limit != 0:
                break

            page += 1
            next_page_payload = self._client.get(
                "/database/search",
                params={**query_params, "per_page": limit, "page": page},
            )
            next_page_results = list(next_page_payload.get("results", []))
            if not next_page_results:
                break
            results.extend(next_page_results)

        payload["results"] = results[intra_page_offset : intra_page_offset + limit]
        return payload

    def _get_cached_search_payload(
        self,
        cache_key: tuple[tuple[str, Any], ...],
    ) -> dict[str, Any] | None:
        cached_search = self._search_cache.get(cache_key)
        if cached_search is None:
            return None

        cached_at, payload = cached_search
        if (self._now_provider() - cached_at) > self._cache_ttl:
            self._search_cache.pop(cache_key, None)
            return None

        return payload

    def _search_cache_key(
        self,
        query_params: dict[str, Any],
        *,
        limit: int,
        offset: int,
    ) -> tuple[tuple[str, Any], ...]:
        normalized_params = {
            **query_params,
            "limit": limit,
            "offset": offset,
        }
        return tuple(
            sorted((key, value) for key, value in normalized_params.items() if value is not None and value != "")
        )
