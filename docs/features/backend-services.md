---
name: backend-services
description: This document explains the backend service layer in `backend/app/services/`. Services sit between API routes and repositories/pipelines. Routes handle HTTP details; services own business decisions.
---

# Backend Services

## Backend Service Map

| Service file | Main responsibility | Primary collaborators |
| --- | --- | --- |
| `auth_account_service.py` | Register accounts, verify email codes, sign in with password, resend verification, run password reset/change flows, and delete accounts after password re-authentication. | `AuthRepository`, `Argon2idPasswordHasher`, auth email sender. |
| `account_data_mutation.py` | Shared guard for reset-deleted account data mutations. Locks the user account row so app-data writes serialize with full account data resets. | `AuthRepository`, `user_accounts`. |
| `auth_token_service.py` | Issue access tokens, rotate refresh tokens, detect refresh-token reuse, and enforce inactivity re-auth. | `AuthRepository`, `AccessTokenService`, `consumed_refresh_tokens`. |
| `auth_email_delivery.py` | Send auth verification/reset messages through local JSONL outbox or Mailgun Provider API. | Auth account service, Mailgun configuration, local outbox path. |
| `password_hashing.py` | Hash and verify passwords with Argon2id plus versioned cost metadata. | Argon2 runtime settings. |
| `entitlement_service.py` | Check capability access and record user-scoped usage events for future gated features. | `AuthRepository`, `user_entitlements`, `usage_events`. |
| `identify_service.py` | Identify a vinyl release from an uploaded image. | Identification pipeline, `ReleasesRepository`, `DiscogsIntegrationService`, `DiscogsService`, `CandidateRanker`. |
| `identify_job_service.py` | Persist and expose async image and text-only identify job status, enforce identify admission and usage limits, serialize job admission with account data resets, and release processing capacity after terminal outcomes. | `IdentifyService`, `IdentifyJobRepository`, `EntitlementService`, `SessionLocal`, admission controller, account data mutation guard. |
| `discogs_integration_service.py` | Validate, store, expose, and reset sanitized Discogs integration state under the account data mutation guard. | `ProviderIntegrationRepository`, `CollectionSettingsRepository`, `TokenCipher`, `DiscogsClient`, account data mutation guard. |
| `token_cipher.py` | Encrypt and decrypt stored provider access tokens. | `DISCOGS_TOKEN_ENCRYPTION_KEY`. |
| `discogs_service.py` | Call Discogs search/release/collection APIs with rate limiting, auth headers, and local release payload caching. | Explicit `DiscogsClient`, `DiscogsReleaseRepository`, settings for URL/user-agent/timeouts. |
| `collection_sync_service.py` | Sync Discogs collection metadata and folder memberships while respecting the persisted collection source of truth. In `APP` mode, local membership is preserved even when Discogs returns empty or missing items. | `DiscogsIntegrationService`, `DiscogsService`, `ReleasesRepository`, `CollectionFoldersRepository`, `CollectionSettingsRepository`, `release_mapper.py`. |
| `collection_sync_job_service.py` | Persist and expose manual collection sync job progress for Android polling while guarding queued, progress, completion, and failure writes against account data resets. | `CollectionSyncService`, `CollectionSyncJobRepository`, `SessionLocal`, account data mutation guard. |
| `release_import_service.py` | Import, refresh, or fetch a Discogs release in the local `releases` table. | `DiscogsIntegrationService`, `DiscogsService`, `ReleasesRepository`, `DiscogsReleaseRepository`, `release_mapper.py`. |
| `manual_release_service.py` | Create, validate, and manage user-owned manual release drafts and saved manual releases under the account data mutation guard. | `ManualReleaseRepository`, `manual_release_policy.py`, `manual_releases`, `manual_release_drafts`, account data mutation guard. |
| `manual_release_policy.py` | Shared manual entry validation constants for field limits, draft cap, supported formats, vinyl details, track roles, and cover uploads. | Manual release schemas and service validation. |
| `release_mapper.py` | Convert raw Discogs release payloads into local release fields. | Pure mapping helpers. |
| `sessions_service.py` | Create, edit, and read listening sessions, including optional track selections, timed-session membership, active collection membership checks, and account-reset-safe session mutations. | `SessionsRepository`, `ReleasesRepository`, `DiscogsReleaseRepository`, `SessionGroupsService`, account data mutation guard. |
| `session_groups_service.py` | Start, read, finish, and auto-expire optional timed listening session groups while serializing mutating paths with account data resets. | `SessionGroupsRepository`, `SessionsRepository`, account data mutation guard. |
| `spotify_listening_import_service.py` | Import backend-local Spotify `end_song` exports, filter private/out-of-scope fields, dedupe events, rebuild rollups, and commit import batches under the account data mutation guard. | `SpotifyListeningRepository`, `SpotifyListeningRollupService`, configured import directory, account data mutation guard. |
| `spotify_listening_rollup_service.py` | Rebuild Spotify summary tables and exact Spotify-to-vinyl collection matches. | `SpotifyListeningRepository`, `ReleasesRepository`. |
| `ai_insights_service.py` | Own the AI Insights chat service boundary, provider fallback behavior, persistent history, read-only tool context, and account-reset-safe chat mutations. | `app/ai` runtime adapter, `AiInsightToolRunner`, chat repository, account data mutation guard. |

## Auth Services

Auth is exposed through `/api/v1/auth/*` and guarded by `app/api/auth_dependencies.py`. The route layer maps service errors to structured API errors such as `auth_required`, `invalid_access_token`, `email_code_expired`, `refresh_token_reuse_detected`, and `inactivity_reauth_required`.

`AuthAccountService` owns account bootstrap and password flows:

1. `register_account` creates an unverified `user_accounts` row, hashes the password with Argon2id, stores a hashed verification code, and sends the plaintext code through the configured email sender.
2. `verify_email` consumes the latest matching single-use code and marks the account verified.
3. `resend_email_verification` issues a new code after the configured cooldown.
4. `sign_in_with_password` verifies the stored password hash and blocks sign-in until email verification is complete.
5. `request_password_reset` and `confirm_password_reset` issue and consume reset codes. Reset confirmation updates the password hash and revokes existing sessions. Reset-request email delivery failures are logged and still return the generic accepted response.
6. `change_password` verifies the current password, stores a fresh Argon2id hash, revokes other active sessions unless sign-out-everywhere is requested, and sends a best-effort security notification email after the DB commit succeeds.
7. `delete_account` verifies the password, hard-deletes user-owned rows and auth state including structured auth audit rows for that account, and retains only a minimal deletion audit receipt.
8. `reset_account_data` verifies the password and hard-deletes user-owned app rows and provider tokens while preserving the auth account, active sessions, security audit rows, entitlement identity, and usage quota ledger.

Verification and reset confirmation track failed code attempts on the latest code row for the account. After the configured attempt limit, the flow returns a typed `429` until the lock window expires.

### Account Data Reset Serialization

`reset_account_data` locks the target `user_accounts` row while deleting resettable app data. Any service that creates, updates, or deletes reset-deleted user data must call `lock_account_data_mutation` before the first account-owned write so concurrent requests serialize with the reset. This includes manual release drafts/releases and cover metadata, identify jobs, Discogs provider tokens and collection settings, collection sync jobs and progress updates, listening sessions and timed session groups, Spotify listening imports and rollups, and AI chat history.

The lock is transaction-scoped. When a mutation spans multiple reset-deleted tables, the service should keep related writes in one transaction where possible, or reacquire the guard before each later write and re-read the target row after locking. Long-running job callbacks that run synchronously inside an already-locked operation should reuse that session and flush progress without taking a second lock. Callback paths that run in a separate session must guard the write and no-op if reset already removed the job.

Usage quota and entitlement rows are intentionally not reset-deleted. Identify admission records usage and creates the resettable job in the same guarded transaction so a data reset cannot leave a post-reset job behind or clear a user's rolling quota ledger.

`AuthRepository.record_auth_audit_event` stores structured audit rows for auth-sensitive operations. Current event coverage includes account registration, email verification/resend, sign-in success/failure, password reset request/confirmation, password change success/failure, account deletion rejection, account data reset success/rejection, auth session creation, refresh-token rotation/rejection, logout, and logout-all. Audit event details must stay non-secret: no plaintext emails, passwords, verification/reset codes, provider tokens, access tokens, or refresh tokens.

`AuthTokenLifecycleService` owns session tokens:

- Access tokens are short-lived HMAC-signed bearer tokens with minimal `sub`, `sid`, `iat`, and `exp` claims.
- Refresh tokens are opaque, stored as hashes, and rotated on every refresh.
- Consumed refresh token hashes are kept so token reuse can be detected and the owning session revoked.
- Sessions that exceed the inactivity window return `inactivity_reauth_required`; clients should ask for the password again.
- Session creation, successful refresh rotation, and rejected refresh attempts are written to `auth_audit_events`.

Email delivery is local by default. With `AUTH_EMAIL_DELIVERY_BACKEND=local`, auth emails are written to `AUTH_LOCAL_EMAIL_OUTBOX_PATH` as JSONL for development testing. With `AUTH_EMAIL_DELIVERY_BACKEND=mailgun`, `MAILGUN_API_KEY` and `MAILGUN_DOMAIN` must be configured.

## EntitlementService

`EntitlementService` is the backend foundation for future paid or limited features. It checks capability keys such as `ocr_identify` against the authenticated user's entitlement row, sums usage events inside the configured rolling window, and records accepted usage events.

Current behavior:

- Missing entitlement rows are treated as `FREE` and are created when accepted usage is recorded.
- `FREE` and `TRIAL` OCR/identify limits are configurable; `PLUS` and `PRO` are represented as unlimited in the default rule set.
- Sync identify and accepted async identify jobs each record one `ocr_identify` usage unit.
- PostgreSQL deployments serialize `consume_usage` with a transaction-level advisory lock per `(user_id, capability)` before reading the current usage sum and inserting the new usage event.
- Validation errors, capacity rejections, and over-limit denials do not record usage.
- Over-limit denials raise `FeatureGateError`, which API routes map to `402 feature_usage_limit_exceeded`.

## AI Insights and Spotify Tools

`AiInsightsService` persists the single local chat thread, runs deterministic insight tools, and passes bounded context to the configured AI adapter. Collection tools cover listening summaries, recent sessions, top records, style/mood/rating distribution, and high-priority session notes.

Spotify tools are included only for Spotify-specific prompts. They read the authenticated user's precomputed rollups and exact collection-match tables, then return compact summaries such as overlap, listening-hour patterns, top artists by period, and known-release recommendation signals. They never expose raw Spotify event rows to the model and do not recommend outside that user's collection.

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
7. Build a token-backed `DiscogsService` from saved integration credentials.
8. Execute Discogs search steps until enough strong candidates are found.
9. Map Discogs search results to `IdentifyCandidate`.
10. Rank candidates and return the top candidates.

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
- `EntitlementService` gates the `ocr_identify` capability and records usage for accepted sync identify calls and accepted async identify jobs.

The Redis limiter uses token-bucket state with expiring keys and a short socket/connect timeout from `inbound_rate_limit_redis_timeout_seconds`. MVP behavior is fail-open by default: Redis limiter errors are logged and the request is allowed, so Redis outages do not make the API unavailable. Set `inbound_rate_limit_redis_fail_open=false` before public launch if strict protection is more important than availability during Redis outages.

Async identify jobs store both `user_id` and `client_key` in `identify_jobs`. `user_id` owns create/status/cancel access; `client_key` remains an admission-control signal within that owner. `IdentifyJobService` uses active job counts plus an in-process keyed client lock so one user/client pair cannot create more than the configured active job count within a backend process. It can also enforce a configured global active-job count from DB state. Stale active rows are marked `expired` before admission checks so crashed jobs do not block the same client forever. Active rows older than the current service instance startup are also expired before admission, which handles backend restarts that leave orphaned `upload_received` or processing rows without an in-memory worker ticket. A local semaphore caps total in-process identify work. Capacity is released in `finally` after background processing succeeds, fails, expires, or is acknowledged as canceled.

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

`IdentifyJobService` powers `POST /api/v1/identify/jobs`, `POST /api/v1/identify/text/jobs`, `GET /api/v1/identify/jobs/{job_id}`, and `POST /api/v1/identify/jobs/{job_id}/cancel`. It exists so clients can show server-backed Processing screen progress instead of guessing from local HTTP state.

### Create flow

`create_job(db, image_bytes, filename, content_type)`:

1. Validates the upload through `IdentifyService.validate_upload`.
2. Runs stale-job and active-capacity admission checks.
3. Records one `ocr_identify` usage unit after the job is admitted.
4. Creates an `identify_jobs` row with `status="upload_received"`.
5. Sets `expires_at` to the current time plus the job TTL.
6. Returns an `IdentifyJobStatusResponse` immediately.

The current job TTL is 24 hours.

`create_text_job(db, request)` uses the same stale-job, active-capacity, entitlement, expiration, status read, and cancellation infrastructure as image jobs. It creates an `identify_jobs` row with `status="text_received"`, stores source metadata with `event_source="text_identify"` and `source_type="ANDROID_MLKIT_TEXT"`, and returns an `IdentifyJobStatusResponse` immediately.

Text-only jobs are intended for Android ML Kit OCR output. They accept extracted lines plus optional selected catalog number or barcode hints, but they do not persist an uploaded image and do not enter image-only phases such as `upload_received`, `preprocessing_image`, or `extracting_text`. The request contract bounds OCR input to 1-200 lines, 500 characters per line, and 10,000 normalized characters total before service admission runs.

Text-only processing parses the submitted lines into the same `ExtractedIdentifiers` model used by the image OCR pipeline. Selected catalog and barcode hints are folded into those identifiers before the service reuses local candidate lookup, Discogs search planning, and ranking.

### Background processing

`process_job(job_id, image_bytes, filename, content_type)` opens a fresh database session, loads the job, and runs `IdentifyService.identify` with a database-backed progress reporter.

The reporter persists status and message updates at each major identify phase. On success, the service stores the serialized `IdentifyResponse` in `result` and marks the job `completed`.

`process_text_job(job_id, request)` opens a fresh database session and releases the same admission ticket used by image jobs. It skips image preprocessing and OCR, then emits `parsing_identifiers`, `searching_local`, `searching_discogs`, and `ranking_candidates` updates as the reused parser/search path runs.

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

Discogs API access is built from the saved Discogs integration token, not from a
backend `.env` token. `DiscogsIntegrationService` validates the saved token via
Discogs identity, stores it encrypted, and uses the returned username for
collection sync.

`DiscogsApiConfig.from_token` reads:

- `discogs_base_url`
- `discogs_user_agent`
- `discogs_request_timeout_seconds`

Image identify and collection sync require a saved Discogs integration token.
Backend release import by Discogs ID also requires saved credentials. No-token
barcode/manual-search imports fetch the selected release on Android, then submit
the full payload to the backend through the client-provided import path. Missing
saved credentials raise `DiscogsConfigurationError` for token-gated flows.

`DiscogsIntegrationService` exposes:

- `get_status`, which returns sanitized saved-token state, Discogs identity,
  current collection source of truth, and whether backend image identify is enabled.
- `save_access_token`, which validates `/oauth/identity`, encrypts the token,
  and upserts the `provider_integrations` row.
- `delete_access_token`, which clears the stored token, marks the integration
  inactive, and resets collection source of truth to `APP`.
- `get_saved_credentials`, which decrypts the stored token and returns the
  identity-derived username.
- `build_discogs_service`, which creates a `DiscogsService` with an explicit
  `DiscogsClient` built from the saved token.

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

`GET /api/v1/releases/search` exposes token-backed server Discogs release search.
The current Android manual search and barcode processing flows use the Android
`DiscogsApiClient` to search Discogs directly from the device with local
unauthenticated rate limiting. The backend search route remains available for
server-side callers that have a saved Discogs integration token.

The route:

1. Requires at least one search field.
2. Builds `DiscogsService` from saved integration credentials.
3. Calls `DiscogsService.search_releases`.
4. Normalizes Discogs result payloads into compact candidate rows.
5. Returns Discogs IDs only; token-backed clients can call `POST /api/v1/releases/import` after selection to get an internal `release_id`.

Android no-token manual search, barcode search, and collection-add candidate confirmation fetch the selected full Discogs release directly on-device, then call `POST /api/v1/releases/import/client-discogs`.

### Release fetch behavior

`fetch_release(db, discogs_release_id)`:

1. Checks `DiscogsReleaseRepository` for an existing cached payload.
2. Returns fresh cached payloads without calling Discogs.
3. Touches stale cache rows before refresh attempts.
4. Calls Discogs `/releases/{id}` when needed.
5. Upserts the raw payload into `discogs_release_cache`.

The release cache preserves raw Discogs JSON. Mapping into local release fields happens in `release_mapper.py`.

## CollectionSyncService

`CollectionSyncService` powers manual Discogs collection imports and keeps the
authenticated user's local collection membership compatible with that user's
selected source of truth. Release metadata stays shared catalog data.

### Sync flow

1. Resolve the source of truth from `CollectionSettingsRepository` for `user_id`.
2. Fetch the default Discogs collection folder through the user's saved Discogs token.
3. Collapse duplicate Discogs instances to one representative release per
   Discogs release id.
4. Map each representative item with `release_mapper.py`.
5. Upsert release metadata through `ReleasesRepository`.
6. Activate imported releases in `release_collection_memberships` when the source of truth is `DISCOGS`, when the
   shared release row is new, or when an app-owned first import has no prior
   user membership history.
7. In `DISCOGS` mode only, mark the user's missing active local releases as removed.
8. Fetch Discogs folder metadata and persist folder memberships through
   `CollectionFoldersRepository`.

Folder memberships are stored separately from release metadata and include
`user_id`, so different accounts can have different folders for the same shared
release row. Folder filters always query the user's active local collection
membership; removed records remain available to analytics/history but do not
appear in folder-filtered Collection results.

## ReleaseImportService

`ReleaseImportService` powers release import, one-record Discogs refresh, and local release reads.

### Import flow

1. Use an injected `DiscogsService` in tests, or build one from saved integration credentials at runtime.
2. Fetch the raw Discogs release with `DiscogsService.fetch_release`.
3. Map the raw payload to `InternalReleaseData`.
4. Save or update the local release through `ReleasesRepository.save_or_update`.
5. Return `ReleaseImportResult`.

`ReleaseImportResult.status` returns `created` or `updated`, based on whether the repository created a new row.

### Import-to-collection flow

`import_release_to_collection` reuses the token-backed import flow, then calls
`ReleasesRepository.mark_in_collection` for the authenticated user's membership
with no Discogs collection instance id. It activates or reactivates the release,
clears the membership `collection_removed_at`, and updates the membership sync
timestamp. This route is for server-owned Discogs fetches that can use a saved
backend token.

### Client-provided import flow

1. Android fetches the selected Discogs release directly for no-token barcode/manual-search and collection-add flows.
2. Backend accepts the full Discogs payload without creating a Discogs client.
3. Backend maps the payload to `InternalReleaseData`.
4. Backend upserts the raw payload into `discogs_release_cache`.
5. Backend saves or updates the local release and returns `ReleaseImportResult`.

When client-provided import is used from Collection add, Android follows the
import with `reactivateReleaseCollectionMembership` so the saved release appears
in Records Collection and Record Details can log future sessions.

### Refresh flow

`refresh_release` reads an existing local release by internal ID, then imports its Discogs release ID with `force_refresh=True`. This updates mapped release fields and the full Discogs cache for one collection record without making bulk collection sync fetch every full release.

### Read and mapping helpers

- `get_release` reads a local release by database ID.
- `has_full_discogs_info` reports whether a full Discogs payload is cached for the release.
- `get_available_sides` reads cached Discogs track positions and returns ordered side prefixes for session logging.
- `map_discogs_payload` exposes the Discogs-to-internal mapping for tests and route workflows.

## ManualReleaseService

`ManualReleaseService` powers `/api/v1/manual-releases/*`. Manual release data is deliberately user-owned: saved manual submissions live in `manual_releases`, drafts live in `manual_release_drafts`, and neither path writes shared Discogs metadata into `releases`.

### Draft flow

Drafts support list/create/update/delete for the authenticated user. Each account can keep up to 5 drafts. Draft creation serializes the per-user cap check with a PostgreSQL transaction advisory lock so concurrent creates cannot exceed the limit. Draft saves accept partial form data, normalize string/list inputs, enforce type-safe payload shapes, and do not add anything to the user's collection, listening history, or analytics.

### Save flow

Saving a manual release validates the complete form, creates a user-owned `manual_releases` row, and removes the source draft when the request saves from an existing draft. Draft-backed saves read the source draft with `FOR UPDATE` and consume it in the same transaction, so concurrent saves for the same draft cannot create duplicate manual releases. Validation covers required artist/title/label/format/genre data, optional release year bounds, Electronic style requirements, vinyl size/speed/disc count, tracklist limits, supported track credit roles, barcode format, duration bounds, and shared field length limits.

Manual releases remain separate from Discogs-backed releases until a future replacement workflow explicitly maps a user's manual submission to a richer Discogs release.

### Cover upload contract

Cover upload endpoints validate file type, size, and dimensions through `manual_release_policy.py`, with a 500 KB image limit and a 100..1200 px longest-side range. Valid manual release covers are stored on the server under the configured manual release cover storage directory and draft cover metadata is updated with the served image URL.

### Test coverage status

Current service/API/repository tests cover draft CRUD contracts, the 5-draft cap, serialized draft-cap checks, locked draft consumption, form validation, list normalization, cover validation policy, save-from-draft behavior, user ownership scoping, and persistence guards proving that manual release saves preserve collection semantics without creating listening history or analytics records before sessions are logged.

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

`SessionsService` owns listening session creation, editing, and retrieval.

### Create flow

`create_session(db, payload)`:

1. Validates and normalizes input.
2. Confirms the local release exists.
3. Confirms the release is active in the collection.
4. Optionally checks the raw Discogs release payload for valid side labels.
5. Validates optional `session_group_id` through `SessionGroupsService`.
6. Creates a session through `SessionsRepository`.
7. Persists optional selected tracks through `session_tracks`, including track-level Discogs artist snapshots when present. Response mapping enriches older track rows from cached Discogs tracklists when the stored artist snapshot is missing.
8. Returns `CreateSessionResult` with session ID, timestamp, optional session group id, and success status.

### Edit flow

`update_session(db, session_id, fields)`:

1. Loads the existing session.
2. Requires the session to be within 15 minutes of `created_at`.
3. Validates only editable fields: `side`, `track_positions`, `rating`, `mood`, and `notes`.
4. Reuses side validation and mood canonicalization from session creation.
5. Persists the updated session through `SessionsRepository`.

### Validation behavior

The service validates:

- `release_id` must point to a local release.
- The release must be active in the collection.
- `played_at` may be omitted or parsed from ISO datetime text.
- `side` is trimmed and uppercased.
- `mood` and `notes` are trimmed and stored as nullable optional text.
- If Discogs track positions are available, requested side must exist on the release.
- `track_positions` are optional; when provided, each selected track must exist on the selected side in cached full Discogs release data.
- `session_group_id` is optional; when provided, it must point to an active timed session group.
- Custom mood options are stored in `session_moods` through `GET/POST/DELETE /api/v1/sessions/moods` and scoped to the authenticated user; session analytics still reads the selected text from `sessions.mood`.
- Mood names are canonicalized case-insensitively from built-in moods, the authenticated user's active custom mood options, or that user's historical session rows before a session is stored.
- Session edits are allowed only during the backend-controlled 15-minute window after `created_at`.

Errors are typed:

- `SessionValidationError` for malformed input.
- `SessionEditWindowExpiredError` when the edit window has passed.
- `ReleaseNotFoundError` when a release does not exist.
- `ReleaseNotInCollectionError` when a release was removed from active collection membership.
- `SessionNotFoundError` when a session lookup misses.
- `SessionGroupNotFoundError` or `SessionGroupInactiveError` when timed-session membership is invalid.

### Read behavior

- `get_session` returns one session by ID or raises `SessionNotFoundError`.
- `get_session` and `get_sessions_by_release` can be scoped by authenticated `user_id` so one account cannot read another account's listening history.
- Home and release session responses include `can_edit` and `editable_until` so clients can show edit affordances without owning the rule.

## SessionGroupsService

`SessionGroupsService` owns optional timed listening sessions.

### Start flow

`start_session_group(db, title, started_at)`:

1. Loads the current active group.
2. Auto-finishes it first if it has been inactive for 30 minutes.
3. Rejects the request if a non-stale active group remains.
4. Creates a new `session_groups` row with `status = active`.

The one-active-group rule is enforced in this service layer, not by a database uniqueness constraint. That matches the current single-client app flow; add a database-level guard before supporting concurrent multi-client starts.

### Active and finish behavior

- `get_active_session_group` returns the active group or `None` for the current authenticated user.
- `finish_session_group` marks an active group as `completed` and sets `ended_at`.
- `validate_active_session_group` is used during session creation before a child session is linked and filters by owner.
- Inactivity is measured from the latest child session `created_at`; if there are no child sessions, it uses `session_groups.started_at`.
- Auto-expiry sets `ended_at` to `last_activity + 30 minutes`.

Typed errors:

- `SessionGroupAlreadyActiveError` for a start request while an active group is still valid.
- `SessionGroupNotFoundError` when a group id does not exist.
- `SessionGroupInactiveError` when a stopped or auto-expired group is used.
- `SessionGroupValidationError` for invalid title or datetime input.

## AnalyticsService

`AnalyticsService` owns dashboard aggregations used by the Android Analytics screens.

Analytics endpoints read from persisted releases and sessions scoped to the authenticated user:

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
Drilldown pagination is validated at the service boundary: `limit` must be between 1 and the configured max page limit (`max_page_limit`, currently 250), `offset` must be nonnegative, rating must be 1-5, month must be strict `YYYY-MM`, and mood/style labels must be nonblank.

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
