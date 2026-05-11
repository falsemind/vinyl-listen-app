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
/releases
/sessions
/analytics
/system
```

---

# 1. Record Identification

Endpoint used after the user captures a photo.

## POST /identify

Uploads an image and returns candidate releases.

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
Discogs search
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
      "discogs_release_id": "123456",
      "artist": "Pink Floyd",
      "title": "The Dark Side of the Moon",
      "year": 1973,
      "label": "Harvest",
      "catalog_number": "SHVL 804",
      "thumbnail_url": "https://..."
    }
  ]
}
```

Notes:

* Candidates do **not include `release_id` yet** because the record may not exist in the backend database.
* `release_id` will be created once the user confirms a match.

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
      "discogs_release_id": "555123",
      "artist": "Boards of Canada",
      "title": "Music Has The Right To Children",
      "year": 1998,
      "label": "Warp Records",
      "thumbnail_url": "https://..."
    }
  ]
}
```

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
  "moods": ["Calm", "Nostalgic"],
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

The Android app formats `date` into display text such as `Today`, `1d`, `1w`, or `1m`.

---

# 6. Get Record Details

Used by the **Record Detail screen**.

## GET /releases/{release_id}/stats

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
  "sessions": [
    {
      "session_id": "...",
      "side": "A",
      "rating": 5,
      "moods": ["Energetic", "Happy"],
      "notes": "...",
      "played_at": "2026-03-13T14:23:00Z"
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
      "side": "B",
      "rating": 4,
      "moods": ["Calm"],
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

| Parameter | Description       |
| --------- | ----------------- |
| limit     | number of records |

### Response

```json
{
  "records": [
    {
      "release_id": "1",
      "discogs_release_id": "555123",
      "artist": "Boards of Canada",
      "title": "Music Has The Right To Children",
      "plays": 12
    }
  ]
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
