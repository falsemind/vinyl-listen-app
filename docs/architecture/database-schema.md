---
name: database-schema
description: This document explains Database Schema Specification.
---

# Vinyl Listening App — Database Schema Specification (MVP)

## Purpose

Define the relational database schema used by the backend service.

The schema supports:

- account registration and auth sessions
- record identification
    
- listening session logging
    
- analytics queries
    
- Discogs metadata caching
- encrypted provider integration storage
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
manual_releases
manual_release_drafts
user_accounts
auth_sessions
consumed_refresh_tokens
email_verification_codes
password_reset_codes
user_entitlements
usage_events
sessions
session_groups
session_tracks
session_moods
discogs_release_cache
identify_jobs
collection_settings
provider_integrations
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
   │        └── session_tracks
   │
   ├── session_moods
   │
    └── discogs_release_cache

manual_releases
   └── user-owned manual release metadata outside the shared Discogs catalog

manual_release_drafts
   └── user-owned draft form state for manual submissions

session_groups
   │
   └── sessions

identify_jobs
   └── stores short-lived identify progress, result, and error payloads

collection_sync_jobs
    └── stores short-lived Discogs collection sync progress and count summaries

collection_settings
    └── stores the app-wide collection source of truth

collection_folders
    └── release_collection_folders
        └── maps imported releases to Discogs collection folders

provider_integrations
    └── stores encrypted provider tokens and external account identity

user_accounts
   ├── auth_sessions
   ├── email_verification_codes
   ├── password_reset_codes
   ├── user_entitlements
   ├── usage_events
   ├── manual_releases
   └── manual_release_drafts

auth_sessions
   └── consumed_refresh_tokens

ai_chat_sessions
   └── ai_chat_messages

spotify_listening_import_batches
   └── spotify_listening_events
             └── summary rollups and exact collection-match tables
```

---

# Auth Tables

Auth tables support account bootstrap, email verification, password reset, token-backed sessions, structured auth audit events, account deletion receipts, and future entitlement/usage gates. Some user-owned data has nullable owner columns for legacy compatibility, but active multi-user flows must filter by the authenticated owner.

## Table: user_accounts

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID | Primary key |
| email | VARCHAR | Original email casing for display |
| normalized_email | VARCHAR | Unique lookup key |
| password_hash | TEXT | Argon2id hash |
| password_hash_algorithm | VARCHAR | Current default is `argon2id` |
| password_hash_version | INTEGER | Password hash metadata version |
| password_hash_params | JSONB | Memory/time/parallelism/hash parameters |
| is_active | BOOLEAN | Account active flag |
| email_verified_at | TIMESTAMP | Null until verification succeeds |
| deletion_requested_at | TIMESTAMP | Future account deletion workflow |
| deleted_at | TIMESTAMP | Soft marker for deleted account state |
| created_at | TIMESTAMP | Row creation time |
| updated_at | TIMESTAMP | Last account update time |

Indexes:

```sql
UNIQUE (normalized_email)
INDEX (normalized_email)
```

## Table: auth_sessions

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID | Primary key |
| user_id | UUID | Foreign key to `user_accounts.id` |
| refresh_token_hash | VARCHAR | Unique hash of current refresh token |
| device_label | VARCHAR | Optional client/device label |
| last_activity_at | TIMESTAMP | Used for inactivity re-auth |
| expires_at | TIMESTAMP | Refresh session expiry |
| revoked_at | TIMESTAMP | Null while active |
| revoke_reason | VARCHAR | Logout, password reset, reuse, expiry, or inactivity reason |
| created_at | TIMESTAMP | Row creation time |
| updated_at | TIMESTAMP | Last session update time |

Indexes:

```sql
UNIQUE (refresh_token_hash)
INDEX (user_id)
INDEX (expires_at)
```

## Table: consumed_refresh_tokens

Stores rotated refresh token hashes long enough to detect reuse.

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID | Primary key |
| session_id | UUID | Foreign key to `auth_sessions.id` |
| user_id | UUID | Foreign key to `user_accounts.id` |
| refresh_token_hash | VARCHAR | Unique consumed token hash |
| consumed_at | TIMESTAMP | Rotation time |
| expires_at | TIMESTAMP | Original refresh token expiry |
| created_at | TIMESTAMP | Row creation time |

## Table: auth_audit_events

Structured audit trail for auth-sensitive operations. Rows intentionally avoid storing plaintext emails, passwords, verification/reset codes, provider tokens, or refresh/access tokens.

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID | Primary key |
| user_id | UUID | Nullable foreign key to `user_accounts.id`; set null if the account is deleted |
| session_id | UUID | Optional auth session id context, not a foreign key because sessions can be deleted |
| event_type | VARCHAR | Event key such as `sign_in`, `password_changed`, or `refresh_token_rejected` |
| outcome | VARCHAR | `success` or `failure` |
| occurred_at | TIMESTAMP | Event time |
| event_details | JSONB | Optional non-secret structured metadata |
| created_at | TIMESTAMP | Row creation time |

Indexes include `idx_auth_audit_events_user_time` and `idx_auth_audit_events_event_type_time` for account and event-type investigations.

## Table: email_verification_codes

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID | Primary key |
| user_id | UUID | Foreign key to `user_accounts.id` |
| code_hash | VARCHAR | Hashed verification code |
| sent_to_email | VARCHAR | Recipient email |
| expires_at | TIMESTAMP | Code expiry |
| consumed_at | TIMESTAMP | Null until used |
| resend_count | INTEGER | Number of resend attempts in the flow |
| rate_limited_until | TIMESTAMP | Resend cooldown boundary |
| failed_attempt_count | INTEGER | Wrong-code attempts against this code |
| failed_attempt_limited_until | TIMESTAMP | Per-account wrong-code lockout boundary |
| created_at | TIMESTAMP | Issue time used for latest-code semantics |

## Table: password_reset_codes

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID | Primary key |
| user_id | UUID | Foreign key to `user_accounts.id` |
| code_hash | VARCHAR | Hashed reset code |
| sent_to_email | VARCHAR | Recipient email |
| expires_at | TIMESTAMP | Code expiry |
| consumed_at | TIMESTAMP | Null until used or superseded |
| failed_attempt_count | INTEGER | Wrong-code attempts against this code |
| failed_attempt_limited_until | TIMESTAMP | Per-account wrong-code lockout boundary |
| created_at | TIMESTAMP | Issue time used for latest-code semantics |

## Table: user_entitlements

Foundation table for future plan/capability state.

| Column | Type | Notes |
| --- | --- | --- |
| user_id | UUID | Primary key and foreign key to `user_accounts.id` |
| plan | VARCHAR | Current default is `FREE` |
| status | VARCHAR | Current default is `ACTIVE` |
| valid_until | TIMESTAMP | Optional entitlement expiry |
| created_at | TIMESTAMP | Row creation time |
| updated_at | TIMESTAMP | Last entitlement update time |

## Table: usage_events

Append-only foundation for future feature usage limits, starting with OCR/identify.

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID | Primary key |
| user_id | UUID | Foreign key to `user_accounts.id` |
| capability | VARCHAR | Capability key, such as `ocr_identify` |
| units | INTEGER | Usage units recorded |
| occurred_at | TIMESTAMP | Event time |
| event_metadata | JSONB | Optional structured metadata |
| created_at | TIMESTAMP | Row creation time |

Indexes include `idx_usage_events_user_capability_time` for per-user rolling-window capability counters.

## Table: account_deletion_audits

Minimal receipt table retained after hard account deletion. It intentionally does not store email, provider tokens, collection contents, listening history, prompts, analytics inputs, or other user-owned payloads.

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID | Deletion receipt/request id |
| event_type | VARCHAR | Current value is `account_deleted` |
| requested_at | TIMESTAMP | Password-confirmed deletion request time |
| deleted_at | TIMESTAMP | Hard deletion completion time |
| created_at | TIMESTAMP | Audit row creation time |

---

# Table: releases

Represents shared **vinyl release/catalog metadata imported from Discogs** and stored internally for session tracking and analytics. Per-user collection state lives in `release_collection_memberships`.

## Columns

| Column             | Type      | Notes                                    |
| ------------------ | --------- | ---------------------------------------- |
| id                 | UUID      | Primary key                              |
| discogs_release_id | BIGINT    | Discogs release identifier               |
| artist             | TEXT      | Cached artist name                       |
| title              | TEXT      | Album title                              |
| year               | INTEGER   | Release year                             |
| format             | TEXT      | Display format such as Vinyl, LP         |
| label              | TEXT      | Label name                               |
| catalog_number     | TEXT      | Catalog number                           |
| barcode            | TEXT      | Barcode if available                     |
| genres             | TEXT[]    | Discogs genres (e.g. Electronic, Rock)   |
| styles             | TEXT[]    | Discogs styles (e.g. Techno, Dub Techno) |
| thumbnail_url      | TEXT      | Cached Discogs thumbnail image           |
| cover_image_url    | TEXT      | Cached Discogs image                     |
| in_collection      | BOOLEAN   | Legacy single-user membership column; new collection reads use `release_collection_memberships` |
| collection_added_at | TIMESTAMP | Legacy single-user membership timestamp |
| collection_removed_at | TIMESTAMP | Legacy single-user removal timestamp |
| last_discogs_sync_at | TIMESTAMP | Legacy single-user sync timestamp |
| discogs_instance_id | BIGINT   | Legacy single-user Discogs instance id |
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
  "format": "Vinyl, 12\"",
  "label": "Basic Channel",
  "catalog_number": "BC 01",
  "genres": ["Electronic"],
  "styles": ["Techno", "Dub Techno"],
  "thumbnail_url": "https://discogs.com/thumb.jpg",
  "cover_image_url": "https://discogs.com/image.jpg",
  "in_collection": false,
  "collection_added_at": null,
  "collection_removed_at": null,
  "last_discogs_sync_at": null,
  "discogs_instance_id": null
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

INDEX (in_collection)
INDEX (collection_added_at)
```

---

# Table: manual_releases

Stores committed manual submissions as **user-owned app data**. These rows are separate from the shared Discogs-backed `releases` catalog so one user's manual release never becomes shared metadata for another user.

Manual releases can later be replaced by a user-confirmed Discogs match, but Phase 10A does not store a Discogs id here.

## Columns

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID | Primary key |
| user_id | UUID | Required owner; references `user_accounts.id` with `ON DELETE CASCADE` |
| artist | VARCHAR(200) | Display artist summary |
| title | VARCHAR(200) | Release title |
| label | VARCHAR(200) | Display label summary |
| catalog_number | VARCHAR(80) | Optional matching hint |
| barcode | VARCHAR(14) | Optional normalized barcode |
| format | VARCHAR(20) | `Vinyl`, `CD`, `Tape`, or `Other` |
| genres | TEXT[] | App-defined genre values |
| styles | TEXT[] | App-defined style values |
| artists | JSON | Structured artist list |
| labels | JSON | Structured label list |
| identifiers | JSON | Catalog number, barcode, and future matching helpers |
| format_details | JSON | Vinyl size, speed, disc count, or other format details |
| tracklist | JSON | Structured track rows and optional track credits |
| cover_storage_key | TEXT | Optional backend storage key for cover art |
| cover_image_url | TEXT | Optional cover image URL |
| cover_thumbnail_url | TEXT | Optional cover thumbnail URL |
| cover_content_type | VARCHAR(80) | `image/jpeg`, `image/png`, or `image/webp` |
| cover_size_bytes | INTEGER | Optional cover image size; must be non-negative |
| in_collection | BOOLEAN | Whether the manual release is active in the user's collection |
| collection_added_at | TIMESTAMP | Time the manual release entered the collection |
| collection_removed_at | TIMESTAMP | Time the manual release was removed from the collection |
| is_favorite | BOOLEAN | User-specific favorite flag |
| created_at | TIMESTAMP | Record creation time |
| updated_at | TIMESTAMP | Last metadata update |

## Constraints and Indexes

```sql
FOREIGN KEY (user_id)
REFERENCES user_accounts(id)
ON DELETE CASCADE

CHECK (
  cover_size_bytes IS NULL
  OR cover_size_bytes >= 0
)

INDEX (user_id)
INDEX (user_id, updated_at)
INDEX (user_id, title)
INDEX (in_collection)
```

Access to this table must always filter by authenticated `user_id`. Manual releases are not joined into the shared `releases` catalog unless a later replacement flow explicitly maps user-owned data to a Discogs release.

---

# Table: manual_release_drafts

Stores partial Manual Submissions form state before a release is saved to the user's collection. Drafts are user-owned and do not appear in collection queries, listening history, analytics, or insights.

## Columns

| Column | Type | Notes |
| --- | --- | --- |
| id | UUID | Primary key |
| user_id | UUID | Required owner; references `user_accounts.id` with `ON DELETE CASCADE` |
| form_data | JSON | Partial manual submission form state |
| completion_state | JSON | Optional required-field completion summary for draft cards |
| cover_storage_key | TEXT | Optional backend storage key for draft cover art |
| cover_image_url | TEXT | Optional cover image URL |
| cover_thumbnail_url | TEXT | Optional cover thumbnail URL |
| cover_content_type | VARCHAR(80) | `image/jpeg`, `image/png`, or `image/webp` |
| cover_size_bytes | INTEGER | Optional cover image size; must be non-negative |
| validation_version | INTEGER | Version of the validation rules used to save the draft |
| created_at | TIMESTAMP | Draft creation time |
| updated_at | TIMESTAMP | Last draft update time |

## Constraints and Indexes

```sql
FOREIGN KEY (user_id)
REFERENCES user_accounts(id)
ON DELETE CASCADE

CHECK (
  cover_size_bytes IS NULL
  OR cover_size_bytes >= 0
)

INDEX (user_id)
INDEX (user_id, updated_at)
```

The application enforces a maximum of five drafts per user. The table keeps ownership non-null so draft limits, deletion, and future account cleanup cannot be bypassed by orphan rows.

---

# Table: release_collection_memberships

Stores per-account collection state for shared release metadata. Account deletion cascades these rows without deleting shared Discogs/catalog release rows.

During the multi-user upgrade, legacy single-user collection fields on `releases`
are copied into this table. The migration uses the only active account when
there is exactly one; otherwise `VINYL_LEGACY_OWNER_EMAIL` must identify the
intended owner before upgrade.

## Columns

| Column | Type | Notes |
| --- | --- | --- |
| id | INTEGER | Primary key |
| user_id | UUID | Foreign key to `user_accounts.id` |
| release_id | UUID | Foreign key to `releases.id` |
| in_collection | BOOLEAN | Current active membership for this account |
| collection_added_at | TIMESTAMP | Representative time the account added the release |
| collection_removed_at | TIMESTAMP | Time the account removed the release from active collection |
| last_discogs_sync_at | TIMESTAMP | Last Discogs sync touching this account's membership |
| discogs_instance_id | BIGINT | Representative Discogs collection instance id for this account |
| is_favorite | BOOLEAN | Account-owned favorite flag |
| created_at | TIMESTAMP | Row creation time |
| updated_at | TIMESTAMP | Last membership update |

## Constraints and Indexes

```sql
UNIQUE (user_id, release_id)
FOREIGN KEY (user_id) REFERENCES user_accounts(id) ON DELETE CASCADE
FOREIGN KEY (release_id) REFERENCES releases(id) ON DELETE CASCADE
INDEX (user_id, in_collection)
INDEX (user_id, is_favorite)
INDEX (user_id, collection_added_at)
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

# Table: collection_folders

Stores per-account Discogs collection folder metadata imported during collection sync.
Folder rows power Collection screen filters only; they do not change source of
truth or sync scope.

## Columns

| Column              | Type      | Notes                                      |
| ------------------- | --------- | ------------------------------------------ |
| id                  | INTEGER   | Primary key                                |
| user_id             | UUID      | Foreign key to `user_accounts.id`          |
| discogs_folder_id   | BIGINT    | Stable Discogs folder id unique per account |
| name                | TEXT      | Discogs folder display name                |
| item_count          | INTEGER   | Raw Discogs folder count, if provided      |
| is_default          | BOOLEAN   | `true` for Discogs default folder `0`      |
| last_discogs_sync_at | TIMESTAMP | Last sync that refreshed this folder       |
| created_at          | TIMESTAMP | Row creation time                          |
| updated_at          | TIMESTAMP | Last folder metadata update                |

## Indexes

```sql
UNIQUE (user_id, discogs_folder_id)
FOREIGN KEY (user_id) REFERENCES user_accounts(id) ON DELETE CASCADE
INDEX (user_id, discogs_folder_id)
INDEX (user_id, is_default)
```

---

# Table: release_collection_folders

Join table linking an account's local releases to Discogs collection folders without
duplicating release metadata. Sync replaces memberships for each imported folder.
Collection folder filters always return active local collection records.

## Columns

| Column              | Type      | Notes                                      |
| ------------------- | --------- | ------------------------------------------ |
| id                  | INTEGER   | Primary key                                |
| user_id             | UUID      | Foreign key to `user_accounts.id`          |
| release_id          | UUID      | Foreign key to `releases.id`               |
| collection_folder_id | INTEGER  | Foreign key to `collection_folders.id`     |
| discogs_instance_id | BIGINT    | Discogs collection instance id for that folder membership |
| date_added          | TIMESTAMP | Discogs date the release was added to that folder |
| last_discogs_sync_at | TIMESTAMP | Last sync that refreshed this membership   |
| created_at          | TIMESTAMP | Row creation time                          |
| updated_at          | TIMESTAMP | Last membership update                     |

## Constraints and Indexes

```sql
UNIQUE (user_id, release_id, collection_folder_id)
FOREIGN KEY (user_id) REFERENCES user_accounts(id) ON DELETE CASCADE
FOREIGN KEY (release_id) REFERENCES releases(id) ON DELETE CASCADE
FOREIGN KEY (collection_folder_id) REFERENCES collection_folders(id) ON DELETE CASCADE
INDEX (user_id, release_id)
INDEX (user_id, collection_folder_id)
```

---

# Table: collection_sync_jobs

Stores short-lived per-account progress state for manual Discogs collection sync jobs.

## Columns

| Column          | Type      | Notes                                       |
| --------------- | --------- | ------------------------------------------- |
| id              | UUID      | Primary key                                 |
| user_id         | UUID      | Foreign key to `user_accounts.id`           |
| status          | TEXT      | queued, running, succeeded, failed, or expired |
| step            | TEXT      | fetching, importing, loading, or finalizing |
| message         | TEXT      | User-facing progress message                |
| total_items     | INTEGER   | Discogs items returned by the sync          |
| processed_items | INTEGER   | Unique releases processed                   |
| added_count     | INTEGER   | Newly added releases                        |
| updated_count   | INTEGER   | Existing releases refreshed                 |
| removed_count   | INTEGER   | Releases marked removed from collection when membership mirroring is active |
| error           | JSONB     | Stable error code, message, and failed step |
| created_at      | TIMESTAMP | Job creation time                           |
| updated_at      | TIMESTAMP | Last status update time                     |
| expires_at      | TIMESTAMP | Job retention boundary                      |

## Indexes

```sql
INDEX (status)
INDEX (user_id, status)
INDEX (status, updated_at)
INDEX (expires_at)
```

---

# Table: collection_settings

Stores the collection source-of-truth setting for one account. Legacy rows may have a null owner until backfilled.

## Columns

| Column          | Type      | Notes                                      |
| --------------- | --------- | ------------------------------------------ |
| id              | INTEGER   | Primary key |
| user_id         | VARCHAR   | Nullable owner id; null means legacy unassigned settings |
| source_of_truth | TEXT      | `APP` or `DISCOGS`; defaults to `APP`      |
| created_at      | TIMESTAMP | Row creation time                          |
| updated_at      | TIMESTAMP | Last settings update time                  |

## Constraints

```sql
CHECK (source_of_truth IN ('APP', 'DISCOGS'))
```

`APP` means the authenticated user's local collection membership is authoritative. Discogs sync may enrich shared release metadata but must not remove, deactivate, or re-add that user's releases. `DISCOGS` is persisted for future explicit mirror behavior.

---

# Table: provider_integrations

Stores optional external provider integration state. The current implementation
uses this table for per-user Discogs tokens. Legacy rows may have a null
`user_id` until local data is reset or a future migration assigns ownership.

## Columns

| Column                  | Type      | Notes |
| ----------------------- | --------- | ----- |
| id                      | INTEGER   | Primary key |
| provider                | VARCHAR   | Provider key, currently `DISCOGS` |
| user_id                 | VARCHAR   | Nullable owner id; null means legacy unassigned integration |
| access_token_ciphertext | TEXT      | Encrypted provider access token |
| external_user_id        | VARCHAR   | Provider account id returned by identity validation |
| external_username       | VARCHAR   | Provider username returned by identity validation |
| is_active               | BOOLEAN   | Whether this integration should be used |
| created_at              | TIMESTAMP | Row creation time |
| updated_at              | TIMESTAMP | Last integration update time |

## Indexes

```sql
idx_provider_integrations_provider
idx_provider_integrations_user_id
idx_provider_integrations_provider_user_id
```

Discogs tokens are never stored in plaintext. `DISCOGS_TOKEN_ENCRYPTION_KEY`
must remain stable across backend restarts so saved tokens can be decrypted.
Changing or removing the key makes existing ciphertext unreadable.

---

# Table: sessions

Represents a **listening event**.

Each time a user listens to a record, a session is created.

Sessions can optionally belong to a timed listening session group. Existing and standalone sessions keep `session_group_id = null`.

Current sessions target shared Discogs-backed releases through `sessions.release_id -> releases.id`. Manual releases are user-owned rows in `manual_releases` and are not valid session targets until a later session-domain migration adds a manual-release reference or polymorphic release target.

### Columns

|Column|Type|Notes|
|---|---|---|
|id|UUID|Primary key|
|release_id|UUID|FK → releases.id|
|user_id|UUID|Nullable FK -> user_accounts.id; null means legacy unassigned session|
|session_group_id|UUID|Nullable FK -> session_groups.id|
|rating|INTEGER|1–5 rating|
|mood|TEXT|User selected mood|
|notes|TEXT|Optional session notes|
|played_at|TIMESTAMP|Time of listening|
|vinyl_side|TEXT|Optional side (A,B,C,D...)|
|created_at|TIMESTAMP|Session creation time|

### Foreign Keys

```
release_id → releases.id
user_id -> user_accounts.id ON DELETE CASCADE
session_group_id -> session_groups.id ON DELETE SET NULL
```

### Indexes

```
PRIMARY KEY (id)

INDEX (release_id)

INDEX (user_id)

INDEX (user_id, release_id)

INDEX (user_id, played_at)

INDEX (played_at)

INDEX (session_group_id)
```

---

# Table: session_groups

Represents an optional timed listening session. A timed group contains multiple normal `sessions` rows through `sessions.session_group_id`.

Only one group should be active at a time. This invariant is currently enforced by `SessionGroupsService` rather than a database uniqueness constraint, which is enough for the current single-client app flow but should be hardened if multiple clients can start groups concurrently. The service auto-finishes stale active groups after 30 minutes without newly logged child sessions.

### Columns

|Column|Type|Notes|
|---|---|---|
|id|UUID|Primary key|
|user_id|UUID|Nullable FK -> user_accounts.id; null means legacy unassigned group|
|title|TEXT|Optional user title|
|status|TEXT|`active` or `completed`|
|style_focus|TEXT|Timed-session style intent: `one_style`, `mixed`, or `random`; defaults to `mixed`|
|mood_direction|TEXT|Timed-session mood intent: `steady_mood`, `mood_switch`, `energy_build`, or `cool_down`; defaults to `steady_mood`|
|session_type|TEXT|Timed-session context: `dj_set`, `casual_listening`, `rediscovery`, `testing_records`, or `background`; defaults to `casual_listening`|
|notes|TEXT|Optional notes for the overall timed session|
|started_at|TIMESTAMP|Timer start time|
|ended_at|TIMESTAMP|Timer stop time, nullable while active|
|created_at|TIMESTAMP|Group creation time|
|updated_at|TIMESTAMP|Last group update time|

### Indexes

```
PRIMARY KEY (id)

INDEX (status)

INDEX (user_id)

INDEX (user_id, status)

INDEX (started_at)
```

---

# Table: session_tracks

Stores optional track selections for a side-level listening session. A session can still represent a played side with no selected tracks; selected tracks add detail for future track-level analytics.

### Columns

|Column|Type|Notes|
|---|---|---|
|id|UUID|Primary key|
|session_id|UUID|FK -> sessions.id|
|track_position|TEXT|Discogs track position snapshot, e.g. A1|
|track_artist|TEXT|Optional Discogs track artist snapshot, e.g. Pixl & Tim Reaper|
|track_title|TEXT|Discogs track title snapshot|
|track_duration|TEXT|Optional Discogs duration snapshot|
|track_sequence|INTEGER|Tracklist order at time of logging|
|created_at|TIMESTAMP|Track selection creation time|

### Foreign Keys

```
session_id -> sessions.id ON DELETE CASCADE
```

### Indexes

```
PRIMARY KEY (id)

INDEX (session_id)

INDEX (track_position)
```

---

# Table: session_moods

Stores account-owned custom mood options shown on the Log Session screen. Shared reference rows may use `user_id = NULL`, but custom moods created from the app are tied to the authenticated account.

Logged sessions keep the selected mood text in `sessions.mood`, so deleting a custom mood option does not rewrite historical session rows or remove analytics history. The service canonicalizes mood names case-insensitively before storing new sessions and analytics groups case variants together.

### Columns

|Column|Type|Notes|
|---|---|---|
|id|UUID|Primary key|
|user_id|UUID|Nullable FK -> `user_accounts.id`; null means shared reference data|
|name|TEXT|Mood label unique per account|
|is_custom|BOOLEAN|User-defined mood option|
|created_at|TIMESTAMP|Creation time|

### Indexes

```
PRIMARY KEY (id)

UNIQUE (user_id, name)
INDEX (user_id, is_custom)
FOREIGN KEY (user_id) REFERENCES user_accounts(id) ON DELETE CASCADE
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
|user_id|UUID string|FK -> `user_accounts.id`; job owner|
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

INDEX (user_id, status)

INDEX (user_id, client_key, status)

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

Stores persistent AI Insights chat conversations. The MVP uses one public local conversation id by default: `local-single-thread`. Sessions are scoped by owner so the same public conversation id can exist for multiple accounts.

### Columns

|Column|Type|Notes|
|---|---|---|
|id|UUID string|Internal primary key|
|user_id|UUID string|FK -> `user_accounts.id`; chat owner|
|public_conversation_id|TEXT|Client-visible id returned as `conversation_id`|
|created_at|TIMESTAMP|Conversation creation time|
|updated_at|TIMESTAMP|Last message time|

### Indexes

```
PRIMARY KEY (id)

UNIQUE (user_id, public_conversation_id)

INDEX (user_id, updated_at)

INDEX (updated_at)
```

# Table: ai_chat_messages

Stores persisted user and assistant messages for AI Insights.

### Columns

|Column|Type|Notes|
|---|---|---|
|id|UUID string|Primary key|
|conversation_id|UUID/string|Foreign key to internal `ai_chat_sessions.id`|
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
|user_id|UUID string|FK -> `user_accounts.id`; import owner|
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
|user_id|UUID string|FK -> `user_accounts.id`; event owner|
|batch_id|UUID string|FK -> `spotify_listening_import_batches.id`|
|event_key|TEXT|Per-user dedupe key|
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
UNIQUE (user_id, event_key)
INDEX (user_id, played_at)
INDEX (played_date)
INDEX (played_year_month)
INDEX (user_id, normalized_artist_name)
INDEX (normalized_album_name)
INDEX (normalized_track_name)
```

## Spotify Summary Tables

Summary tables are rebuilt from imported events and queried by AI tools. Every summary row carries `user_id`; key and uniqueness constraints include the owner so different accounts can import identical Spotify history without colliding.

|Table|Purpose|
|---|---|
|spotify_artist_stats|Top artists by plays, meaningful plays, skips, total listening time, and first/last play time.|
|spotify_album_stats|Top albums by normalized artist+album keys.|
|spotify_track_stats|Top tracks by normalized artist+album+track keys.|
|spotify_hourly_stats|Listening distribution by hour of day.|
|spotify_monthly_artist_stats|Monthly artist signals for period-based questions.|
|spotify_skip_stats|Skip/end-reason counts for lightweight behavior analysis.|

## Spotify Collection Match Tables

Match tables connect Spotify summaries to user-owned collection memberships. They support collection-only recommendations and explain why a Spotify signal maps to vinyl data.

|Table|Purpose|
|---|---|
|spotify_vinyl_artist_matches|Exact normalized artist overlap, release ids, release count, confidence, match type, and explanation.|
|spotify_vinyl_release_matches|Exact normalized artist+album overlap with release id, Spotify display names, release display names, confidence, match type, and explanation.|

Track-level Spotify-to-vinyl matching remains deferred. User-selected session tracks are stored in `session_tracks` and can support future explicit track-play analytics without changing side-level session counts.

---

# Derived Analytics (Computed)

Current record, rating, mood, style, and monthly analytics are calculated dynamically from `sessions`, so one logged side session counts once even when optional selected tracks exist. Future track analytics should count `session_tracks` separately.

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

Release import uses a saved active Discogs integration token from
`provider_integrations` for backend-owned Discogs fetches. If no token is saved,
Android fetches the selected release directly from Discogs and submits the full
payload to the backend for mapping, cache upsert, and persistence. The backend
does not perform unauthenticated Discogs fetches and does not read a Discogs
access token from configuration.

Manual submissions do not write to `releases`. Saving a manual release inserts
or updates user-owned rows in `manual_release_drafts` until the form is complete,
then creates a `manual_releases` row owned by the authenticated user.

---

### Discogs Integration Token

```text
save token
   → validate token with Discogs /oauth/identity
   → encrypt token with DISCOGS_TOKEN_ENCRYPTION_KEY
   → upsert provider_integrations row
   → store external_user_id and external_username from Discogs

use token
   → load active provider_integrations row
   → decrypt access_token_ciphertext
   → build DiscogsApiConfig.from_token(...)
```

Collection sync uses `external_username` from identity validation. It does not
read a Discogs username from backend environment variables.

---

### Collection Membership

```
deactivate release
   → set release_collection_memberships.in_collection = false
   → set release_collection_memberships.collection_removed_at
   → keep release metadata, sessions, analytics, and cached Discogs payloads

reactivate release
   → set release_collection_memberships.in_collection = true
   → clear release_collection_memberships.collection_removed_at
   → reuse the existing release row
```

`collection_settings.source_of_truth = APP` makes local membership authoritative. In that mode, Discogs sync does not remove, deactivate, or re-add releases based on missing Discogs items.

Changing `collection_settings.source_of_truth` to `DISCOGS` requires an active
Discogs integration token. In Discogs-owned mode, sync can mark local collection
items inactive when they are missing from the Discogs collection, but release
metadata, sessions, analytics, and cached Discogs payloads remain stored.

---

### Listening Session

```
insert into sessions
```

Session creation is allowed only for releases that are still active in the collection.

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
manual_releases
manual_release_drafts
sessions
session_moods
discogs_release_cache
identify_jobs
collection_settings
provider_integrations
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
manual-to-discogs replacement links
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
release_collection_memberships.user_id + in_collection
```

will ensure fast analytics queries.

---

# Summary

The MVP schema provides:

- normalized record storage
    
- efficient session logging
    
- Discogs metadata caching
- user-owned manual submissions and drafts outside shared Discogs metadata
- server-backed identify progress
    
- simple analytics queries
    

while remaining **minimal and easy to maintain**.
