# Implementation Plan: Collection Management

## Goal

Add a Records Collection milestone where the app treats the user's Discogs collection as the source of truth for current collection membership while preserving all local listening history.

The app should answer two separate questions:

- What records are currently in the Discogs collection?
- What records have listening history in the app?

A record can leave the current collection without losing sessions, ratings, moods, notes, analytics, or AI Insights context.

## Product Decisions

- Discogs folder `0` is the MVP source for the full collection.
- Discogs username and token come from backend `.env` variables.
- Android does not collect, store, or display Discogs credentials.
- Sync is manual for the MVP.
- Backend sync should use a job-shaped API so scheduled sync can be added later.
- The app stores one visible record per Discogs release id.
- Discogs duplicate copies are collapsed. The backend picks one deterministic copy.
- Removed records stay reachable from historical screens.
- The Records Collection list shows only active collection records by default.
- Default collection ordering is latest Discogs-added records first.

## Current Context

The backend already stores imported Discogs releases in `releases` and listening history in `sessions`. Analytics use the relationship between those tables.

The app also has async job precedent through identify jobs. Collection import should follow the same client-friendly shape: Android starts work, then polls status instead of waiting on one long request.

## Product Requirements

### MVP

- Add a bottom navigation item labeled **Collection**.
- Replace the current bottom-nav **Settings** item with **Collection**.
- Move settings access to the Home screen top-right corner.
- Use a settings icon only, without visible settings text.
- Keep the settings icon route pointed at the existing settings placeholder screen.
- Add a **Records Collection** screen.
- On first visit with no collection data, show an empty state with **Load Discogs Collection**.
- Style **Load Discogs Collection** like the existing green **Show More** action.
- When collection data exists, show **Sync Items** in the top-right action area.
- Keep the top-left back action on collection child screens.
- Start collection load and sync as background backend jobs.
- Show progress states while the job runs:
  - `Fetching collection data`
  - `Importing data`
  - `Loading...`
- After import completes, show the first 25 records.
- Show 25 collection records by default.
- Load the next 25 records when the user taps **Show More**.
- Sort collection records by Discogs `date_added` descending.
- Each collection card shows:
  - thumbnail image
  - release title
  - artist
  - year
  - format
  - record label
  - catalog number
  - comma-delimited styles
- Tapping a collection card opens the record detail screen.
- A record detail screen with no sessions shows `0` in all listening stat blocks.
- A record detail screen with no sessions shows `No data yet for this record.` under mood summary and recent sessions.
- A removed record remains reachable from old session history and detail screens.
- A removed record detail screen shows a message near the top after the main record card:
  - `This record was removed from your Discogs collection.`

### Not MVP

- Scheduled Discogs sync.
- Android credential entry.
- Multi-user Discogs account management.
- Duplicate-copy inventory UI.
- Discogs selling/listing management.
- Condition-note comparison between duplicate Discogs instances.
- Showing removed records in the main Records Collection list.
- Conflict resolution UI.

## Discogs Sync Rules

### Source Request

MVP sync uses:

```http
GET https://api.discogs.com/users/{username}/collection/folders/0/releases
```

The backend must fetch all paginated pages.

### Identity

Use Discogs release id as the collection identity:

- Prefer `basic_information.id`.
- Treat top-level `id` as equivalent when it matches the release id.
- Do not use `instance_id` as the app record identity.

### Duplicate Copies

Discogs may return multiple `instance_id` values for the same release id.

The backend should collapse duplicates to one representative copy:

1. Pick the copy with the newest `date_added`.
2. If tied, pick the copy with the lowest `instance_id`.

Store duplicate details only if useful for future sync diagnostics. Do not create duplicate visible records.

### Reconciliation

For each sync:

1. Fetch the full Discogs collection from folder `0`.
2. Collapse duplicate copies by release id.
3. Upsert new or changed releases.
4. Mark returned releases as active collection members.
5. Mark previously active releases as removed when their release id is missing from the latest sync.
6. Preserve all local historical data.

Deletion should be logical, not physical. The recommended term in backend code and database columns is `removed_from_collection`.

## Configuration

Add backend settings:

```env
DISCOGS_USERNAME=
DISCOGS_TOKEN=
```

If either value is missing, collection load and sync endpoints should fail with a clear configuration error. Android should display a simple user-facing error state.

## Data Model Recommendation

Extend the existing release storage rather than creating a separate visible record table for MVP.

Recommended fields on releases or an associated one-to-one collection metadata table:

| Field | Purpose |
| --- | --- |
| `discogs_release_id` | Stable Discogs release identity used for reconciliation. |
| `in_collection` | Whether the release is currently present in Discogs folder `0`. |
| `collection_added_at` | Representative Discogs `date_added`. |
| `collection_removed_at` | Timestamp when sync first detected removal. |
| `last_discogs_sync_at` | Last sync that observed this release. |
| `discogs_instance_id` | Representative Discogs instance id, not app identity. |

If the current schema already stores a Discogs release id, reuse it and add only the missing collection membership fields.

## API Contract Draft

### `POST /api/v1/collection/sync`

Start a manual collection sync job.

Use this endpoint for both first load and later sync. The backend can infer whether this is the first collection import.

#### Response

```json
{
  "job_id": "uuid",
  "status": "queued"
}
```

### `GET /api/v1/collection/sync/{job_id}`

Return current sync progress.

#### Response

```json
{
  "job_id": "uuid",
  "status": "running",
  "step": "fetching",
  "message": "Fetching collection data",
  "total_items": 150,
  "processed_items": 50,
  "added_count": 2,
  "updated_count": 8,
  "removed_count": 1,
  "error": null
}
```

#### Status Values

| Status | Meaning |
| --- | --- |
| `queued` | Job was created but has not started. |
| `running` | Job is fetching or importing data. |
| `succeeded` | Job completed successfully. |
| `failed` | Job reached a terminal error. |

#### Step Values

| Step | Android Message |
| --- | --- |
| `fetching` | `Fetching collection data` |
| `importing` | `Importing data` |
| `loading` | `Loading...` |

### `GET /api/v1/collection/releases`

Return active collection records.

#### Query Parameters

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `limit` | integer | `25` | Page size. |
| `offset` | integer | `0` | Number of rows to skip. |
| `include_removed` | boolean | `false` | Future-friendly flag for historical views. |

#### Sort

Always sort by `collection_added_at` descending for MVP.

#### Response

```json
{
  "items": [
    {
      "id": "uuid",
      "discogs_release_id": 11646493,
      "title": "Ruff Out Deh",
      "artist": "Babe Roots, Kojo Neatness",
      "year": 2018,
      "format": "Vinyl, 7\", 45 RPM",
      "label": "4Weed Records",
      "catalog_number": "4WDV009",
      "styles": ["Dub", "Dub Techno"],
      "thumb_url": "https://...",
      "collection_added_at": "2021-10-05T12:32:40-07:00",
      "in_collection": true
    }
  ],
  "limit": 25,
  "offset": 0,
  "has_more": true
}
```

### Record Detail API Impact

Existing record detail responses should include enough collection state for Android to show removed-record messaging:

```json
{
  "in_collection": false,
  "collection_removed_at": "2026-06-04T12:00:00Z"
}
```

## Android Implementation Shape

### Navigation

- Add a `Collection` bottom-nav destination.
- Remove bottom-nav `Settings`.
- Add a top-right settings icon to Home.
- Keep the existing settings placeholder destination.
- Add a collection detail route or reuse the existing record detail route if it can represent removed records safely.

### Records Collection Screen

Screen states:

| State | UI |
| --- | --- |
| Empty | Empty content with **Load Discogs Collection**. |
| Starting job | Disable action and show loading state. |
| Sync running | Show current progress message. |
| Loaded | Show latest 25 records. |
| Loading next page | Keep current records visible and show pagination loading. |
| Error | Show a concise error and allow retry. |

### Collection Card

Use existing card patterns from analytics/view-all screens where possible.

Card content should be compact and scan-friendly:

- image thumbnail on the left
- title and artist as primary text
- year, format, label, and catalog number as metadata
- styles as comma-delimited supporting text

### Removed Record Detail

When `in_collection` is false:

- keep normal record metadata visible
- show the removed-from-collection message below the main record card
- keep historical listening stats visible
- do not offer collection-only actions for the removed record

When the record has no sessions:

- stat blocks show `0`
- mood summary shows `No data yet for this record.`
- recent sessions shows `No data yet for this record.`

## Backend Implementation Shape

### Services

Add or extend services with clear boundaries:

| Service | Responsibility |
| --- | --- |
| `DiscogsService` | Fetch collection pages from Discogs using configured username and token. |
| `CollectionSyncService` | Reconcile fetched Discogs collection with local releases. |
| `CollectionJobService` | Create, run, and expose sync job status. |
| `ReleasesRepository` | Upsert release metadata and update collection membership fields. |

### Error Handling

Expected backend errors:

| Case | Suggested Response |
| --- | --- |
| Missing Discogs config | `500` or service error with stable code `discogs_config_missing`. |
| Discogs auth failure | `502` with stable code `discogs_auth_failed`. |
| Discogs rate limit | `429` or `502` with stable code `discogs_rate_limited`. |
| Job not found | `404`. |
| Expired job | `410`, if using job expiration. |

Android should show concise messages and keep retry available.

## Phased Plan

### Phase 0: Contract and Schema Design

| Task | Done Criteria |
| --- | --- |
| Confirm API contract | Endpoints, status values, and response fields are documented. |
| Design collection fields | Migration plan preserves existing release/session data. |
| Decide job storage | Sync jobs use existing job patterns or a small dedicated collection job table. |
| Define Discogs config | `DISCOGS_USERNAME` and `DISCOGS_TOKEN` are added to backend settings docs. |

### Phase 1: Backend Collection Sync

| Task | Done Criteria |
| --- | --- |
| Fetch Discogs folder pages | Backend retrieves all pages for folder `0`. |
| Collapse duplicates | Same release id maps to one representative copy. |
| Upsert metadata | New and changed releases are stored without duplicate app records. |
| Reconcile removals | Missing release ids become removed from collection without data deletion. |
| Add tests | Unit tests cover duplicate collapse, add, update, and removal preservation. |

### Phase 2: Backend Job API

| Task | Done Criteria |
| --- | --- |
| Add sync start endpoint | `POST /collection/sync` returns a job id quickly. |
| Add status endpoint | Android can poll progress and terminal state. |
| Persist job summaries | Added, updated, and removed counts are available after completion. |
| Map errors | Missing config and Discogs failures return stable error codes. |

### Phase 3: Collection List API

| Task | Done Criteria |
| --- | --- |
| Add active collection endpoint | Returns active records only by default. |
| Add pagination | `limit=25` and `offset` support **Show More**. |
| Add default sorting | Latest `collection_added_at` records appear first. |
| Add detail state | Record detail exposes `in_collection` and removal metadata. |

### Phase 4: Android Navigation and Screen Shell

| Task | Done Criteria |
| --- | --- |
| Update bottom nav | **Collection** replaces **Settings**. |
| Move settings access | Home shows a top-right settings icon routed to the existing placeholder. |
| Add collection route | Navigation smoke tests cover the new route. |
| Build empty state | First visit shows **Load Discogs Collection**. |

### Phase 5: Android Sync and List UI

| Task | Done Criteria |
| --- | --- |
| Start sync job | **Load Discogs Collection** and **Sync Items** call the backend job API. |
| Poll progress | UI shows fetching, importing, and loading messages. |
| Render records | First 25 latest records appear after sync. |
| Paginate records | **Show More** loads the next 25 records. |
| Handle failures | Missing config and sync errors show retryable messages. |

### Phase 6: Record Detail Historical Behavior

| Task | Done Criteria |
| --- | --- |
| Preserve historical access | Old session history can still open removed records. |
| Show removal message | Removed record detail shows the required message after the main card. |
| Handle no-session detail | Empty stat, mood, and recent-session states match product requirements. |
| Add tests/previews | Android previews or tests cover active, removed, and no-session states. |

### Phase 7: Documentation and Verification

| Task | Done Criteria |
| --- | --- |
| Update backend docs | Service map, API spec, and config docs mention collection sync. |
| Update Android docs | Navigation and screen behavior are documented if applicable. |
| Run backend checks | Focused backend tests pass. |
| Run Android checks | Compile, ktlint, lint, and route tests pass for touched modules. |

## Validation Plan

### Backend

- Test Discogs pagination with multiple pages.
- Test duplicate copies collapse to one release.
- Test newest `date_added` representative copy wins.
- Test removed release is marked inactive, not deleted.
- Test sessions remain linked to removed releases.
- Test missing `.env` config returns a stable error.
- Test collection list returns active records only.
- Test collection list sorts by `collection_added_at` descending.
- Test pagination returns `has_more` correctly.

### Android

- Verify bottom nav shows **Collection** instead of **Settings**.
- Verify Home settings icon opens the existing settings placeholder.
- Verify empty collection state shows **Load Discogs Collection**.
- Verify sync progress messages render.
- Verify loaded collection shows 25 latest records.
- Verify **Show More** appends 25 records.
- Verify card tap opens record detail.
- Verify no-session detail uses zero stats and `No data yet for this record.`
- Verify removed record detail shows the removal message and historical stats.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Discogs rate limits collection import | Sync may fail or stall. | Use paginated fetch with clear job errors and retry. |
| Duplicate copies create duplicate app records | Collection list becomes noisy and analytics skew. | Reconcile strictly by Discogs release id. |
| Removal logic deletes history | Analytics and Insights lose historical meaning. | Use logical collection membership fields only. |
| Long import blocks Android | Poor first-load experience. | Use background job plus polling. |
| Future scheduled sync needs different APIs | Rework risk. | Keep job-shaped backend contract from MVP. |

## Recommended First Implementation Slice

Build the backend reconciliation foundation first:

1. Add collection membership fields and migration.
2. Add Discogs collection fetch and duplicate collapse logic.
3. Add focused tests for add, duplicate, and removal behavior.
4. Add the manual sync job endpoints.
5. Add the collection list endpoint.

After that, implement the Android navigation and Records Collection screen against the stable contract.
