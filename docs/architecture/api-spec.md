---
name: api-spec
description: This document explains Backend API Specification.
---

# Vinyl Listening App — Backend API Specification (MVP)

## Purpose

Define the backend API endpoints, request/response structure, and operational constraints for the MVP of the Vinyl Listening App.

Backend responsibilities:

* Account registration, email verification, sign-in, token refresh, and password reset flows
* Record identification via Discogs API when a saved Discogs integration token is available
* Discogs integration status and token storage
* Listening session logging
* Record metadata retrieval
* Analytics aggregation
* Rate limiting, caching, and request throttling

All endpoints are designed to be consumed by the Android application built with **Kotlin + Jetpack Compose**.

All responses use **JSON with strict schema validation**.

---

# Backend Stack

* Python
* FastAPI
* PostgreSQL
* Discogs API integration

---

# Base API Path

```
/api/v1
```

All endpoints are versioned to support future API evolution.

---

# Data Model Design

To decouple the application from Discogs, the backend uses **two identifiers**.

```json
{
  "release_id": "internal backend ID",
  "discogs_release_id": "Discogs release ID",
  "artist": "...",
  "title": "...",
  "catalog_number": "...",
  "barcode": "...",
  "format": "Vinyl, LP",
  "cover_image_url": "...",
  "sessions": []
}
```

### Identifier Roles

| Field              | Purpose                          |
| ------------------ | -------------------------------- |
| release_id         | Internal database identifier     |
| discogs_release_id | External identifier from Discogs |

This separation allows future integrations with:

* MusicBrainz
* AI record identification
* Internal catalog sources

The Android app should **always use `release_id` when communicating with the backend**.

**Internal Release Priority:** When performing searches or retrieving details using `discogs_release_id`, the backend service will first check if an associated `release_id` (internal ID) has already been created and stored in the local database. This ensures data integrity and optimizes retrieval speed for previously matched records.

---

# API Overview

Main API domains:

```
/identify
/identify/jobs
/releases
/collection
/integrations
/sessions
/analytics
/ai
/auth
/health
```

All application endpoints require bearer authentication unless explicitly public. The public allowlist is:

* `/auth/register`
* `/auth/verify-email`
* `/auth/resend-verification`
* `/auth/login`
* `/auth/refresh`
* `/auth/password-reset/request`
* `/auth/password-reset/confirm`
* `/health` and `/health/runtime`

Protected endpoints require:

```http
Authorization: Bearer ACCESS_TOKEN
```

Auth failures use the standard error shape:

```json
{
  "error": {
    "code": "auth_required",
    "message": "Authentication is required."
  }
}
```

---

# 1. Auth And Account Access

Auth endpoints live under `/api/v1/auth`. Local development uses the local email delivery backend by default, so verification and reset codes are written to the configured JSONL outbox instead of being sent through Mailgun.

## POST /auth/register

Creates an unverified account and sends a verification code through the configured auth email sender.

### Request

```json
{
  "email": "alex@example.com",
  "password": "correct-horse-battery-staple"
}
```

### Response

```
201 Created
```

```json
{
  "user_id": "6e3e1c1c-b5c5-4c0e-bbc8-2b5bdb5c4e21",
  "email": "alex@example.com",
  "verification_expires_at": "2026-06-18T20:15:00Z"
}
```

Duplicate emails return `409 email_already_registered`.

## POST /auth/verify-email

Consumes a single-use verification code and marks the account email as verified.

### Request

```json
{
  "email": "alex@example.com",
  "code": "123456"
}
```

Wrong codes return `400 email_code_invalid`, reused codes return `400 email_code_consumed`, and expired codes return `410 email_code_expired`.

## POST /auth/resend-verification

Sends a new verification code for an unverified account. Rate-limited requests return `429 email_verification_rate_limited`.

## POST /auth/login

Verifies email/password credentials and returns an access token plus refresh token. The account must already be email verified.

### Request

```json
{
  "email": "alex@example.com",
  "password": "correct-horse-battery-staple",
  "device_label": "Pixel"
}
```

### Response

```json
{
  "access_token": "eyJ...",
  "access_expires_at": "2026-06-18T20:15:00Z",
  "refresh_token": "opaque-refresh-token",
  "refresh_expires_at": "2026-07-18T20:00:00Z",
  "token_type": "Bearer",
  "session_id": "0f65cf9d-d1bb-4680-85d8-35d9d20787c5"
}
```

Invalid credentials return `401 invalid_credentials`. Unverified accounts return `403 email_not_verified`.

## POST /auth/refresh

Rotates a valid refresh token and returns a new access/refresh token pair. Reused, expired, revoked, and invalid refresh tokens return structured `401` errors. If the session has been inactive for more than the configured inactivity window, the backend returns `401 inactivity_reauth_required` and the client should ask for the password again.

## POST /auth/logout

Protected endpoint. Revokes the current auth session.

## GET /auth/me

Protected endpoint. Returns the current authenticated account summary.

## POST /auth/password-reset/request

Accepts an email address and sends a reset code when the account exists. Unknown emails still return a generic accepted response.

## POST /auth/password-reset/confirm

Consumes a reset code, updates the password hash, and revokes existing sessions for that account.

---

# 2. Record Identification

Endpoints used after the user captures or uploads a photo.

## POST /identify

Uploads an image and returns candidate releases synchronously.

This endpoint is protected by the identify admission guard. If local identify capacity is full, it returns `429` with error code `identify_capacity_exceeded` and a `Retry-After` header.

### Request

Content type:

```
multipart/form-data
```

Fields:

| Field | Type | Description                   |
| ----- | ---- | ----------------------------- |
| image | file | Photo of label/runout/barcode |

---

### Processing Pipeline

```
OCR extraction
↓
barcode detection
↓
text cleanup
↓
local release search
↓
Discogs search when local matches are not enough
↓
candidate ranking
```

---

### Response

```
200 OK
```

```json
{
  "candidates": [
    {
      "discogs_release_id": 123456,
      "release_id": null,
      "artist": "Pink Floyd",
      "title": "The Dark Side of the Moon",
      "year": 1973,
      "label": "Harvest",
      "catalog_number": "SHVL 804",
      "barcode": null,
      "cover_image_url": "https://...",
      "format": "Vinyl, LP",
      "match_source": "discogs",
      "matched_on": ["catalog_number"],
      "confidence": 0.92
    }
  ]
}
```

Notes:

* Candidates include `release_id` when the candidate already exists in the local database.
* Candidates from Discogs may have `release_id: null`.
* If `release_id` is null, the client imports the selected Discogs release before logging a session.
* Collection add uses the same candidate shape. Android no-token collection add fetches the selected full Discogs release from the device, imports it through `POST /releases/import/client-discogs`, then calls `POST /releases/{release_id}/collection/reactivate` before opening Record Details.

## POST /identify/jobs

Uploads an image, creates an async identify job, and returns the first persisted job status.

This is the preferred Android Processing screen flow because it exposes backend status while OCR, parsing, search, and ranking are running.

### Request

Content type:

```
multipart/form-data
```

Fields:

| Field | Type | Description |
| ----- | ---- | ----------- |
| image | file | Photo of label/runout/barcode |

### Response

```
202 Accepted
```

```json
{
  "job_id": "4a36f17f-caf5-4ef3-8af0-1f55e5408f64",
  "status": "upload_received",
  "message": "Image upload received",
  "created_at": "2026-05-11T20:00:00Z",
  "updated_at": "2026-05-11T20:00:00Z",
  "cancel_requested": false,
  "result": null,
  "error": null
}
```

Upload validation errors use the same structured error format and status codes as `POST /identify`.

If the client already has too many active identify jobs, or local identify capacity is full, the endpoint returns `429` with a `Retry-After` header:

```json
{
  "error": {
    "code": "identify_capacity_exceeded",
    "message": "Identify capacity is full. Please retry later."
  }
}
```

Clients should honor `Retry-After` before applying local exponential backoff.

Before enforcing the active-job limit, the backend expires stale active job rows. Rows that predate the current backend service instance are treated as orphaned restart leftovers and do not keep blocking the same client.

## GET /identify/jobs/{job_id}

Returns the current identify job status, terminal result, or terminal error.

### Response

```
200 OK
```

```json
{
  "job_id": "4a36f17f-caf5-4ef3-8af0-1f55e5408f64",
  "status": "completed",
  "message": "Identify completed",
  "created_at": "2026-05-11T20:00:00Z",
  "updated_at": "2026-05-11T20:00:04Z",
  "cancel_requested": false,
  "result": {
    "candidates": []
  },
  "error": null
}
```

### Status Values

| Status | Description |
| ------ | ----------- |
| `queued` | Reserved for future queued execution. |
| `upload_received` | Upload validation passed and the job was created. |
| `preprocessing_image` | Backend is preparing image variants. |
| `extracting_text` | OCR and barcode extraction are running. |
| `parsing_identifiers` | OCR output is being parsed into identifiers. |
| `searching_local` | Local release candidates are being searched. |
| `searching_discogs` | Discogs candidate search is running. |
| `ranking_candidates` | Candidate ranking is running. |
| `completed` | `result` contains the identify response. |
| `failed` | `error` contains a terminal failure. |
| `expired` | Job is outside the retention window. |
| `canceled` | Client requested cancellation and the backend acknowledged it. |

### Error Payload

```json
{
  "job_id": "4a36f17f-caf5-4ef3-8af0-1f55e5408f64",
  "status": "failed",
  "message": "Candidate search failed. Retry in a moment.",
  "created_at": "2026-05-11T20:00:00Z",
  "updated_at": "2026-05-11T20:00:04Z",
  "cancel_requested": false,
  "result": null,
  "error": {
    "code": "candidate_search_failed",
    "message": "Candidate search failed. Retry in a moment.",
    "failed_step": "search"
  }
}
```

`failed_step` values are `upload`, `extract`, `search`, or `unknown`.

### Job Lookup Errors

| Status | Meaning |
| ------ | ------- |
| `404 Not Found` | No job exists for `job_id`. |
| `410 Gone` | Job exists but has expired. |

## POST /identify/jobs/{job_id}/cancel

Requests cooperative cancellation for an async identify job.

Cancellation is idempotent. If the job is active, the backend records the cancellation request and returns the current job status with `cancel_requested: true`. The response does not report `status: "canceled"` until backend processing acknowledges cancellation at a safe checkpoint.

If the job is already terminal, the endpoint returns the current terminal status without rewriting it. For example, completed jobs remain `completed`, expired jobs remain `expired`, and canceled jobs remain `canceled`.

Operational logs distinguish cancellation requests, duplicate or terminal no-op cancellation attempts, and backend acknowledgment when processing marks the job `canceled`.

Common outcomes:

| Current job state | Response behavior |
| --- | --- |
| Active job | Returns current status with `cancel_requested=true`. |
| Cancellation acknowledged by worker | Returns `status="canceled"` with no `result` or `error`. |
| Completed before cancel | Returns `status="completed"` with the completed `result`. |
| Failed, expired, or already canceled | Returns the existing terminal state. |

Missing jobs return the same `404` shape as `GET /identify/jobs/{job_id}`.

### Response

```json
{
  "job_id": "4a36f17f-caf5-4ef3-8af0-1f55e5408f64",
  "status": "extracting_text",
  "message": "Extracting text from image",
  "created_at": "2026-05-11T20:00:00Z",
  "updated_at": "2026-05-11T20:00:02Z",
  "cancel_requested": true,
  "result": null,
  "error": null
}
```

### Errors

| Status | Meaning |
| ------ | ------- |
| `404 Not Found` | No job exists for `job_id`. |

---

# 3. Manual Release Search

Fallback when automatic identification fails.

Android manual search and on-device barcode search call Discogs directly from
the device with the app's local unauthenticated rate limiter. The backend route
below remains available for token-backed server-side Discogs search, tests, and
future clients that explicitly opt into the saved integration. It requires a
saved Discogs integration token.

## GET /releases/search

### Query Parameters

| Parameter | Required | Description       |
| --------- | -------- | ----------------- |
| artist    | optional | Artist name       |
| title     | optional | Release title     |
| catalog   | optional | Catalog number    |
| barcode   | optional | Barcode           |
| year      | optional | Release year      |
| limit     | optional | Pagination limit  |
| offset    | optional | Pagination offset |

### Example

```
GET /api/v1/releases/search?artist=boards+of+canada&title=music&limit=10&offset=0
```

### Response

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
      "format": "Vinyl, LP",
      "thumbnail_url": "https://..."
    }
  ],
  "limit": 10,
  "offset": 0
}
```

The response contains Discogs results, not local records. Android no-token flows do not use this backend search route; they search and fetch the selected release directly from Discogs, then import with `POST /api/v1/releases/import/client-discogs`.

### Errors

| Status | Meaning |
| ------ | ------- |
| `400 Bad Request` | A saved Discogs access token is required for backend Discogs search. |
| `422 Unprocessable Content` | No search field was provided, or a query parameter failed validation. |
| `502 Bad Gateway` | Discogs returned an error or could not be reached. |

---

# 4. Release Details

Release detail endpoints read and update releases by internal `release_id`. Manual Discogs imports and identify flow matches create or update the local release row first, then Android navigates with the internal ID.

Collection sync imports only Discogs `basic_information` for each item. When Record Details opens a Discogs-backed release that still has basic metadata, Android fetches the full release payload directly from Discogs without a saved backend token and imports it through `POST /releases/import/client-discogs`. The **Sync release** action uses the same no-token path after user confirmation and overwrites local release metadata from the latest Discogs payload.

## POST /releases/import

Imports a Discogs release into the local database by Discogs release ID. This is a token-backed backend flow used after backend identify/OCR candidates or other server-owned Discogs flows.

Requires a saved Discogs integration token. The backend must not use this endpoint to perform unauthenticated Discogs fetches for no-token users.

### Request

```json
{
  "discogs_release_id": 555123,
  "force_refresh": false
}
```

### Response

```json
{
  "release_id": "internal_id",
  "discogs_release_id": 555123,
  "status": "created"
}
```

`status` is `created` or `updated`.

## POST /releases/import-to-collection

Imports a full Discogs release through the backend's saved Discogs integration token and marks the saved release active in the app collection. This is a token-backed server-owned flow for callers that can use backend Discogs credentials.

Android collection add does not require a saved backend Discogs token. In no-token collection-add mode, Android fetches the full Discogs release payload on-device, calls `POST /releases/import/client-discogs`, then calls `POST /releases/{release_id}/collection/reactivate`.

### Request

```json
{
  "discogs_release_id": 555123,
  "force_refresh": false
}
```

### Response

Same response shape as `POST /releases/import`.

### Errors

| Status | Meaning |
| ------ | ------- |
| `400 Bad Request` | A saved Discogs access token is required. |
| `404 Not Found` | Discogs returned 404 for the requested release. |
| `422 Unprocessable Content` | The Discogs payload cannot be mapped into local release metadata. |
| `502 Bad Gateway` | Discogs returned a non-404 client error. |

## POST /releases/import/client-discogs

Imports a Discogs release from a full Discogs payload already fetched by Android.

Use this endpoint for no-token barcode/manual-search imports, no-token collection-add imports, Record Details automatic full-release imports, and confirmed **Sync release** actions. Android owns the unauthenticated Discogs request and local rate limiting, then sends the selected release payload to the backend for validation, mapping, caching, and persistence. Collection add then activates membership through `POST /releases/{release_id}/collection/reactivate`.

### Request

```json
{
  "discogs_release": {
    "id": 555123,
    "title": "Music Has The Right To Children",
    "artists_sort": "Boards of Canada"
  }
}
```

### Response

Same response shape as `POST /releases/import`.

### Errors

| Status | Meaning |
| ------ | ------- |
| `422 Unprocessable Content` | The payload is missing required Discogs release fields or fails request validation. |

## GET /releases/{release_id}

Returns stored release metadata for an internal release ID.

### Response

```json
{
  "id": "internal_id",
  "discogs_release_id": 555123,
  "artist": "Boards of Canada",
  "title": "Music Has The Right To Children",
  "year": 1998,
  "format": "Vinyl, LP",
  "label": "Warp Records",
  "catalog_number": "WARPLP55",
  "barcode": "5021603065515",
  "genres": ["Electronic"],
  "styles": ["IDM"],
  "thumbnail_url": "https://...",
  "cover_image_url": "https://...",
  "in_collection": true,
  "collection_added_at": "2021-10-05T19:32:40Z",
  "collection_removed_at": null,
  "last_discogs_sync_at": "2026-06-04T20:15:00Z",
  "discogs_instance_id": 123456,
  "is_favorite": false,
  "has_full_discogs_info": true,
  "available_sides": ["A", "B"],
  "available_side_options": [
    {
      "value": "A",
      "label": "Side A",
      "side": "A",
      "disc_number": null
    }
  ],
  "tracklist": [
    {
      "position": "X2",
      "title": "S.O.U.R",
      "duration": null
    }
  ],
  "discogs_artists": [
    {
      "name": "Boards of Canada",
      "discogs_artist_id": 194
    }
  ],
  "created_at": "2026-04-19T00:00:00Z",
  "updated_at": "2026-06-06T12:00:00Z"
}
```

`has_full_discogs_info` is `true` when the backend has a cached full Discogs release payload for this release. Android uses `false` Discogs-backed records to auto-import full release data on open, while **Sync release** stays available for confirmed manual refreshes.

`available_sides`, `available_side_options`, and `tracklist` are derived from the cached Discogs tracklist. They are empty until full Discogs release data is cached. `tracklist` contains Discogs track rows only; headings and other non-track rows are omitted. `duration` may be `null`.

`discogs_artists` is derived from the cached full Discogs release artist list and includes only artists with Discogs artist IDs. Android uses it to link to artist discography pages.

## PATCH /releases/{release_id}/favorite

Sets the local favorite flag for a release and returns the same response shape as `GET /releases/{release_id}`.

### Request

```json
{
  "is_favorite": true
}
```

### Errors

| Status | Meaning |
| --- | --- |
| `404 Not Found` | No local release exists for `release_id`. |

## POST /releases/{release_id}/refresh

Fetches the full Discogs release payload for an existing local release, saves the mapped release fields, updates the Discogs release cache, and returns the same response shape as `GET /releases/{release_id}`.

Android uses this endpoint from Record Details to hydrate one collection import on demand instead of fetching full Discogs data during bulk collection sync.

### Errors

| Status | Meaning |
| --- | --- |
| `404 Not Found` | No local release exists for `release_id`, or Discogs returned 404 for the mapped Discogs release ID. |
| `422 Unprocessable Content` | The Discogs payload cannot be mapped into local release metadata. |
| `502 Bad Gateway` | Discogs returned a non-404 client error. |

## POST /releases/{release_id}/collection/deactivate

Marks a release as removed from the active collection without deleting the release row, sessions, analytics inputs, or cached Discogs metadata. Returns the same response shape as `GET /releases/{release_id}` with `in_collection: false` and `collection_removed_at` set.

### Errors

| Status | Meaning |
| --- | --- |
| `404 Not Found` | No local release exists for `release_id`. |

## POST /releases/{release_id}/collection/reactivate

Restores an existing release to the active collection without creating a duplicate. Returns the same response shape as `GET /releases/{release_id}` with `in_collection: true`.

### Errors

| Status | Meaning |
| --- | --- |
| `404 Not Found` | No local release exists for `release_id`. |

---

# 5. Collection Management

Endpoints used by the Records Collection screen to load the authenticated user's collection records, start manual Discogs metadata sync, and manage that user's collection source of truth. The default source of truth is the app database. In app-owned mode, Discogs sync can enrich shared release metadata but must not remove, deactivate, or re-add the user's collection membership. Removed records stay in the local database so historical listening sessions and analytics remain available.

## GET /collection/settings

Returns the current collection source-of-truth setting. If no settings row exists yet, the backend creates the default `APP` setting.

### Response

```json
{
  "source_of_truth": "APP"
}
```

Allowed values are `APP` and `DISCOGS`.

## PUT /collection/settings

Updates the collection source-of-truth setting. Changing to `DISCOGS` requires
a saved active Discogs access token because that mode makes Discogs eligible to
drive collection membership.

### Request

```json
{
  "source_of_truth": "DISCOGS"
}
```

### Response

Same response shape as `GET /collection/settings`.

### Errors

| Status | Code | Meaning |
| ------ | ---- | ------- |
| `400 Bad Request` | `discogs_token_required` | `DISCOGS` source of truth was requested before a Discogs access token was saved. |

## POST /collection/sync

Starts a manual background collection sync job for the authenticated user and returns immediately. Requires
that user's saved Discogs integration token. The backend uses the username returned by
Discogs identity validation, not a username from backend configuration.

Sync behavior depends on `source_of_truth`:

| Source | Behavior |
| --- | --- |
| `APP` | Preserve the user's local `in_collection` membership. Missing or empty Discogs collection responses do not remove, deactivate, or re-add records. |
| `DISCOGS` | Treat Discogs as the collection source of truth. Releases missing from the Discogs collection can be marked inactive locally while metadata, sessions, analytics, and cached payloads remain stored. |

### Response

```json
{
  "job_id": "4a36f17f-caf5-4ef3-8af0-1f55e5408f64",
  "status": "queued",
  "message": "Collection sync queued",
  "step": "queued",
  "added_count": 0,
  "updated_count": 0,
  "removed_count": 0,
  "started_at": "2026-06-04T20:15:00Z",
  "completed_at": null,
  "error": null
}
```

Returns `202 Accepted`.

## GET /collection/sync/active

Returns the authenticated user's most recent queued or running collection sync job so Android can reattach to an import after navigation or screen recreation.

Queued or running jobs left behind by a previous backend process are marked `expired` and are not returned as active.

Returns `204 No Content` when no collection sync is active.

## GET /collection/sync/{job_id}

Returns progress for one of the authenticated user's collection sync jobs. Android polls this endpoint while showing collection import status.

Status values are `queued`, `running`, `succeeded`, `failed`, and `expired`. `expired` means a queued or running job was orphaned by a backend restart or exceeded its lifetime.

### Response

```json
{
  "job_id": "4a36f17f-caf5-4ef3-8af0-1f55e5408f64",
  "status": "running",
  "message": "Importing collection data",
  "step": "importing",
  "added_count": 12,
  "updated_count": 4,
  "removed_count": 1,
  "started_at": "2026-06-04T20:15:00Z",
  "completed_at": null,
  "error": null
}
```

Terminal statuses are `succeeded` and `failed`. Missing jobs return `404` with `collection_sync_job_not_found`.

## GET /collection/releases

Returns the authenticated user's active collection records ordered by Discogs collection add date, newest first. Release metadata is shared catalog data; `in_collection`, `collection_added_at`, and `is_favorite` come from that user's collection membership row.

### Query Parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `limit` | integer | Page size. Android loads `25` by default and supports custom page sizes up to the configured max page limit, currently `250`. |
| `offset` | integer | Number of active collection records to skip. |
| `artist` | string | Optional artist-name filter, 1..255 characters. Matches the release artist field and cached Discogs artist data so multi-artist releases can be shown from Record Details. |
| `label` | string | Optional label-name filter, 1..255 characters. Matches the release label field and cached Discogs release data so multi-label releases can be shown from Record Details. |
| `favorite` | boolean | Optional flag. When `true`, returns only records marked as the user's personal favorites. |
| `folder_id` | integer | Optional Discogs collection folder id. When present, returns the user's active local collection records that were imported in that Discogs folder. `total` is the active local count for the folder, not the raw Discogs folder count. |

### Response

```json
{
  "items": [
    {
      "id": "internal_id",
      "discogs_release_id": 11646493,
      "title": "Ruff Out Deh",
      "artist": "Babe Roots, Kojo Neatness",
      "year": 2018,
      "format": "Vinyl, 7\", 45 RPM",
      "label": "4Weed Records",
      "catalog_number": "4WDV009",
      "styles": ["Dub", "Dub Techno"],
      "thumb_url": "https://...",
      "collection_added_at": "2021-10-05T19:32:40Z",
      "in_collection": true,
      "is_favorite": true
    }
  ],
  "limit": 25,
  "offset": 0,
  "total": 41,
  "has_more": true,
  "has_favorites": true
}
```

---

## GET /collection/folders

Returns the authenticated user's persisted Discogs collection folders for the Collection action menu.
When Discogs credentials are missing or inactive, the endpoint returns a safe
not-configured response so Android can hide folder controls without surfacing an
error. Default-only Discogs collections return `has_extra_folders=false`; Android
hides the folders action unless at least one non-default folder exists.

### Response

```json
{
  "discogs_configured": true,
  "folders": [
    {
      "id": 0,
      "name": "All",
      "count": 120,
      "is_default": true
    },
    {
      "id": 123,
      "name": "Shelf A",
      "count": 42,
      "is_default": false
    }
  ],
  "has_extra_folders": true
}
```

Folder rows are filters for the current app collection only. They do not change
the collection source of truth and do not persist a folder-specific sync scope.
Android shows up to 10 folders in the Collection action menu. If more folders
exist, the menu shows a `View all folders` row that opens a full folder list.

---

## GET /collection/search

Searches records already present in the active internal collection. This powers the Collection screen manual search and does not call Discogs or import external releases.

Artist search matches the local `artist` field and, when a full release payload is cached, the raw Discogs JSON. That lets hydrated records match track-level or remix artist metadata without fetching every collection item during bulk sync.

### Query Parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `artist` | string | Optional artist text. |
| `title` | string | Optional title text. |
| `catalog` | string | Optional catalog number text. |
| `barcode` | string | Optional barcode text. |
| `year` | integer | Optional release year. |
| `limit` | integer | Page size. Defaults to `10`; capped by the configured max page limit. |
| `offset` | integer | Number of matching collection records to skip. |

### Response

Same response shape as `GET /releases/search`, with `release_id` populated for direct internal navigation. The response also includes `has_more`, a boolean pagination hint computed from one extra internal result so clients can show or hide "Show More" accurately.

---

# 6. Integrations

Endpoints used by Settings to manage optional provider integrations. Discogs
integration state is scoped to the authenticated user; legacy rows may remain
unowned only until local data is reset or a future migration assigns ownership.

## GET /integrations/discogs

Returns sanitized Discogs integration state. The raw access token is never
returned.

### Response

```json
{
  "provider": "DISCOGS",
  "access_token_saved": true,
  "external_user_id": "12345",
  "external_username": "discogs_user",
  "source_of_truth": "APP",
  "backend_identify_enabled": true
}
```

`backend_identify_enabled` is `true` only when a valid active token is saved.
Android uses this flag to enable or disable backend image identification.

## PUT /integrations/discogs/token

Validates and saves a Discogs personal access token. Validation calls Discogs
`/oauth/identity`, then stores the token encrypted and stores the returned
Discogs user id and username.

### Request

```json
{
  "access_token": "discogs_personal_access_token"
}
```

### Response

Same response shape as `GET /integrations/discogs`.

### Errors

| Status | Code | Meaning |
| ------ | ---- | ------- |
| `400 Bad Request` | `discogs_token_invalid` | Discogs identity validation failed or the identity response was incomplete. |
| `500 Internal Server Error` | `discogs_token_storage_not_configured` | `DISCOGS_TOKEN_ENCRYPTION_KEY` is missing or invalid. |

## DELETE /integrations/discogs/token

Deletes the saved Discogs personal access token. This disables token-backed
Discogs features and resets collection source of truth to `APP`, because
`DISCOGS` source of truth requires active saved credentials.

### Response

Same response shape as `GET /integrations/discogs`.

---

# 7. Create Listening Session

Logs a listening session.

## POST /sessions

### Request

```json
{
  "release_id": "internal_id",
  "session_group_id": "optional_timed_session_id",
  "side": "A",
  "track_positions": ["A1", "A2"],
  "rating": 1,
  "mood": "Calm",
  "notes": "Amazing pressing, deep bass.",
  "played_at": "ISO8601 datetime"
}
```

### Response

```
201 Created
```

```json
{
  "session_id": "8b38e7a2",
  "timestamp": "2026-03-14T19:21:00Z",
  "session_group_id": "optional_timed_session_id",
  "status": "success"
}
```

---

### Validation Rules

```
rating must be 1–5
session_group_id optional; when present, it must reference an active timed session group
release must still be active in the collection
side must exist for the release when Discogs side metadata is known
track_positions optional; when present, each track must exist on the selected side in cached full Discogs tracklist data
notes optional
played_at required
```

Inactive collection releases return `400 Bad Request` with `release_not_in_collection`.

---

## PATCH /sessions/{session_id}

Edits a logged session during the server-enforced 15-minute edit window after `created_at`.

Editable fields:

```json
{
  "side": "B",
  "track_positions": ["B1"],
  "rating": 4,
  "mood": "Focused",
  "notes": "Updated after replaying the second side."
}
```

All fields are optional, but at least one field must be present. Send `null` to clear an optional field.

### Response

```json
{
  "id": "session-123",
  "release_id": "release-123",
  "session_group_id": "optional_timed_session_id",
  "rating": 4,
  "mood": "Focused",
  "notes": "Updated after replaying the second side.",
  "played_at": "2026-03-14T19:21:00Z",
  "vinyl_side": "B",
  "tracks": [
    {
      "position": "B1",
      "artist": "Pixl & Tim Reaper",
      "title": "Flip Tune",
      "duration": null,
      "sequence": 3
    }
  ],
  "created_at": "2026-04-19T08:30:00Z",
  "can_edit": true,
  "editable_until": "2026-04-19T08:45:00Z"
}
```

Expired edit windows return `403` with `session_edit_window_expired`.

---

# 8. Timed Session Groups

Used by Android to start an optional timed listening session. Individual record plays are still stored as normal `sessions` rows. When auto-add is enabled, the app passes the active group id as `session_group_id` while logging each record.

The backend auto-finishes an active timed session after 30 minutes without newly logged records. Inactivity is based on the latest grouped session `created_at`, falling back to the group `started_at` when no records were logged.

## POST /sessions/groups

Starts a timed session group. Only one group can be active at a time. The current backend enforces this in service logic; add a database-level uniqueness guard before supporting concurrent multi-client starts.

### Request

```json
{
  "title": "Late night stack",
  "started_at": "2026-04-19T08:00:00Z",
  "style_focus": "mixed",
  "mood_direction": "steady_mood",
  "session_type": "casual_listening",
  "notes": "Starting with new arrivals."
}
```

All fields are optional. `title` is trimmed and limited to 100 characters. `started_at` defaults to server time. `notes` is trimmed and limited to 500 characters.

Metadata defaults:

- `style_focus`: `mixed`
- `mood_direction`: `steady_mood`
- `session_type`: `casual_listening`

Allowed values:

- `style_focus`: `one_style`, `mixed`, `random`
- `mood_direction`: `steady_mood`, `mood_switch`, `energy_build`, `cool_down`
- `session_type`: `dj_set`, `casual_listening`, `rediscovery`, `testing_records`, `background`

### Response

```
201 Created
```

```json
{
  "id": "group-123",
  "title": "Late night stack",
  "status": "active",
  "style_focus": "mixed",
  "mood_direction": "steady_mood",
  "session_type": "casual_listening",
  "notes": null,
  "started_at": "2026-04-19T08:00:00Z",
  "ended_at": null,
  "created_at": "2026-04-19T08:00:00Z",
  "updated_at": "2026-04-19T08:00:00Z",
  "can_edit": true,
  "editable_until": null
}
```

An existing active group returns `409 Conflict` with `session_group_active`.

## GET /sessions/groups/active

Returns the active timed session group, or `null` when none is active. This endpoint may auto-finish a stale group before returning.

```json
{
  "session_group": {
    "id": "group-123",
    "title": "Late night stack",
    "status": "active",
    "style_focus": "mixed",
    "mood_direction": "steady_mood",
    "session_type": "casual_listening",
    "notes": null,
    "started_at": "2026-04-19T08:00:00Z",
    "ended_at": null,
    "created_at": "2026-04-19T08:00:00Z",
    "updated_at": "2026-04-19T08:00:00Z",
    "can_edit": true,
    "editable_until": null
  }
}
```

## GET /sessions/groups/{session_group_id}

Returns one timed session group by id.

Missing groups return `404` with `session_group_not_found`.

## PATCH /sessions/groups/{session_group_id}

Edits timed session metadata while the group is active or for 15 minutes after it stops.

### Request

```json
{
  "style_focus": "one_style",
  "mood_direction": "mood_switch",
  "session_type": "rediscovery",
  "notes": "Ended with a few forgotten shelves."
}
```

All fields are optional. `notes` is trimmed, limited to 500 characters, and can be cleared with `null`.

Expired edit windows return `403` with `session_group_edit_window_expired`. Invalid metadata returns `422` with the matching `invalid_*` code.

## PATCH /sessions/groups/{session_group_id}/finish

Stops an active timed session group. `ended_at` is optional and defaults to server time. Optional metadata and notes can be saved at the same time.

### Request

```json
{
  "ended_at": "2026-04-19T09:00:00Z",
  "style_focus": "one_style",
  "mood_direction": "mood_switch",
  "session_type": "rediscovery",
  "notes": "Ended with a few forgotten shelves."
}
```

### Response

```json
{
  "id": "group-123",
  "title": "Late night stack",
  "status": "completed",
  "style_focus": "one_style",
  "mood_direction": "mood_switch",
  "session_type": "rediscovery",
  "notes": "Ended with a few forgotten shelves.",
  "started_at": "2026-04-19T08:00:00Z",
  "ended_at": "2026-04-19T09:00:00Z",
  "created_at": "2026-04-19T08:00:00Z",
  "updated_at": "2026-04-19T09:00:00Z",
  "can_edit": true,
  "editable_until": "2026-04-19T09:15:00Z"
}
```

Inactive groups return `409` with `session_group_inactive`. `ended_at` before `started_at` returns `422` with `invalid_ended_at`.

---

# 9. Session Moods

Used by the **Log Session screen** to load, create, and delete custom mood chips. Saved moods live in `session_moods`; logged sessions still store the selected mood text on `sessions.mood` so analytics can count historical usage.

## GET /sessions/moods

Returns custom mood options.

```json
{
  "moods": [
    {
      "name": "Late Night",
      "is_custom": true
    }
  ]
}
```

## POST /sessions/moods

Creates a custom mood option. Names are compared case-insensitively.

### Request

```json
{
  "name": "Late Night"
}
```

### Response

```
201 Created
```

```json
{
  "mood": {
    "name": "Late Night",
    "is_custom": true
  }
}
```

Validation rules:

```
name must be 3-20 characters
name may contain only letters, numbers, and spaces
name must not match a built-in mood
name must not match an existing custom mood
```

Duplicate names return `409 Conflict` with `duplicate_mood`.

If a deleted custom mood still exists in historical session rows, the backend reuses the historical casing when the option is created again.

## DELETE /sessions/moods/{mood_name}

Deletes a custom mood option. Existing listening sessions keep their saved `mood` value for analytics history.

Response:

```
204 No Content
```

---

# 10. Home Summary

Used by the **Home screen** to show real listening data after sessions are logged.

## GET /sessions/summary

### Query Parameters

| Parameter | Description | Default |
| --------- | ----------- | ------- |
| recent_limit | Maximum recent sessions to return. Must be between 1 and the configured max page limit, currently `250`. | 5 |
| top_limit | Maximum top records to return. Must be between 1 and the configured max page limit, currently `250`. | 3 |

### Response

```json
{
  "recent_sessions": [
    {
      "session_id": "session-123",
      "release_id": "release-123",
      "session_group_id": "group-123",
      "session_group": {
        "id": "group-123",
        "title": "Late night stack",
        "status": "completed",
        "style_focus": "one_style",
        "mood_direction": "mood_switch",
        "session_type": "rediscovery",
        "notes": "Ended with a few forgotten shelves.",
        "started_at": "2026-05-10T22:45:00Z",
        "ended_at": "2026-05-10T23:45:00Z",
        "can_edit": true,
        "editable_until": "2026-05-11T00:00:00Z"
      },
      "artist": "DJ Harmony & Kid Lib",
      "title": "Future / Fire Feeler / Dressback",
      "year": 2024,
      "label": "Deep Jungle",
      "catalog_number": "DJ-001",
      "thumbnail_url": "https://...",
      "date": "2026-05-10",
      "played_at": "2026-05-10T23:30:00Z",
      "side": "A",
      "tracks": [
        {
          "position": "A1",
          "artist": "DJ Harmony & Kid Lib",
          "title": "Future",
          "duration": "6:34",
          "sequence": 1
        }
      ],
      "rating": 5,
      "mood": "Focused",
      "has_notes": true,
      "created_at": "2026-05-10T23:31:00Z",
      "can_edit": true,
      "editable_until": "2026-05-10T23:46:00Z"
    }
  ],
  "total_sessions": 1,
  "records_this_month": 1,
  "top_records": [
    {
      "release_id": "release-123",
      "artist": "DJ Harmony & Kid Lib",
      "title": "Future / Fire Feeler / Dressback",
      "thumbnail_url": "https://...",
      "plays": 1,
      "average_rating": 5.0
    }
  ]
}
```

The Android app prefers `played_at` for device-timezone-aware labels such as `Today`, `1d`, `1w`, or `1m`. `date` remains as a calendar-date fallback.

On the expanded Recent Sessions screen, Android groups adjacent items with the same non-null `session_group_id` into a timed-session container. Existing sessions with `session_group_id = null` remain individual cards. This grouping is client-side for the currently fetched recent-session list; a future mixed-feed endpoint can preserve groups across page boundaries.

When `session_group_id` is non-null, `session_group` carries the timed-session metadata for metadata chips. Ungrouped rows return `session_group: null`.

---

# 11. Get Record Details

Used by the **Record Detail screen**.

Record metadata comes from `GET /releases/{release_id}`. Listening history comes from `GET /releases/{release_id}/sessions`. Basic collection imports can be hydrated with `POST /releases/{release_id}/refresh`.

## GET /releases/{release_id}

### Response

```json
{
  "id": "internal_id",
  "discogs_release_id": 555123,
  "artist": "...",
  "title": "...",
  "catalog_number": "...",
  "barcode": "...",
  "cover_image_url": "...",
  "in_collection": true,
  "is_favorite": false,
  "has_full_discogs_info": true,
  "available_sides": ["X", "Y"],
  "available_side_options": [
    {
      "value": "1:X",
      "label": "Disc 1 - Side X",
      "side": "X",
      "disc_number": 1
    },
    {
      "value": "2:X",
      "label": "Disc 2 - Side X",
      "side": "X",
      "disc_number": 2
    }
  ],
  "tracklist": [
    {
      "position": "X2",
      "title": "S.O.U.R",
      "duration": null
    }
  ],
  "discogs_artists": [
    {
      "name": "Boards of Canada",
      "discogs_artist_id": 194
    }
  ]
}
```

---

# 12. Session History

Used for listening history.

## GET /releases/{release_id}/sessions

### Query Parameters

| Parameter | Description       |
| --------- | ----------------- |
| limit     | pagination limit  |
| offset    | pagination offset |

### Response

```json
{
  "sessions": [
    {
      "session_id": "abc123",
      "session_group_id": "group-123",
      "date": "2026-03-10",
      "played_at": "2026-03-10T23:30:00Z",
      "side": "B",
      "tracks": [
        {
          "position": "B1",
          "artist": "Pixl & Tim Reaper",
          "title": "Flip Tune",
          "duration": null,
          "sequence": 3
        }
      ],
      "rating": 4,
      "mood": "Calm",
      "notes": "The low end opened up after a clean.",
      "has_notes": true,
      "created_at": "2026-03-10T23:31:00Z",
      "can_edit": false,
      "editable_until": "2026-03-10T23:46:00Z"
    }
  ]
}
```

## GET /releases/{release_id}/flow-insights

Returns deterministic record-flow facts for the Record Details Insights Summary.
Timed session groups are treated as strongest sequence evidence. Standalone
sessions are only linked when neighboring plays are within 1 hour, and
consecutive plays of the same release are collapsed into one record block. By
default, insights use logged plays from the last 3 months.

### Query Parameters

| Parameter | Description                                                  |
| --------- | ------------------------------------------------------------ |
| limit     | max before/after/mood items, 1..10; defaults to 5            |
| period    | history window; one of `3m`, `6m`, `1y`, `all`; defaults `3m` |

The `period` filter is applied before sequence building and release hydration.
`sample_size`, `before`, `after`, and `mood_transitions` describe only the
selected window. Use `all` only when the caller explicitly requests full
history.

### Response

```json
{
  "release_id": "release-123",
  "before": [
    {
      "release_id": "release-before",
      "artist": "Aphex Twin",
      "title": "Selected Ambient Works 85-92",
      "year": 1992,
      "thumbnail_url": null,
      "cover_image_url": "https://img.discogs.com/before.jpg",
      "styles": ["Ambient"],
      "count": 2
    }
  ],
  "after": [
    {
      "release_id": "release-after",
      "artist": "Basic Channel",
      "title": "Quadrant Dub",
      "year": 1994,
      "thumbnail_url": null,
      "cover_image_url": "https://img.discogs.com/after.jpg",
      "styles": ["Dub Techno"],
      "count": 1
    }
  ],
  "mood_transitions": [
    {
      "previous_mood": "Calm",
      "current_mood": "Focused",
      "next_mood": "Energetic",
      "count": 1
    }
  ],
  "sample_size": 2,
  "confidence": "low"
}
```

### Errors

| Status | Code             | Description                                  |
| ------ | ---------------- | -------------------------------------------- |
| 404    | release_not_found | Release does not exist                       |
| 422    | invalid_limit     | `limit` is outside the supported range       |
| 422    | invalid_period    | `period` is not one of `3m`, `6m`, `1y`, `all` |

---

# 13. Analytics

Endpoints used by the **Analytics screen charts**.

Backend calculates metrics using configurable time windows (e.g. last 90 days).
Drilldown endpoints use the same pagination envelope as View All screens.

---

## GET /analytics/plays/monthly

### Response

```json
{
  "data": [
    { "month": "2026-01", "plays": 12 },
    { "month": "2026-02", "plays": 18 }
  ]
}
```

---

## GET /analytics/top-records

### Query Parameters

| Parameter | Description | Default |
| --------- | ----------- | ------- |
| limit | Number of records. Must be between 1 and the configured max page limit, currently `250`. | 10 |

### Response

Records are ordered by play count descending, then average rating descending.

```json
{
  "records": [
    {
      "release_id": "1",
      "discogs_release_id": 555123,
      "artist": "Boards of Canada",
      "title": "Music Has The Right To Children",
      "thumbnail_url": "https://...",
      "plays": 12,
      "average_rating": 4.5,
      "top_track": "Roygbiv",
      "top_mood": "Focused"
    }
  ]
}
```

---

## GET /analytics/rating-distribution

### Response

```json
{
  "ratings": {
    "1": 0,
    "2": 1,
    "3": 2,
    "4": 8,
    "5": 11
  }
}
```

---

## GET /analytics/mood-distribution

Mood names are grouped case-insensitively so historical values such as `LateNight` and `latenight` count under one displayed mood.

### Response

```json
{
  "moods": {
    "Calm": 15,
    "Energetic": 4,
    "Nostalgic": 9
  }
}
```

---

## GET /analytics/style-distribution

Counts Discogs release `styles` across logged listening sessions. Each session contributes one count to every style on its release, so specific styles such as `Dub Techno`, `House`, and `Deep House` can appear separately from broader genres.

Style names are grouped case-insensitively so imported values such as `Dub Techno` and `dub techno` count under one displayed style.

### Response

```json
{
  "styles": {
    "Dub Techno": 12,
    "House": 8,
    "Deep House": 5
  }
}
```

---

## GET /analytics/sessions

Returns listening sessions for a selected month from Plays Over Time.

### Query Parameters

| Parameter | Description | Default |
| --------- | ----------- | ------- |
| month | Required month in strict `YYYY-MM` format. | - |
| limit | Page size. Must be between 1 and the configured max page limit, currently `250`. | 10 |
| offset | Page offset. Must be 0 or greater. | 0 |

### Response

```json
{
  "sessions": [
    {
      "session_id": "session-123",
      "release_id": "release-123",
      "session_group_id": "group-123",
      "session_group": {
        "id": "group-123",
        "title": "Late night stack",
        "status": "completed",
        "style_focus": "one_style",
        "mood_direction": "mood_switch",
        "session_type": "rediscovery",
        "notes": null,
        "started_at": "2026-05-10T22:45:00Z",
        "ended_at": "2026-05-10T23:45:00Z",
        "can_edit": true,
        "editable_until": "2026-05-11T00:00:00Z"
      },
      "artist": "DJ Harmony & Kid Lib",
      "title": "Future / Fire Feeler / Dressback",
      "year": 2024,
      "label": "Deep Jungle",
      "catalog_number": "DJ-001",
      "thumbnail_url": "https://...",
      "date": "2026-05-10",
      "played_at": "2026-05-10T23:30:00Z",
      "side": "A",
      "tracks": [
        {
          "position": "A1",
          "artist": "DJ Harmony & Kid Lib",
          "title": "Future",
          "duration": "6:34",
          "sequence": 1
        }
      ],
      "rating": 5,
      "mood": "Focused",
      "has_notes": true
    }
  ],
  "pagination": {
    "limit": 10,
    "offset": 0,
    "total": 1,
    "has_more": false
  }
}
```

Invalid month or pagination values return the standard structured validation error.

---

## GET /analytics/records/by-rating

Returns records that have sessions with the selected star rating. `count` is the number of matching session ratings for that release.

### Query Parameters

| Parameter | Description | Default |
| --------- | ----------- | ------- |
| rating | Required rating. Must be 1-5. | - |
| limit | Page size. Must be between 1 and the configured max page limit, currently `250`. | 10 |
| offset | Page offset. Must be 0 or greater. | 0 |

### Response

```json
{
  "records": [
    {
      "release_id": "release-123",
      "discogs_release_id": 555123,
      "artist": "Boards of Canada",
      "title": "Music Has The Right To Children",
      "thumbnail_url": "https://...",
      "count": 7
    }
  ],
  "pagination": {
    "limit": 10,
    "offset": 0,
    "total": 1,
    "has_more": false
  }
}
```

---

## GET /analytics/records/by-mood

Returns records that have sessions with the selected mood. Mood matching is case-insensitive.

### Query Parameters

| Parameter | Description | Default |
| --------- | ----------- | ------- |
| mood | Required nonblank mood label. | - |
| limit | Page size. Must be between 1 and the configured max page limit, currently `250`. | 10 |
| offset | Page offset. Must be 0 or greater. | 0 |

### Response

Same response shape as `GET /analytics/records/by-rating`, with `count` representing matching mood sessions.

---

## GET /analytics/records/by-style

Returns records whose imported Discogs `styles` include the selected style. Style matching is case-insensitive and uses the specific style label, not broad genres.

### Query Parameters

| Parameter | Description | Default |
| --------- | ----------- | ------- |
| style | Required nonblank style label. | - |
| limit | Page size. Must be between 1 and the configured max page limit, currently `250`. | 10 |
| offset | Page offset. Must be 0 or greater. | 0 |

### Response

Same response shape as `GET /analytics/records/by-rating`, with `count` representing matching logged sessions for records carrying that style.

---

# 14. AI Insights

Used by the **Insights screen** chat shell.

The backend owns the AI boundary. When AI chat settings are disabled or incomplete, it returns a clear disabled assistant response. When configured, it calls an LM Studio native chat endpoint or an OpenAI-compatible chat completions provider. Chat messages are persisted under the authenticated user so the assistant can receive recent conversation history and the user has clear/export paths.

Before calling the model, the backend runs deterministic read-only insight tools against known collection data. Tool results are passed to the model as bounded context, and the response `used_tools` field lists the tool names used for that turn. Saved session notes are included as high-priority context for recommendation and subjective insight prompts when notes are present.

When the prompt explicitly asks about Spotify, streaming history, listening history, overlap, or correlation, the backend may add Spotify summary tools. These tools use the authenticated user's precomputed rollups and exact collection matches; they do not pass raw Spotify events to the model. Spotify-backed recommendation signals return only releases in that user's collection.

## POST /ai/chat

### Request

```json
{
  "conversation_id": "local-single-thread",
  "message": "What style did I explore most this month?",
  "client_context": {
    "timezone": "America/Los_Angeles"
  }
}
```

`conversation_id` and `client_context` are optional. When `conversation_id` is omitted, the backend uses `local-single-thread`. Conversation ids are scoped by authenticated user, so two accounts can use the same default id without sharing history. Provided `conversation_id` values must be 36 characters or fewer.

`client_context` currently supports only the optional `timezone` field. `timezone` must be 64 characters or fewer, and unknown `client_context` fields are rejected with `422`.

### Response

```json
{
  "conversation_id": "local-single-thread",
  "message": {
    "role": "assistant",
    "content": "AI Insights is ready...",
    "used_tools": [],
    "created_at": null
  },
  "used_tools": []
}
```

Spotify-specific prompts may return tool names such as:

```json
[
  "get_spotify_vinyl_overlap_summary",
  "get_spotify_top_artists_by_period",
  "get_spotify_listening_time_patterns",
  "get_spotify_collection_recommendation_signals"
]
```

### Validation Errors

Blank `message` values return:

```json
{
  "error": {
    "code": "empty_message",
    "message": "message must not be blank."
  }
}
```

Blank provided `conversation_id` values return `empty_conversation_id`.

## GET /ai/chat/history

Returns the authenticated user's persisted conversation for the requested `conversation_id`, or `local-single-thread` when omitted.

```json
{
  "conversation_id": "local-single-thread",
  "messages": [
    {
      "role": "user",
      "content": "What style did I explore most this month?",
      "used_tools": [],
      "created_at": "2026-05-23T12:00:00Z"
    },
    {
      "role": "assistant",
      "content": "Your recent sessions lean toward...",
      "used_tools": ["get_style_distribution"],
      "created_at": "2026-05-23T12:00:01Z"
    }
  ]
}
```

## GET /ai/chat/export

Returns the same user-owned persisted messages plus `exported_at` for privacy/data export.

## DELETE /ai/chat/history

Deletes the authenticated user's persisted conversation for the requested `conversation_id`, or `local-single-thread` when omitted.

```json
{
  "conversation_id": "local-single-thread",
  "deleted_messages": 2
}
```

## POST /ai/spotify/import

Imports local Spotify `end_song` JSON export files from the configured backend import directory into the authenticated user's Spotify history. This endpoint is for local backend testing and experimentation; it does not upload files from Android.

### Request

```json
{
  "file_paths": [
    "Streaming_History_Audio_2019.json",
    "Streaming_History_Audio_2020.json"
  ],
  "batch_size": 1000,
  "refresh_rollups": true
}
```

`file_paths` must contain 1-8 relative file names under `SPOTIFY_IMPORT_DIR`, which defaults to `spotify_import` under the backend working directory. Absolute paths, `..` path escapes, symlinks, and directories are rejected. In Docker, `./spotify_import` is mounted to `/app/backend/spotify_import`.

`batch_size` defaults to `1000` and must be between `1` and `10000`. `refresh_rollups` defaults to `true`.

### Response

```json
{
  "batch_id": "spotify-batch-id",
  "source_files": [
    "Streaming_History_Audio_2019.json",
    "Streaming_History_Audio_2020.json"
  ],
  "total_items": 12000,
  "imported_count": 11800,
  "duplicate_count": 150,
  "skipped_count": 50,
  "error_count": 0,
  "error_summary": []
}
```

The import stores only the filtered song-event fields defined in the AI Insights implementation plan, dedupes repeated events per user, then refreshes that user's Spotify rollups and collection matches when `refresh_rollups` is `true`. Later AI chat requests read those summary tables through deterministic tools instead of scanning raw event history.

---

# 15. Health Endpoints

Used by local development, runtime checks, and clients that need basic backend
readiness.

## GET /health

### Response

```json
{
  "status": "ok"
}
```

## GET /health/runtime

Returns optional runtime dependency status and operation readiness.

### Response

```json
{
  "status": "ok",
  "ready": true,
  "dependencies": [
    {
      "name": "tesseract",
      "available": true,
      "detail": "available",
      "required": true
    }
  ],
  "operations": {
    "rate_limiter": {
      "enabled": true,
      "backend": "redis"
    },
    "identify": {
      "max_concurrency": 2,
      "active_jobs": 0,
      "queued_jobs": null
    }
  }
}
```

---

# Authentication

### MVP Strategy

* Discogs API access uses a **Personal Access Token**
* No OAuth required
* Backend stores the token securely
* Android app never sees the token

### Discogs Request Example

```
Authorization: Discogs token=YOUR_PERSONAL_TOKEN
User-Agent: VinylListeningApp/0.1
```

---

# Rate Limiting & Throttling

Discogs API rate limits must be respected.

### Discogs Limits

```
60 requests per minute per token
```

---

### Backend Protection Strategy

Backend must implement:

```
request throttling
request queueing
duplicate request detection
```

---

### Caching Strategy

To reduce Discogs API calls:

```
cache release metadata
cache search results
cache discogs responses
```

Cache expiration should be configurable.

Possible future improvement:

```
Redis caching layer
```

---

### Client Rate Limiting

Optional protection against excessive requests:

```
limit requests per device
limit rapid search queries
```

This prevents abuse and protects the Discogs quota.

Clients should also handle backend `429` responses gracefully:

* Honor `Retry-After` when present.
* Use exponential backoff with jitter when no valid retry hint is present.
* Avoid automatic retries for uploads and writes unless the backend provides an idempotency contract.
* Use a circuit breaker later if repeated `429`, `502`, `503`, timeout, or offline failures appear in production.

---

# Error Response Format

All API errors follow the same structure.

```json
{
  "error": {
    "code": "release_not_found",
    "message": "Release not found"
  }
}
```

---

# API Versioning Strategy

All endpoints are versioned.

```
/api/v1/...
```

Future breaking changes will use:

```
/api/v2/...
```

---

# Summary of MVP Constraints

```
Single-user MVP
Discogs personal access token (no OAuth)
60 Discogs API requests per minute
Backend caching required
Internal release_id abstraction
```

The API provides capabilities for:

```
record identification
manual search
release metadata retrieval
listening session logging
home dashboard summary
session history
analytics charts
system information
```

This structure keeps the backend **simple, scalable, and ready for future features**.
