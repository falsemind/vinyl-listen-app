---
name: database-schema
description: This document explains Database Schema Specification.
---

# Vinyl Listening App — Database Schema Specification (MVP)

## Purpose

Define the relational database schema used by the backend service.

The schema supports:

- record identification
    
- listening session logging
    
- analytics queries
    
- Discogs metadata caching
- server-backed identify job progress
    

Database engine:

PostgreSQL

The schema is designed to be **simple for MVP**, while allowing future expansion for:

- AI insights
    
- collection management
    
- pricing analytics
    
- recommendation engines
    

---

# Entity Overview

Core entities:

```
releases
sessions
session_moods
discogs_release_cache
identify_jobs
```

Analytics uses the existing `sessions` and `releases` tables. No separate analytics table is required for the MVP.

Relationships:

```
releases
   │
   ├── sessions
   │        │
   │        └── session_moods
   │
   └── discogs_release_cache

identify_jobs
   └── stores short-lived identify progress, result, and error payloads
```

---

# Table: releases

Represents a **vinyl release imported from Discogs** and stored internally for session tracking and analytics.

## Columns

| Column             | Type      | Notes                                    |
| ------------------ | --------- | ---------------------------------------- |
| id                 | UUID      | Primary key                              |
| discogs_release_id | BIGINT    | Discogs release identifier               |
| artist             | TEXT      | Cached artist name                       |
| title              | TEXT      | Album title                              |
| year               | INTEGER   | Release year                             |
| label              | TEXT      | Label name                               |
| catalog_number     | TEXT      | Catalog number                           |
| barcode            | TEXT      | Barcode if available                     |
| genres             | TEXT[]    | Discogs genres (e.g. Electronic, Rock)   |
| styles             | TEXT[]    | Discogs styles (e.g. Techno, Dub Techno) |
| cover_image_url    | TEXT      | Cached Discogs image                     |
| created_at         | TIMESTAMP | Record creation time                     |
| updated_at         | TIMESTAMP | Last metadata update                     |

## Example Stored Record

```json
{
  "id": "6e3e1c1c-b5c5-4c0e-bbc8-2b5bdb5c4e21",
  "discogs_release_id": 123456,
  "artist": "Basic Channel",
  "title": "Phylyps Trak",
  "year": 1993,
  "label": "Basic Channel",
  "catalog_number": "BC 01",
  "genres": ["Electronic"],
  "styles": ["Techno", "Dub Techno"],
  "cover_image_url": "https://discogs.com/image.jpg"
}
```

## Indexes

```sql
PRIMARY KEY (id)

UNIQUE (discogs_release_id)

INDEX (artist)
INDEX (title)

CREATE INDEX idx_releases_genres
ON releases
USING GIN (genres);

CREATE INDEX idx_releases_styles
ON releases
USING GIN (styles);
```

## Why Arrays Work Well Here

Discogs metadata already returns genres and styles as arrays:

```
genres → ["Electronic"]
styles → ["Dub Techno", "Minimal"]
```

Using `TEXT[]` allows:

- direct mapping from API → database
    
- simple analytics queries
    
- efficient filtering
    
- no join tables required
    

Example query:

```sql
SELECT *
FROM releases
WHERE 'Techno' = ANY(styles);
```
---

# Table: sessions

Represents a **listening event**.

Each time a user listens to a record, a session is created.

### Columns

|Column|Type|Notes|
|---|---|---|
|id|UUID|Primary key|
|release_id|UUID|FK → releases.id|
|rating|INTEGER|1–5 rating|
|mood|TEXT|User selected mood|
|notes|TEXT|Optional session notes|
|played_at|TIMESTAMP|Time of listening|
|vinyl_side|TEXT|Optional side (A,B,C,D...)|
|created_at|TIMESTAMP|Session creation time|

### Foreign Keys

```
release_id → releases.id
```

### Indexes

```
PRIMARY KEY (id)

INDEX (release_id)

INDEX (played_at)
```

---

# Table: session_moods

Stores custom mood options shown on the Log Session screen.

Logged sessions keep the selected mood text in `sessions.mood`, so deleting a custom mood option does not rewrite historical session rows or remove analytics history. The service canonicalizes mood names case-insensitively before storing new sessions and analytics groups case variants together.

### Columns

|Column|Type|Notes|
|---|---|---|
|id|UUID|Primary key|
|name|TEXT|Unique mood label|
|is_custom|BOOLEAN|User-defined mood option|
|created_at|TIMESTAMP|Creation time|

### Indexes

```
PRIMARY KEY (id)

UNIQUE (name)
```

---

# Table: discogs_release_cache

Caches Discogs metadata to reduce API calls and avoid rate limits.

### Columns

|Column|Type|Notes|
|---|---|---|
|discogs_release_id|BIGINT|Primary key|
|raw_discogs_json|JSONB|Full Discogs payload|
|cached_at|TIMESTAMP|When cached|
|last_accessed_at|TIMESTAMP|Cache usage tracking|

### Indexes

```
PRIMARY KEY (discogs_release_id)

INDEX (last_accessed_at)
```

---

# Table: identify_jobs

Stores short-lived server-side status for image identification jobs.

This table supports the Android Processing screen. It lets the client poll backend state instead of inferring progress from one long-running HTTP request.

### Columns

|Column|Type|Notes|
|---|---|---|
|id|UUID string|Primary key returned to clients as `job_id`|
|status|TEXT|Current identify status|
|client_key|TEXT|Resolved client identity used for per-client active job admission|
|message|TEXT|Short progress or terminal message|
|filename|TEXT|Original upload filename for diagnostics|
|content_type|TEXT|Upload content type|
|result|JSONB|Serialized identify response when completed|
|error|JSONB|Serialized terminal error when failed|
|created_at|TIMESTAMP|Job creation time|
|updated_at|TIMESTAMP|Last status update time|
|expires_at|TIMESTAMP|Retention cutoff|

### Status Values

```
queued
upload_received
preprocessing_image
extracting_text
parsing_identifiers
searching_local
searching_discogs
ranking_candidates
completed
failed
expired
```

### Indexes

```
PRIMARY KEY (id)

INDEX (status)

INDEX (status, updated_at)

INDEX (client_key, status)

INDEX (expires_at)
```

### Lifecycle

```
upload received
   -> row inserted
   -> background identify task updates status/message
   -> completed result or failed error stored
   -> job expires after retention window
```

Image bytes are not stored in this table.

---

# Derived Analytics (Computed)

Analytics are calculated dynamically from sessions.

Examples:

### Play Count

```
SELECT COUNT(*)
FROM sessions
WHERE release_id = ?
```

---

### Plays in Last 90 Days

```
SELECT COUNT(*)
FROM sessions
WHERE release_id = ?
AND played_at > NOW() - INTERVAL '90 days'
```

---

### Average Rating

```
SELECT AVG(rating)
FROM sessions
WHERE release_id = ?
```

---

### Most Played Records

```
SELECT release_id, COUNT(*) AS play_count
FROM sessions
GROUP BY release_id
ORDER BY play_count DESC
LIMIT 20
```

---

# ID Strategy

All internal entities use UUIDs.

```
releases.id
sessions.id
session_moods.id
identify_jobs.id
```

Discogs identifiers remain separate:

```
discogs_release_id
```

---

# Data Lifecycle

### Release Import

When a Discogs match is confirmed:

```
if release not exists
   → fetch Discogs metadata
   → insert into releases
   → cache full payload
```

---

### Listening Session

```
insert into sessions
```

---

### Analytics Queries

```
computed dynamically
no materialized views required for MVP
```

### Identify Job

```
insert identify_jobs row
background task updates status/message
store completed result or failed error
expire after retention window or stale active timeout
```

---

# Migration Strategy

Use a migration tool such as:

```
Alembic
```

Initial migration should create:

```
releases
sessions
session_moods
discogs_release_cache
identify_jobs
```

---

# Future Schema Extensions

Possible additions after MVP:

```
collections
wishlist
record_prices
marketplace_links
ai_insights
```

Example future tables:

```
record_value_history
collection_tags
session_sentiment_analysis
```

---

# Performance Considerations

Expected workload for MVP:

```
< 10k sessions
< 2k releases
```

PostgreSQL handles this easily without optimization.

Indexes on:

```
release_id
played_at
discogs_release_id
identify_jobs.status
identify_jobs.status + identify_jobs.updated_at
identify_jobs.expires_at
```

will ensure fast analytics queries.

---

# Summary

The MVP schema provides:

- normalized record storage
    
- efficient session logging
    
- Discogs metadata caching
- server-backed identify progress
    
- simple analytics queries
    

while remaining **minimal and easy to maintain**.
