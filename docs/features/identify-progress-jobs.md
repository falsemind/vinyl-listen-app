---
name: identify-progress-jobs
description: This document explains the server-backed identify job workflow used to expose backend processing status to the Android Processing screen.
---

# Identify Progress Jobs

## Purpose

Identify progress jobs let the Android client show real backend state while an uploaded image moves through identification.

The original synchronous endpoint remains available at `POST /api/v1/identify`. The job flow wraps the same `IdentifyService` pipeline with persisted status updates so the client can poll progress, show terminal errors, and still receive the normal `IdentifyResponse` when processing completes.

## API Flow

1. The client uploads an image to `POST /api/v1/identify/jobs`.
2. The backend validates the upload and checks identify admission capacity.
3. The backend creates an `identify_jobs` row with the resolved `client_key`.
4. The backend starts the identify pipeline in a background task.
5. The client polls `GET /api/v1/identify/jobs/{job_id}`.
6. The job returns `completed` with `result`, `failed` with `error`, or `expired`.

Upload validation still happens before a job is created. Invalid content type, empty files, or files larger than the configured identify upload limit return the same structured errors as the synchronous endpoint.

When identify capacity is full, `POST /api/v1/identify` and `POST /api/v1/identify/jobs` return `429 identify_capacity_exceeded` with `Retry-After` before starting OCR or search work.

## Job Statuses

| Status | Meaning |
| --- | --- |
| `queued` | Reserved for future queued execution. |
| `upload_received` | Upload validation passed and the job row was created. |
| `preprocessing_image` | The image is being normalized and prepared. |
| `extracting_text` | OCR and barcode extraction are running. |
| `parsing_identifiers` | OCR text is being parsed into barcodes, catalog numbers, artist/title clues, and other evidence. |
| `searching_local` | Local releases are being searched first. |
| `searching_discogs` | External Discogs candidate search is running. |
| `ranking_candidates` | Local or Discogs candidates are being scored and sorted. |
| `completed` | Identification finished and `result` contains candidates. |
| `failed` | Identification failed and `error` explains the terminal failure. |
| `expired` | The job is past its retention window or was stale before completion. |

## Storage

Jobs are stored in the `identify_jobs` table.

Important fields:

- `id`: UUID string returned to the client as `job_id`.
- `status`: current job status.
- `client_key`: resolved client identity used for per-client active job admission.
- `message`: short user-facing progress message.
- `filename` and `content_type`: upload metadata for diagnostics.
- `result`: completed `IdentifyResponse` payload.
- `error`: terminal failure payload with `code`, `message`, and `failed_step`.
- `expires_at`: retention cutoff. Current jobs expire after 24 hours.

Image bytes are not stored in the table. They are held only long enough for the background task to process the upload.

Before creating a new job, the backend expires active rows whose status has not advanced within `identify_stale_active_job_timeout_seconds`. It also expires active rows older than the current `IdentifyJobService` instance startup. This covers backend restarts where the database still has an active job row, but the new process no longer has the in-memory background worker ticket for that job. These stale rows are marked `expired` with `identify_job_stale` so one interrupted upload does not block a client's active-job limit until the full timeout passes.

## Error Handling

`IdentifyJobService` maps backend failures into stable client-facing errors.

| Failure area | `failed_step` | Example codes |
| --- | --- | --- |
| Upload validation | `upload` | `empty_upload`, `unsupported_media_type`, `file_too_large` |
| Image preparation or OCR | `extract` | `image_preprocessing_failed`, `ocr_failed`, `identifier_parse_failed` |
| Candidate lookup or Discogs | `search` | `discogs_unavailable`, `candidate_search_failed` |
| Unknown failure | `unknown` | `identify_failed` |

The Android client can use `failed_step` for diagnostics or future step-level UI. The current Processing screen shows the terminal backend message under the spinner and exposes Retry and Manual Search actions.

## Android Polling Behavior

`VinylApiClient.identifyImage` starts a job, polls job status, and returns candidates once the job is completed.

The Processing screen maps backend statuses into one concise status line under the spinner:

- `queued`, `upload_received`: upload or server receipt.
- `preprocessing_image`, `extracting_text`, `parsing_identifiers`: image preparation and text extraction.
- `searching_local`, `searching_discogs`, `ranking_candidates`: candidate search and ranking.

When the job fails, the client uses the persisted backend message. Offline/local API failures are collapsed to a generic identify-failure message, while backend capacity or validation responses keep their structured API messages.

## Compatibility

`POST /api/v1/identify` still provides the direct synchronous flow. It is useful for tests, scripts, and any client that does not need progress polling.

Both flows use the same identification pipeline, search behavior, ranking, and response schema.

## Test Coverage

Relevant coverage lives in:

- `backend/tests/services/test_identify_job_service.py`
- `backend/tests/api/test_identify_api.py`
- `backend/tests/migrations/test_schema_migration.py`
- `backend/tests/services/test_identify_service.py`
