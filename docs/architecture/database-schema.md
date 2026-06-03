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
ai_chat_sessions
ai_chat_messages
spotify_listening_import_batches
spotify_listening_events
spotify_artist_stats
spotify_album_stats
spotify_track_stats
spotify_hourly_stats
spotify_monthly_artist_stats
spotify_skip_stats
spotify_vinyl_artist_matches
spotify_vinyl_release_matches
```

Collection analytics uses the existing `sessions` and `releases` tables. Style analytics reads `releases.styles` and counts those release styles through logged sessions. Spotify analytics uses precomputed summary tables so AI Insights does not scan raw Spotify event history during chat requests.

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

ai_chat_sessions
   └── ai_chat_messages

spotify_listening_import_batches
   └── spotify_listening_events
             └── summary rollups and exact collection-match tables
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
  - style distribution can count specific Discogs styles such as `Dub Techno`, `House`, and `Deep House` without adding a separate style table
    
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
|cancel_requested_at|TIMESTAMP|Set when a client requests cooperative cancellation|
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
canceled
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
   -> completed result, failed error, expired state, or canceled state stored
   -> job expires after retention window
```

Cancellation is cooperative. `POST /api/v1/identify/jobs/{job_id}/cancel` sets `cancel_requested_at` for active jobs. The worker marks the row `canceled` after the next cancellation checkpoint. If the job reaches `completed`, `failed`, or `expired` first, that terminal status is preserved.

Image bytes are not stored in this table.

---

# Table: ai_chat_sessions

Stores persistent AI Insights chat conversations. The MVP uses one local conversation by default: `local-single-thread`.

### Columns

|Column|Type|Notes|
|---|---|---|
|id|UUID/string|Primary key returned as `conversation_id`|
|created_at|TIMESTAMP|Conversation creation time|
|updated_at|TIMESTAMP|Last message time|

### Indexes

```
PRIMARY KEY (id)

INDEX (updated_at)
```

# Table: ai_chat_messages

Stores persisted user and assistant messages for AI Insights.

### Columns

|Column|Type|Notes|
|---|---|---|
|id|UUID string|Primary key|
|conversation_id|UUID/string|Foreign key to `ai_chat_sessions.id`|
|role|TEXT|`user` or `assistant`|
|content|TEXT|Message content|
|used_tools|JSONB|Assistant tool names, empty for user messages|
|client_context|JSONB|Bounded request context such as timezone on user messages|
|created_at|TIMESTAMP|Message creation time|

### Foreign Keys

```
ai_chat_messages.conversation_id -> ai_chat_sessions.id ON DELETE CASCADE
```

### Indexes

```
PRIMARY KEY (id)

INDEX (conversation_id, created_at)

INDEX (conversation_id, role)
```

`DELETE /api/v1/ai/chat/history` deletes both the session and its messages. `GET /api/v1/ai/chat/export` returns the persisted messages for user-controlled export.

---

# Spotify Listening History Tables

Spotify tables support optional AI Insights enrichment from local Spotify `end_song` JSON exports. Import keeps only fields needed for analytics and drops identifiers such as username, IP address, user agent, platform, incognito mode, track URI, and podcast/episode fields.

## Table: spotify_listening_import_batches

Tracks backend-local import attempts.

|Column|Type|Notes|
|---|---|---|
|id|UUID string|Primary key|
|source_paths|JSONB|Validated relative source file names|
|status|TEXT|`running`, `completed`, or failed status|
|total_items|INTEGER|Parsed export rows|
|imported_count|INTEGER|New events inserted|
|duplicate_count|INTEGER|Rows skipped by dedupe key|
|skipped_count|INTEGER|Rows skipped as non-song or invalid starter data|
|error_count|INTEGER|Rows/files with import errors|
|error_summary|JSONB|Bounded error details|
|started_at|TIMESTAMP|Import start time|
|completed_at|TIMESTAMP|Import completion time|

## Table: spotify_listening_events

Stores filtered song events plus derived fields used for rollups.

|Column|Type|Notes|
|---|---|---|
|id|UUID string|Primary key|
|batch_id|UUID string|FK -> `spotify_listening_import_batches.id`|
|event_key|TEXT|Unique dedupe key|
|played_at|TIMESTAMP|Spotify `ts` value|
|played_date|DATE|Derived local date bucket|
|played_hour|INTEGER|Derived local hour bucket|
|played_weekday|INTEGER|Derived weekday bucket|
|played_year_month|TEXT|Derived `YYYY-MM` bucket|
|ms_played|INTEGER|Playback duration|
|conn_country|TEXT|Connection country from export|
|track_name|TEXT|Track name|
|artist_name|TEXT|Album artist name|
|album_name|TEXT|Album name|
|normalized_track_name|TEXT|Normalized track key|
|normalized_artist_name|TEXT|Normalized artist key|
|normalized_album_name|TEXT|Normalized album key|
|reason_start|TEXT|Spotify start reason|
|reason_end|TEXT|Spotify end reason|
|shuffle|BOOLEAN|Shuffle flag|
|skipped|BOOLEAN|Skip flag|
|offline|BOOLEAN|Offline flag|
|offline_timestamp|BIGINT|Spotify offline timestamp|
|is_meaningful_listen|BOOLEAN|Derived signal for non-trivial listens|
|created_at|TIMESTAMP|Row creation time|

### Indexes

```
UNIQUE (event_key)
INDEX (played_at)
INDEX (played_date)
INDEX (played_year_month)
INDEX (normalized_artist_name)
INDEX (normalized_album_name)
INDEX (normalized_track_name)
```

## Spotify Summary Tables

Summary tables are rebuilt from imported events and queried by AI tools.

|Table|Purpose|
|---|---|
|spotify_artist_stats|Top artists by plays, meaningful plays, skips, total listening time, and first/last play time.|
|spotify_album_stats|Top albums by normalized artist+album keys.|
|spotify_track_stats|Top tracks by normalized artist+album+track keys.|
|spotify_hourly_stats|Listening distribution by hour of day.|
|spotify_monthly_artist_stats|Monthly artist signals for period-based questions.|
|spotify_skip_stats|Skip/end-reason counts for lightweight behavior analysis.|

## Spotify Collection Match Tables

Match tables connect Spotify summaries to known local releases. They support collection-only recommendations and explain why a Spotify signal maps to vinyl data.

|Table|Purpose|
|---|---|
|spotify_vinyl_artist_matches|Exact normalized artist overlap, release ids, release count, confidence, match type, and explanation.|
|spotify_vinyl_release_matches|Exact normalized artist+album overlap with release id, Spotify display names, release display names, confidence, match type, and explanation.|

Track-level matching is deferred until local release track metadata is reliable enough to support it.

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
