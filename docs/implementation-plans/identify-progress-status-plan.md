# Code Implementation Plan: Server-Backed Identify Progress Status

## Goal

Let the Android Processing screen show identify progress from backend state instead of local placeholder timing.

## Current Behavior

`ProcessingScreen.kt` starts one `apiClient.identifyImage(...)` call and renders:

- Uploading image
- Extracting text
- Searching candidates

Only upload/request failure is observable from the client. The backend identify endpoint is a synchronous `POST /api/v1/identify` that returns final candidates only. It does not stream or expose intermediate OCR/search state, so "Extracting text" and "Searching candidates" are currently inferred UI labels.

## Recommended Backend Shape

Use an asynchronous identify job with polling.

Keep `POST /api/v1/identify` for compatibility, and add job endpoints for progress-aware clients:

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/identify/jobs` | Accept image upload, validate/read bytes, create job, return `202 Accepted`. |
| `GET /api/v1/identify/jobs/{job_id}` | Return current status, timestamps, optional result, optional error. |

Polling is the best MVP fit because it is simple for Android lifecycle handling, works over normal HTTP, avoids streaming upload complexity, and can be tested with existing FastAPI/client patterns. Server-sent events can remain a later upgrade if polling latency becomes a problem.

## Status Contract

Use server-owned statuses:

| Status | Meaning | Android mapping |
| --- | --- | --- |
| `queued` | Job created, waiting to run. | Upload complete, extraction pending. |
| `upload_received` | Backend accepted and validated image bytes. | Upload complete. |
| `preprocessing_image` | Backend is preparing image variants. | Extracting text active. |
| `extracting_text` | OCR/barcode extraction is running. | Extracting text active. |
| `parsing_identifiers` | OCR text is being parsed into identifiers. | Extracting text active. |
| `searching_local` | Backend is checking local releases. | Searching candidates active. |
| `searching_discogs` | Backend is calling Discogs search. | Searching candidates active. |
| `ranking_candidates` | Backend is ranking/deduplicating candidates. | Searching candidates active. |
| `completed` | Final candidates are available. | Navigate to match confirmation or empty state. |
| `failed` | Processing failed with structured error. | Show failed step and recovery actions. |
| `expired` | Job result is no longer available. | Retry from capture/manual search. |

Response shape:

```json
{
  "job_id": "uuid",
  "status": "extracting_text",
  "message": "Extracting text from label image",
  "created_at": "2026-05-12T00:00:00Z",
  "updated_at": "2026-05-12T00:00:02Z",
  "result": null,
  "error": null
}
```

`completed` includes the existing `IdentifyResponse` payload in `result`. `failed` includes `{ "code": "...", "message": "...", "failed_step": "..." }`.

## Backend Phases

### P1 - Job model and API contract

1. Add identify job schemas.
2. Add `IdentifyJobStatus` enum.
3. Add API routes for create/read job.
4. Keep old synchronous identify route unchanged.
5. Define structured error responses for upload validation, missing jobs, expired jobs, and failed jobs.

### P2 - Job storage and worker

1. Add an `identify_jobs` table with status, message, result JSON, error JSON, created/updated timestamps, and expiry.
2. On `POST /identify/jobs`, read and validate upload bytes, create a job row, schedule background processing, and return `202`.
3. If upload validation fails before job creation, return the same structured validation errors as the sync endpoint.
4. If processing fails after job creation, persist `failed` with structured error JSON instead of only logging.
5. Use a TTL cleanup path or scheduled cleanup later.

For first implementation, FastAPI `BackgroundTasks` is enough. If we later run multiple workers or need crash recovery, move execution to a durable queue.

### P3 - Progress reporter inside identify pipeline

1. Introduce `IdentifyProgressReporter`.
2. Update route after upload read: `upload_received`.
3. Update `IdentifyService` before image preprocessing, extraction, local search, Discogs search, ranking, completion, and failure.
4. Keep reporter optional so existing tests and sync endpoint stay simple.
5. Catch known `IdentifyValidationError`, `DiscogsClientError`, OCR/runtime errors, and unexpected exceptions at the job worker boundary.
6. Map backend exceptions to stable job error codes and `failed_step` values.

### P4 - Android polling client

1. Add API models for identify job status/result/error.
2. Add `startIdentifyJob(...)` and `getIdentifyJobStatus(...)` in `VinylApiClient`.
3. Change `ProcessingScreen` to start job, poll until terminal status, and map server statuses to UI cards.
4. Remove timed/local status assumptions after server status is wired.
5. Handle polling transport failures separately from job failures, so Android can show "connection lost" without losing the server job.

## Error Handling Contract

Errors must be explicit because async jobs split request acceptance from processing completion.

### Create Job Errors

These happen before a job exists:

| HTTP status | Code | Meaning |
| --- | --- | --- |
| `413` | `image_too_large` | Upload exceeds backend limit. |
| `415` | `unsupported_image_type` | Content type is not supported. |
| `422` | `invalid_image_upload` | Image bytes cannot be read or are empty. |

The response shape should match existing sync identify errors:

```json
{
  "error": {
    "code": "unsupported_image_type",
    "message": "Unsupported image type."
  }
}
```

### Poll Job Errors

These happen while reading job state:

| HTTP status | Code | Meaning |
| --- | --- | --- |
| `404` | `identify_job_not_found` | Unknown job ID. |
| `410` | `identify_job_expired` | Job existed but result was purged. |

### Processing Job Failures

These are returned by `GET /identify/jobs/{job_id}` with `status="failed"`:

| Code | Failed step | Meaning |
| --- | --- | --- |
| `image_preprocessing_failed` | `extract` | Backend could not prepare image variants. |
| `ocr_failed` | `extract` | OCR backend failed or returned unusable output because of runtime error. |
| `identifier_parse_failed` | `extract` | Parser failed unexpectedly. |
| `discogs_unavailable` | `search` | Discogs request failed or timed out. |
| `candidate_search_failed` | `search` | Candidate lookup/ranking failed unexpectedly. |
| `identify_failed` | `unknown` | Unclassified backend failure. |

Failure payload:

```json
{
  "job_id": "uuid",
  "status": "failed",
  "message": "Discogs search failed",
  "result": null,
  "error": {
    "code": "discogs_unavailable",
    "message": "Discogs is unavailable. Retry in a moment.",
    "failed_step": "search"
  }
}
```

Android should map `failed_step` to the relevant Processing card:

- `upload`: Uploading image
- `extract`: Extracting text
- `search`: Searching candidates
- `unknown`: Current active or generic failure state

## Validation

Backend:

```bash
cd backend
DISCOGS_TOKEN=test .venv/bin/pytest tests/api/test_identify_api.py tests/services/test_identify_service.py
DISCOGS_TOKEN=test .venv/bin/ruff check app tests
```

Android:

```bash
cd android-app
./gradlew :app:ktlintCheck :app:compileDebugKotlin
```

## Risks

- In-memory job state is simpler but not safe across process restarts. Prefer DB-backed status rows for the implementation.
- Polling interval should be modest, around 500-1000 ms, to avoid noisy backend traffic.
- The existing sync endpoint should remain until Android fully migrates.
- Background worker exceptions must never leave jobs stuck in non-terminal states.
