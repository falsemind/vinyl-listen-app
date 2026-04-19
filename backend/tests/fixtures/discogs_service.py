from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from app.models.discogs_release_cache import DiscogsReleaseCache
from app.services.discogs_service import DiscogsApiConfig, DiscogsClient


class RecordingTransport:
    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or {"results": []}
        self.calls: list[dict] = []

    def __call__(self, url: str, headers: dict[str, str], timeout: float) -> dict:
        self.calls.append({"url": url, "headers": headers, "timeout": timeout})
        return self.payload


class QueueTransport:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = payloads
        self.calls: list[dict] = []

    def __call__(self, url: str, headers: dict[str, str], timeout: float) -> dict:
        self.calls.append({"url": url, "headers": headers, "timeout": timeout})
        return self.payloads.pop(0)


class InMemoryDiscogsRepository:
    def __init__(self, cache_entry: DiscogsReleaseCache | None = None) -> None:
        self.cache_entry = cache_entry
        self.touch_count = 0
        self.upserts: list[tuple[int, dict]] = []

    def get_by_discogs_release_id(self, _db, discogs_release_id: int) -> DiscogsReleaseCache | None:
        if self.cache_entry and self.cache_entry.discogs_release_id == discogs_release_id:
            return self.cache_entry
        return None

    def touch(self, _db, cache_entry: DiscogsReleaseCache) -> DiscogsReleaseCache:
        self.touch_count += 1
        cache_entry.last_accessed_at = datetime.now(UTC)
        return cache_entry

    def upsert(self, _db, discogs_release_id: int, raw_discogs_json: dict) -> DiscogsReleaseCache:
        self.upserts.append((discogs_release_id, raw_discogs_json))
        self.cache_entry = DiscogsReleaseCache(
            discogs_release_id=discogs_release_id,
            raw_discogs_json=raw_discogs_json,
            cached_at=datetime.now(UTC),
            last_accessed_at=datetime.now(UTC),
        )
        return self.cache_entry


@pytest.fixture
def discogs_api_config() -> DiscogsApiConfig:
    return DiscogsApiConfig(
        base_url="https://api.discogs.test",
        token="secret-token",
        user_agent="vinyl-tests/1.0",
        timeout_seconds=3.5,
    )


@pytest.fixture
def build_discogs_client(
    discogs_api_config: DiscogsApiConfig,
) -> Callable[[Callable[[str, dict[str, str], float], dict]], DiscogsClient]:
    def _build_client(transport: Callable[[str, dict[str, str], float], dict]) -> DiscogsClient:
        return DiscogsClient(config=discogs_api_config, transport=transport)

    return _build_client


@pytest.fixture
def recording_transport_factory() -> Callable[[dict | None], RecordingTransport]:
    def _factory(payload: dict | None = None) -> RecordingTransport:
        return RecordingTransport(payload=payload)

    return _factory


@pytest.fixture
def queue_transport_factory() -> Callable[[list[dict]], QueueTransport]:
    def _factory(payloads: list[dict]) -> QueueTransport:
        return QueueTransport(payloads=list(payloads))

    return _factory


@pytest.fixture
def in_memory_discogs_repository_factory() -> Callable[[DiscogsReleaseCache | None], InMemoryDiscogsRepository]:
    def _factory(cache_entry: DiscogsReleaseCache | None = None) -> InMemoryDiscogsRepository:
        return InMemoryDiscogsRepository(cache_entry=cache_entry)

    return _factory
