# Code Implementation Plan: Manual Release Search

## Goal

Make the Android Manual Search screen functional by adding a backend-backed Discogs release search flow, then letting the app import the selected Discogs release before navigating into session logging.

## Current Repo Findings

| Area | Current state | Work needed |
| :--- | :--- | :--- |
| Android UI | `ManualSearchScreen.kt` already has Artist, Title, Catalog Number, and Year fields. The `Search` button has an empty click handler and results are the injected `records` list. | Replace mock/static results with API-backed state: idle, loading, results, empty, and error. |
| Android navigation | `VinylNavHost.kt` passes `MockVinylData.records`; selecting a row navigates directly to `session_logging/{releaseId}`. | Search results will only have a Discogs ID at first, so selection must call `POST /api/v1/releases/import`, receive internal `release_id`, then navigate. |
| Android API client | `VinylApiClient.kt` supports identify, import, release detail, sessions, home, and analytics. No release search method exists. | Add search DTO parsing and `searchReleases(...)`. Reuse existing `importRelease(...)` after selection. |
| Backend route | `backend/app/api/routes/releases.py` exposes `/`, `/import`, `/{release_id}`, and `/{release_id}/sessions`. | Add `GET /api/v1/releases/search` before `/{release_id}` so route matching stays correct. |
| Backend service | `DiscogsService.search_releases(...)` already supports artist, title, catalog number, barcode, query, limit, offset, in-memory cached search payloads, and `/database/search`. | Wrap this in an API/service response model for manual search. Add `year` support if keeping the current Android field. |
| Docs | `docs/architecture/api-spec.md` already documents `GET /releases/search`; `docs/architecture/navigation-graph.md` says backend does not expose it yet; `docs/product/mvp-screen-spec.md` lists Barcode, while Android currently has Year. | Align API spec, navigation graph, MVP screen spec, and feature docs after implementation decisions. |

## Recommended Contract

`GET /api/v1/releases/search`

Query params:

| Param | Required | Notes |
| :--- | :--- | :--- |
| `artist` | no | Discogs `artist` |
| `title` | no | Discogs `release_title` |
| `catalog` | no | Maps to service `catalog_number` and Discogs `catno` |
| `barcode` | no | Keep because product spec asks for it and service already supports it |
| `year` | no | Add if keeping current Android field |
| `query` | no | General fallback search box support, optional |
| `limit` | no | Default 10, clamp to a small max such as 25 |
| `offset` | no | Default 0 |

Response:

```json
{
  "results": [
    {
      "discogs_release_id": 555123,
      "artist": "Boards of Canada",
      "title": "Music Has The Right To Children",
      "year": 1998,
      "label": "Warp Records",
      "catalog_number": "WARPLP55",
      "thumbnail_url": "https://..."
    }
  ],
  "limit": 10,
  "offset": 0
}
```

Selection flow:

```text
Manual Search -> GET /releases/search -> user selects result -> POST /releases/import -> session_logging/{release_id}
```

## Implementation Phases

### Phase 1: Backend Search Endpoint

| Task | Files | Done criteria |
| :--- | :--- | :--- |
| Add response schemas | `backend/app/schemas/releases.py` | `ReleaseSearchResult` and `ReleaseSearchResponse` models exist with typed Discogs fields. |
| Add route | `backend/app/api/routes/releases.py` | `GET /search` accepts query params, validates at least one search field, calls `DiscogsService.search_releases`, and returns normalized results. |
| Normalize Discogs result payloads | new helper in route or small service module | Handles Discogs `title` strings like `Artist - Title`, labels list, `catno`, `year`, `thumb`/`cover_image`. |
| Preserve route ordering | `backend/app/api/routes/releases.py` | `/search` is declared before `/{release_id}`. |
| Tests | `backend/tests/api/test_releases_api.py` or new focused file | Covers success, empty results, no query fields, invalid pagination, and Discogs error mapping. |

### Phase 2: Android API Wiring

| Task | Files | Done criteria |
| :--- | :--- | :--- |
| Add manual search DTO/domain mapping | `VinylApiClient.kt`, possibly `RecordModels.kt` | App can parse backend search results without pretending they are local `RecordSummary` records. |
| Add `searchReleases(...)` | `VinylApiClient.kt` | Encodes optional query params and returns search results. |
| Add import-on-select flow | `VinylNavHost.kt` or a small state holder | Selecting a Discogs-only result imports it first, then navigates with internal `release_id`. |

### Phase 3: Manual Search Screen State

| Task | Files | Done criteria |
| :--- | :--- | :--- |
| Replace static results | `ManualSearchScreen.kt` | Uses API results, not `MockVinylData.records`. |
| Wire `Search` action | `ManualSearchScreen.kt` | Button triggers search with current fields; disabled while loading or when all fields are blank. |
| Add states | `ManualSearchScreen.kt` | Loading, empty, error, retry, and result selection are visible and accessible. |
| Resolve field mismatch | `ManualSearchScreen.kt`, docs | Choose one: add Barcode to Android, or document Year as supported. Recommended: support both Barcode and Year if layout remains clean. |

### Phase 4: Documentation Alignment

| Doc | Update |
| :--- | :--- |
| `docs/architecture/api-spec.md` | Mark `GET /releases/search` as implemented, fix types, include `catalog_number`, `year`, pagination, and import-on-select flow. |
| `docs/architecture/navigation-graph.md` | Replace the stale note saying no backend manual search endpoint exists. |
| `docs/product/mvp-screen-spec.md` | Align Manual Search fields with final Android UI. |
| `docs/features/backend-services.md` | Add backend manual release search behavior and Discogs cache note. |
| `docs/repository-structure.md` | Only update if new files/modules are added. |

## Verification Plan

Backend:

```text
DISCOGS_TOKEN=test .venv/bin/pytest backend/tests/api/test_releases_api.py backend/tests/services/test_discogs_service.py
DISCOGS_TOKEN=test .venv/bin/ruff check backend/app backend/tests
```

Android:

```text
./gradlew :app:ktlintCheck :app:compileDebugKotlin
./gradlew :app:lintDebug
```

Manual smoke:

```text
Start backend -> open Android app -> Capture Record -> Manual Search -> search known artist/title -> select result -> verify Session Logging receives internal release_id.
```

## Risks

| Risk | Mitigation |
| :--- | :--- |
| Discogs result `title` format is inconsistent | Keep parser defensive; expose raw combined title fallback if split fails. |
| Search results do not have internal `release_id` | Always import on selection before navigating. |
| API spec currently uses `catalog`, while service uses `catalog_number` | Public API keeps `catalog`; backend maps it internally. |
| UI field mismatch: product says Barcode, app has Year | Resolve in Phase 3 and update product docs in Phase 4. |
