---
name: backend-services
description: This document explains the backend service layer in `backend/app/services/`. Services sit between API routes and repositories/pipelines. Routes handle HTTP details; services own business decisions.
---

# Backend Services

## Backend Service Map

| Service file | Main responsibility | Primary collaborators |
| --- | --- | --- |
| `identify_service.py` | Identify a vinyl release from an uploaded image. | Identification pipeline, `ReleasesRepository`, `DiscogsService`, `CandidateRanker`. |
| `identify_job_service.py` | Persist and expose async identify job status, enforce identify admission limits, and release processing capacity after terminal outcomes. | `IdentifyService`, `IdentifyJobRepository`, `SessionLocal`, admission controller. |
| `discogs_service.py` | Call Discogs search/release APIs with rate limiting, auth headers, and local release payload caching. | `DiscogsClient`, `DiscogsReleaseRepository`, settings. |
| `release_import_service.py` | Import or fetch a Discogs release into the local `releases` table. | `DiscogsService`, `ReleasesRepository`, `release_mapper.py`. |
| `release_mapper.py` | Convert raw Discogs release payloads into local release fields. | Pure mapping helpers. |
| `sessions_service.py` | Create and read listening sessions and validate session input. | `SessionsRepository`, `ReleasesRepository`, `DiscogsReleaseRepository`. |
| `spotify_listening_import_service.py` | Import backend-local Spotify `end_song` exports, filter private/out-of-scope fields, dedupe events, and report counts/errors. | `SpotifyListeningRepository`, `SpotifyListeningRollupService`, configured import directory. |
| `spotify_listening_rollup_service.py` | Rebuild Spotify summary tables and exact Spotify-to-vinyl collection matches. | `SpotifyListeningRepository`, `ReleasesRepository`. |
| `ai_insights_service.py` | Own the AI Insights chat service boundary, provider fallback behavior, persistent history, and read-only tool context. | `app/ai` runtime adapter, `AiInsightToolRunner`, chat repository. |

## AI Insights and Spotify Tools

`AiInsightsService` persists the single local chat thread, runs deterministic insight tools, and passes bounded context to the configured AI adapter. Collection tools cover listening summaries, recent sessions, top records, style/mood/rating distribution, and high-priority session notes.

Spotify tools are included only for Spotify-specific prompts. They read precomputed rollups and exact collection-match tables, then return compact summaries such as overlap, listening-hour patterns, top artists by period, and known-release recommendation signals. They never expose raw Spotify event rows to the model and do not recommend outside the local collection.

## IdentifyService

`IdentifyService` powers `POST /api/v1/identify` and the background work behind identify jobs. It accepts raw image bytes plus filename/content type and returns up to five ranked `IdentifyCandidate` values.

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
- `validate_upload` is also used by `IdentifyJobService` before creating an async job row.

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

When a progress reporter is provided, the service emits backend status updates before expensive phases:

- `preprocessing_image`
- `extracting_text`
- `parsing_identifiers`
- `searching_local`
- `searching_discogs`
- `ranking_candidates`

When a cancellation checker is provided, the service checks it before and after backend-controlled expensive phases. Cancellation is cooperative: an in-flight OCR, VLM, Discogs, or database call may finish before the next checkpoint observes the request.

## Identify Admission Control

Identify work has two protection layers:

- Inbound API rate limiting in `app/core/rate_limit.py` throttles HTTP request volume and returns structured `429 rate_limited` responses. The default backend is in-memory. Set `inbound_rate_limit_backend=redis` with `inbound_rate_limit_redis_url` to share general API limits across backend workers or instances.
- `IdentifyJobService` admission control protects OCR/search work. It rejects sync identify and async job creation with `429 identify_capacity_exceeded` when local or configured DB-backed capacity is full.

The Redis limiter uses token-bucket state with expiring keys and a short socket/connect timeout from `inbound_rate_limit_redis_timeout_seconds`. MVP behavior is fail-open by default: Redis limiter errors are logged and the request is allowed, so Redis outages do not make the API unavailable. Set `inbound_rate_limit_redis_fail_open=false` before public launch if strict protection is more important than availability during Redis outages.

Async identify jobs store `client_key` in `identify_jobs`. `IdentifyJobService` uses active job counts plus an in-process keyed client lock so one client cannot create more than the configured active job count within a backend process. It can also enforce a configured global active-job count from DB state. Stale active rows are marked `expired` before admission checks so crashed jobs do not block the same client forever. Active rows older than the current service instance startup are also expired before admission, which handles backend restarts that leave orphaned `upload_received` or processing rows without an in-memory worker ticket. A local semaphore caps total in-process identify work. Capacity is released in `finally` after background processing succeeds, fails, expires, or is acknowledged as canceled.

Both generic rate-limit rejects and identify capacity rejects include `Retry-After` so clients can wait before retrying. Android should honor this header before using local exponential backoff with jitter.

The local semaphore and keyed client lock are process-local. DB active counts and stale recovery add shared state awareness, but multiple backend workers still need a database transaction or advisory lock for strict cross-worker admission.

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

## IdentifyJobService

`IdentifyJobService` powers `POST /api/v1/identify/jobs`, `GET /api/v1/identify/jobs/{job_id}`, and `POST /api/v1/identify/jobs/{job_id}/cancel`. It exists so clients can show server-backed Processing screen progress instead of guessing from local HTTP state.

### Create flow

`create_job(db, image_bytes, filename, content_type)`:

1. Validates the upload through `IdentifyService.validate_upload`.
2. Creates an `identify_jobs` row with `status="upload_received"`.
3. Sets `expires_at` to the current time plus the job TTL.
4. Returns an `IdentifyJobStatusResponse` immediately.

The current job TTL is 24 hours.

### Background processing

`process_job(job_id, image_bytes, filename, content_type)` opens a fresh database session, loads the job, and runs `IdentifyService.identify` with a database-backed progress reporter.

The reporter persists status and message updates at each major identify phase. On success, the service stores the serialized `IdentifyResponse` in `result` and marks the job `completed`.

### Cancellation flow

`cancel_job(db, job_id)` is idempotent. For an active job, it records `cancel_requested_at` and returns the current job status with `cancel_requested=true`. It does not immediately rewrite the phase status to `canceled`.

`process_job` passes an `IdentifyJobCancellationToken` into `IdentifyService.identify`. The token checks persisted job state at backend-controlled checkpoints. When cancellation is observed, the job is marked `status="canceled"` with message `Identify canceled`, no `error` payload, and no `result` payload. If cancellation is requested after identify work returns but before the completion write, the result is discarded and the job is still marked `canceled`.

If `cancel_job` is called for a terminal job, the service returns the existing terminal status without rewriting it. Completed jobs remain `completed`, failed jobs remain `failed`, expired jobs remain `expired`, and already canceled jobs remain `canceled`.

Structured cancellation logs distinguish:

- `Identify job cancellation requested`: active job accepted the cancel request.
- `Identify job canceled`: background processing acknowledged cancellation at a checkpoint.
- `Identify job canceled before completion`: cancellation was observed after identify work returned but before result persistence.
- `Identify job cancellation ignored`: cancel request was a duplicate or targeted a terminal job.

### Failure mapping

Failures are persisted as `status="failed"` with an error payload:

- Upload validation failures use `failed_step="upload"`.
- Image preprocessing, OCR, and identifier parsing failures use `failed_step="extract"`.
- Discogs and candidate lookup failures use `failed_step="search"`.
- Unknown failures use `failed_step="unknown"`.

Expired jobs raise `IdentifyJobExpiredError`; missing jobs raise `IdentifyJobNotFoundError`. API routes map those to `410` and `404`.

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

`DiscogsRateLimiter` serializes calls with a lock, keeps configured request spacing as a fallback, and tracks Discogs `X-Discogs-Ratelimit*` response headers. When Discogs reports no remaining requests, the limiter waits for the conservative one-minute window estimate before the next request.

### Search behavior

`search_by_barcode` delegates to `search_releases` with barcode parameters.

`search_releases`:

- Normalizes query parameters into a deterministic cache key.
- Returns in-memory cached search payloads when fresh.
- Calls Discogs `/database/search`.
- Forces `type=release`.
- Supports artist, release title, catalog number, barcode, year, and general query search fields.
- Fetches paginated results.
- Stores successful search payloads in memory with a TTL.

### Manual release search API

`GET /api/v1/releases/search` exposes Discogs release search for the Android Manual Search screen.

The route:

1. Requires at least one search field.
2. Calls `DiscogsService.search_releases`.
3. Normalizes Discogs result payloads into compact candidate rows.
4. Returns Discogs IDs only; clients must call `POST /api/v1/releases/import` after selection to get an internal `release_id`.

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
- `get_available_sides` reads cached Discogs track positions and returns ordered side prefixes for session logging.
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
- `available_sides` for API responses, derived from raw Discogs track positions rather than persisted on `releases`
- `available_side_options` for client selectors that need stable values and labels when side names repeat across multiple discs

The mapper handles common Discogs shapes:

- Artist lists become a display artist.
- Label/company arrays provide label name and catalog number.
- Identifier arrays provide barcode values.
- Image arrays provide cover URLs.
- Track positions provide side options. When a release repeats side names across multiple discs, option values include the disc number, such as `1:X` and `2:X`.
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
- Custom mood options are stored in `session_moods` through `GET/POST/DELETE /api/v1/sessions/moods`; session analytics still reads the selected text from `sessions.mood`.
- Mood names are canonicalized case-insensitively from built-in moods, active custom mood options, or historical session rows before a session is stored.

Errors are typed:

- `SessionValidationError` for malformed input.
- `ReleaseNotFoundError` when a release does not exist.
- `SessionNotFoundError` when a session lookup misses.

### Read behavior

- `get_session` returns one session by ID or raises `SessionNotFoundError`.
- `get_sessions_by_release` validates the release ID, confirms the release exists, and returns all sessions for that release.

## AnalyticsService

`AnalyticsService` owns dashboard aggregations used by the Android Analytics screens.

Analytics endpoints read from persisted releases and sessions:

- `GET /api/v1/analytics/plays/monthly` groups logged sessions by month.
- `GET /api/v1/analytics/top-records` ranks releases by session count and average rating.
- `GET /api/v1/analytics/rating-distribution` counts 1-5 star ratings.
- `GET /api/v1/analytics/mood-distribution` counts saved session mood text and groups case variants together.
- `GET /api/v1/analytics/style-distribution` counts Discogs release styles through logged sessions, preserving specific style labels such as `Dub Techno`, `House`, and `Deep House`.
- `GET /api/v1/analytics/sessions` returns paginated listening sessions for a selected `YYYY-MM` month.
- `GET /api/v1/analytics/records/by-rating` returns paginated record counts for a selected 1-5 star rating.
- `GET /api/v1/analytics/records/by-mood` returns paginated record counts for a selected mood label.
- `GET /api/v1/analytics/records/by-style` returns paginated records for a selected Discogs style.

Style distribution intentionally uses `releases.styles`, not broad `genres`, because the Analytics screen is meant to expose specific listening patterns.
Drilldown pagination is validated at the service boundary: `limit` must be 1-50, `offset` must be nonnegative, rating must be 1-5, month must be strict `YYYY-MM`, and mood/style labels must be nonblank.

## AiInsightsService

`AiInsightsService` powers `POST /api/v1/ai/chat` for the Insights screen chat shell.

The service keeps the HTTP contract stable while the runtime is still experimental:

- It validates the chat message and optional conversation id.
- It returns `local-single-thread` when no conversation id is supplied.
- It calls the configured `app/ai` adapter when `AI_CHAT_ENABLED=true`.
- It returns a clear disabled assistant response when AI chat is off or provider config is incomplete.
- It persists user and assistant messages in `ai_chat_sessions` and `ai_chat_messages`.
- It passes recent persisted chat history to the adapter for conversation continuity.
- It runs deterministic read-only insight tools before the model call and includes their results as bounded prompt context.
- It prioritizes saved session notes when present for recommendation, subjective insight, and "why" questions because notes capture the user's personal listening impressions.
- It exposes history, clear, and export endpoints for private chat data.
- It logs provider, latency, and tool names without message content.

The first runtime adapter targets LM Studio's native `/api/v1/chat` path by default while still supporting OpenAI-compatible chat completions through `AI_CHAT_ENDPOINT_PATH`. Future LangChain or LangGraph orchestration should stay behind the same service boundary. Read-only tools call existing analytics/session/release service or repository methods rather than exposing unrestricted database access to the agent runtime.

## Service Error Boundaries

Routes translate service errors into HTTP status codes:

- Identify validation: `413`, `415`, or `422`.
- Discogs import validation: `422`.
- Missing local release/session: `404`.
- Discogs upstream failures: `404` for missing Discogs releases when detectable, otherwise `502`.
- AI chat validation errors: `422`.

## Testing Coverage

Service behavior is covered under `backend/tests/services/`. Related route behavior is covered under `backend/tests/api/`, and identification pipeline behavior is covered under `backend/tests/pipelines/`.
