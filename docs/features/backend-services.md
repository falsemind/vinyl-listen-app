# Backend Services

This document explains the backend service layer in `backend/app/services/`. Services sit between API routes and repositories/pipelines. Routes handle HTTP details; services own business decisions.

## Service Map

| Service file | Main responsibility | Primary collaborators |
| --- | --- | --- |
| `identify_service.py` | Identify a vinyl release from an uploaded image. | Identification pipeline, `ReleasesRepository`, `DiscogsService`, `CandidateRanker`. |
| `discogs_service.py` | Call Discogs search/release APIs with rate limiting, auth headers, and local release payload caching. | `DiscogsClient`, `DiscogsReleaseRepository`, settings. |
| `release_import_service.py` | Import or fetch a Discogs release into the local `releases` table. | `DiscogsService`, `ReleasesRepository`, `release_mapper.py`. |
| `release_mapper.py` | Convert raw Discogs release payloads into local release fields. | Pure mapping helpers. |
| `sessions_service.py` | Create and read listening sessions and validate session input. | `SessionsRepository`, `ReleasesRepository`, `DiscogsReleaseRepository`. |

## IdentifyService

`IdentifyService` powers `POST /api/v1/identify`. It accepts raw image bytes plus filename/content type and returns up to five ranked `IdentifyCandidate` values.

### Dependencies

- `ImageProcessor` prepares safe image variants and quality metrics.
- `IdentifierExtractor` runs barcode detection, OCR, parsing, and OCR layout analysis.
- `CandidateRanker` scores local and Discogs candidates against extracted identifiers.
- `ReleasesRepository` checks known local releases first.
- `DiscogsService` searches Discogs when local matches are not enough.

### Upload validation

The service rejects invalid uploads before the pipeline runs.

- Allowed content types: `image/jpeg`, `image/png`, `image/webp`.
- Max upload size: `8 MiB`.
- Empty files and blank content types raise `IdentifyValidationError`.
- API routes convert validation errors to structured `ErrorResponse` payloads.

### Identification flow

1. Validate image metadata and byte size.
2. Prepare the image with `ImageProcessor.prepare`.
3. Extract identifiers with `IdentifierExtractor.extract`.
4. Search local releases by barcode, catalog number, and artist/title.
5. If local candidates exist, rank and return them.
6. Build an external Discogs search plan from identifiers.
7. Execute Discogs search steps until enough strong candidates are found.
8. Map Discogs search results to `IdentifyCandidate`.
9. Rank candidates and return the top candidates.

Local matches get `match_source="local"`. Discogs matches get `match_source="discogs"`.

### Local candidate search

Local lookup is intentionally precise. It checks:

- Barcode matches with `get_by_barcode`.
- Catalog number matches with `get_by_catalog_number`.
- Artist/title matches with `search_by_artist_and_title`.

Candidates are deduplicated by Discogs release ID before ranking.

### External candidate search

External lookup uses `build_search_plan` from the identification pipeline. Search strategies include:

- `barcode`
- `catalog_number`
- `catalog_identity_context`
- `vlm_discogs_query`
- `ocr_role_context`
- `artist_title`
- `identity_context`
- `tracklist_context`
- `raw_context`
- `free_text`

Barcode searches stop early when candidates are found, because barcode evidence is the strongest. Other searches are deduplicated and capped so noisy OCR text does not fan out into unlimited Discogs calls.

### Ranking output

The ranker adds:

- `confidence`: normalized score used by clients.
- `matched_on`: tuple of evidence types that matched, such as `barcode`, `catalog_number`, `artist`, `title`, `label`, `year`, or OCR-derived roles.
- `score_trace`: debug-friendly reasons such as `+100 barcode`, `+60 catalog_number`, or contradiction penalties.

## DiscogsService

`DiscogsService` wraps Discogs API access and the local Discogs release cache.

### Configuration

`DiscogsApiConfig.from_settings` reads:

- `discogs_base_url`
- `discogs_token`
- `discogs_user_agent`
- `discogs_request_timeout_seconds`

Missing required Discogs settings raise `DiscogsConfigurationError`.

### Client and rate limiting

`DiscogsClient` builds signed requests with:

- `Authorization: Discogs token=...`
- configured `User-Agent`
- JSON response parsing
- TLS context from `certifi`
- structured `DiscogsClientError` messages for HTTP and URL failures

`DiscogsRateLimiter` serializes calls with a lock and enforces the configured requests-per-minute window.

### Search behavior

`search_by_barcode` delegates to `search_releases` with barcode parameters.

`search_releases`:

- Normalizes query parameters into a deterministic cache key.
- Returns in-memory cached search payloads when fresh.
- Calls Discogs `/database/search`.
- Forces `type=release`.
- Fetches paginated results.
- Stores successful search payloads in memory with a TTL.

### Release fetch behavior

`fetch_release(db, discogs_release_id)`:

1. Checks `DiscogsReleaseRepository` for an existing cached payload.
2. Returns fresh cached payloads without calling Discogs.
3. Touches stale cache rows before refresh attempts.
4. Calls Discogs `/releases/{id}` when needed.
5. Upserts the raw payload into `discogs_release_cache`.

The release cache preserves raw Discogs JSON. Mapping into local release fields happens in `release_mapper.py`.

## ReleaseImportService

`ReleaseImportService` powers release import and local release reads.

### Import flow

1. Fetch the raw Discogs release with `DiscogsService.fetch_release`.
2. Map the raw payload to `InternalReleaseData`.
3. Save or update the local release through `ReleasesRepository.save_or_update`.
4. Return `ReleaseImportResult`.

`ReleaseImportResult.status` returns `created` or `updated`, based on whether the repository created a new row.

### Read and mapping helpers

- `get_release` reads a local release by database ID.
- `map_discogs_payload` exposes the Discogs-to-internal mapping for tests and route workflows.

## release_mapper.py

`release_mapper.py` is a pure mapping module. It converts a Discogs release payload into `InternalReleaseData`.

Mapped fields:

- `discogs_release_id`
- `artist`
- `title`
- `year`
- `label`
- `catalog_number`
- `barcode`
- `genres`
- `styles`
- `cover_image_url`

The mapper handles common Discogs shapes:

- Artist lists become a display artist.
- Label/company arrays provide label name and catalog number.
- Identifier arrays provide barcode values.
- Image arrays provide cover URLs.
- Scalar values are cleaned and coerced before persistence.

## SessionsService

`SessionsService` owns listening session creation and retrieval.

### Create flow

`create_session(db, payload)`:

1. Validates and normalizes input.
2. Confirms the local release exists.
3. Optionally checks the raw Discogs release payload for valid side labels.
4. Creates a session through `SessionsRepository`.
5. Returns `CreateSessionResult` with session ID, timestamp, and `created` status.

### Validation behavior

The service validates:

- `release_id` must point to a local release.
- `played_at` may be omitted or parsed from ISO datetime text.
- `side` is trimmed and uppercased.
- `mood` and `notes` are trimmed and stored as nullable optional text.
- If Discogs track positions are available, requested side must exist on the release.

Errors are typed:

- `SessionValidationError` for malformed input.
- `ReleaseNotFoundError` when a release does not exist.
- `SessionNotFoundError` when a session lookup misses.

### Read behavior

- `get_session` returns one session by ID or raises `SessionNotFoundError`.
- `get_sessions_by_release` validates the release ID, confirms the release exists, and returns all sessions for that release.

## Service Error Boundaries

Routes translate service errors into HTTP status codes:

- Identify validation: `413`, `415`, or `422`.
- Discogs import validation: `422`.
- Missing local release/session: `404`.
- Discogs upstream failures: `404` for missing Discogs releases when detectable, otherwise `502`.

## Testing Coverage

Service behavior is covered under `backend/tests/services/`. Related route behavior is covered under `backend/tests/api/`, and identification pipeline behavior is covered under `backend/tests/pipelines/`.
