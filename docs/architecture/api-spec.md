---
name: api-spec
description: This document explains Backend API Specification.
---

# Vinyl Listening App — Backend API Specification (MVP)

## Purpose

Define the backend API endpoints, request/response structure, and operational constraints for the MVP of the Vinyl Listening App.

Backend responsibilities:

* Record identification via Discogs API
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
/sessions
/analytics
/system
```

---

# 1. Record Identification

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

### Error Payload

```json
{
  "job_id": "4a36f17f-caf5-4ef3-8af0-1f55e5408f64",
  "status": "failed",
  "message": "Candidate search failed. Retry in a moment.",
  "created_at": "2026-05-11T20:00:00Z",
  "updated_at": "2026-05-11T20:00:04Z",
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

---

# 2. Manual Release Search

Fallback when automatic identification fails.

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

The response contains Discogs results, not local records. When the user selects a result, the client imports it with `POST /api/v1/releases/import` and navigates with the returned internal `release_id`.

---

# 3. Release Details

Retrieves and compiles complete metadata for a release using the Discogs ID. This endpoint acts as an intelligent retrieval layer, prioritizing data freshness from local caches or performing a fetch if no cached version is available. If an internal `release_id` exists, it will be returned alongside the metadata.

## GET /releases/{discogs_release_id}

### Response

```json
{
  "discogs_release_id": "555123",
  "artist": "Boards of Canada",
  "title": "Music Has The Right To Children",
  "year": 1998,
  "label": "Warp Records",
  "catalog_number": "WARPLP55",
  "genres": ["Electronic"],
  "styles": ["Techno"],
  "sides": ["A", "B", "C", "D"],
  "thumbnail_url": "https://..."
}
```

Sides are derived from the Discogs tracklist.

---

# 4. Create Listening Session

Logs a listening session.

## POST /sessions

### Request

```json
{
  "release_id": "internal_id",
  "side": "A",
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
  "status": "success"
}
```

---

### Validation Rules

```
rating must be 1–5
side must exist for the release when Discogs side metadata is known
notes optional
played_at required
```

---

# 5. Home Summary

Used by the **Home screen** to show real listening data after sessions are logged.

## GET /sessions/summary

### Query Parameters

| Parameter | Description | Default |
| --------- | ----------- | ------- |
| recent_limit | Maximum recent sessions to return. Must be 1-20. | 5 |
| top_limit | Maximum top records to return. Must be 1-20. | 3 |

### Response

```json
{
  "recent_sessions": [
    {
      "session_id": "session-123",
      "release_id": "release-123",
      "artist": "DJ Harmony & Kid Lib",
      "title": "Future / Fire Feeler / Dressback",
      "date": "2026-05-10",
      "played_at": "2026-05-10T23:30:00Z",
      "side": "A",
      "rating": 5,
      "mood": "Focused",
      "has_notes": true
    }
  ],
  "total_sessions": 1,
  "records_this_month": 1,
  "top_records": [
    {
      "release_id": "release-123",
      "artist": "DJ Harmony & Kid Lib",
      "title": "Future / Fire Feeler / Dressback",
      "plays": 1,
      "average_rating": 5.0
    }
  ]
}
```

The Android app prefers `played_at` for device-timezone-aware labels such as `Today`, `1d`, `1w`, or `1m`. `date` remains as a calendar-date fallback.

---

# 6. Get Record Details

Used by the **Record Detail screen**.

Record metadata comes from `GET /releases/{release_id}`. Listening history comes from `GET /releases/{release_id}/sessions`.

## GET /releases/{release_id}

### Response

```json
{
  "release_id": "internal_id",
  "discogs_release_id": "555123",
  "artist": "...",
  "title": "...",
  "catalog_number": "...",
  "barcode": "...",
  "cover_image_url": "...",
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
  ]
}
```

---

# 7. Session History

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
      "date": "2026-03-10",
      "played_at": "2026-03-10T23:30:00Z",
      "side": "B",
      "rating": 4,
      "mood": "Calm",
      "has_notes": true
    }
  ]
}
```

---

# 8. Analytics

Endpoints used by the **Analytics screen charts**.

Backend calculates metrics using configurable time windows (e.g. last 90 days).

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
| limit | Number of records. Must be 1-50. | 10 |

### Response

```json
{
  "records": [
    {
      "release_id": "1",
      "discogs_release_id": "555123",
      "artist": "Boards of Canada",
      "title": "Music Has The Right To Children",
      "plays": 12,
      "average_rating": 4.5
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

# 9. System Endpoint

Used by the **Settings screen**.

## GET /system/info

### Response

```json
{
  "app_version": "0.1.0",
  "build": "dev",
  "api_version": "v1"
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
