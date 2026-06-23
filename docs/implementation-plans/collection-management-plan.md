# Implementation Plan: Collection Management

## Goal

Extend Milestone 12 so the app can manage collection membership directly while preserving release metadata, listening history, analytics, and insights.

The first implementation slice gives the user three capabilities:

- Choose the collection source of truth: local app DB or Discogs.
- Add records through the existing identify flow or a future manual-entry path.
- Remove records from the visible collection without deleting release/history data.

Default behavior is app-owned collection management. Discogs can still enrich metadata, but it must not remove, deactivate, or re-add local records unless Discogs is explicitly selected as the source of truth.

## Current Implementation Status

First backend and Android slices are implemented:

- Backend `collection_settings` persistence with default `APP`.
- `GET /api/v1/collection/settings` and `PUT /api/v1/collection/settings`.
- Logical collection membership deactivate/reactivate endpoints on releases.
- Active-only Records Collection list/search behavior.
- Session creation guard for releases removed from the active collection.
- `APP` source-of-truth sync safety so empty/missing Discogs collection data does not mutate local membership.
- Android Collection action menu entry for **Collection settings**.
- Android Settings toggle with `Collection source of truth: App/Discogs`.
- Android Collection add CTA above search, expanding left into camera and pencil options with the same floating CTA style as search.
- Android manual-entry placeholder route.
- Android Record Detail **Delete from collection** / **Add to collection** actions with confirmation and log-session CTA hiding for inactive records.
- Backend Discogs collection folders endpoint, folder persistence, release-folder membership sync, and `folder_id` collection filtering.
- Android Collection action-menu icons for settings/sync, expandable **Collection folders**, folder filter state, and green folder chip with counter.
- Backend token-backed import-to-collection endpoint for server-owned Discogs imports.
- Android Collection camera add flow using identify candidates, client-provided Discogs payload import for no-token users, collection membership activation, Record Details navigation, and Collection refresh on return.

Still intentionally placeholder/future:

- Full manual release entry form and save flow.
- Full Discogs mirror reconciliation when `DISCOGS` is selected.
- Scheduled sync.

Latest completed slice:

- Wire the green Collection add CTA camera option into the identify flow as a collection-add path.
- After the user confirms an identify candidate, import the full Discogs release metadata, mark/reactivate the release active in the app collection, and open Record Details for that release.
- Keep the collection-add identify path usable for app-only/no-token users by fetching the selected full Discogs release from Android and importing it with the client-provided Discogs payload endpoint.

## Current Scope

### In Scope

- Backend collection settings contract.
- Backend active/inactive collection membership state.
- Backend endpoints for collection settings, deactivate, reactivate, and active collection filtering.
- Sync behavior update for app-owned source of truth.
- Android Collection action menu entry: **Collection settings**.
- Android Settings screen collection source toggle.
- Android Collection screen add CTA with identify/manual options.
- Android manual-entry placeholder screen.
- Android Record Detail action for **Delete from collection** / **Add to collection**.
- Confirmation dialog for collection removal.
- Hide log-session CTA when a record is no longer in the collection.
- Backend Discogs collection folders contract.
- Backend folder membership persistence and collection filtering.
- Android Collection action menu icon polish.
- Android expandable **Collection folders** action-menu option with folder filters.
- Backend import-to-collection contract for a confirmed Discogs candidate.
- Android identify camera option that imports the confirmed candidate into collection and opens Record Details.
- Manual release entry requirements for a minimal app-owned release.
- Manual release drafts list with bounded saved drafts.

### Out of Scope

- Discogs-equivalent manual submission form depth.
- Manual fields for companies, credits, mastering, lacquer cutting, copyright, matrix/runout data, or other production metadata.
- Automatic Discogs matching/replacement for manual releases.
- Bulk candidate import or multi-select.
- Scheduled sync.
- Persisting a selected Discogs folder as collection source.
- Treating folder filters as a source-of-truth or sync-scope setting.
- Destructive delete of releases, sessions, ratings, notes, analytics, or insight context.
- Fully implementing Discogs mirror reconciliation beyond preserving the backend setting and safe contract shape.

## Product Decisions

- Source of truth defaults to `App`.
- Toggle ON means `App`; toggle OFF means `Discogs`.
- Settings copy: `Collection source of truth: App` or `Collection source of truth: Discogs`.
- `App` source of truth means local collection membership is authoritative.
- In `App` mode, `Sync Items` can enrich release metadata but must not remove, deactivate, or re-add records.
- If the user has no Discogs collection and only uses Discogs for release lookup, `Sync Items` must not affect local collection membership.
- `Discogs` source of truth means the app may eventually mirror Discogs collection membership.
- Removal from collection is a logical deactivate, not a hard delete.
- Removed releases remain available to analytics, insights, and historical session screens.
- Removed releases do not appear in Records Collection.
- Removed releases cannot log new listening sessions until re-added.
- Re-adding a release reactivates the existing release record instead of creating a duplicate.
- Collection action-menu icons should use the existing green action-menu icon treatment: settings gear for **Collection settings** and a sync/refresh arrows icon for **Sync Items** / **Load Discogs collection**.
- **Collection folders** is visible only when Discogs credentials are configured and Discogs returns at least one non-default collection folder.
- **Collection folders** is expandable in the action menu and lists folder names.
- Tapping a folder name filters Records Collection to releases imported in that folder.
- Folder filters should use a green chip with a result counter in the header, matching existing artist and label filter chips.
- Clearing the folder chip returns to the unfiltered active collection.
- Collection add CTA camera starts identify in collection-add mode.
- Confirming an identify candidate imports full Discogs metadata before saving it to collection.
- Token-backed backend import-to-collection is idempotent: an existing active release is updated, and an inactive release is reactivated instead of duplicated.
- Android collection-add confirmation must not require a saved backend Discogs token. Existing local candidates reactivate membership directly; Discogs-only candidates are fetched on-device, imported as a client-provided Discogs payload, then reactivated in collection.
- Successful collection-add confirmation opens Record Details for the saved release and refreshes Records Collection when the user returns.
- Failed candidate import keeps the user in the identify/confirmation flow with visible retry/error handling.

## Backend Implementation

### Phase 1: Schema and Domain State

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Add collection source setting | 2-4h | Existing settings/config patterns | Persistent value exists with default `APP`. |
| Add active collection membership state | 2-4h | Current release model | Release records can be active or inactive in collection. |
| Add membership timestamps | 2-4h | Active membership field | Backend can track when a release was added, removed, and re-added. |
| Add migration | 2-4h | Schema decision | Existing releases migrate to active collection membership without data loss. |

Recommended fields, using existing table/patterns where possible:

| Field | Purpose |
| --- | --- |
| `collection_source_of_truth` | App-level setting: `APP` or `DISCOGS`. |
| `in_collection` or `collection_active` | Whether the release appears in Records Collection. |
| `collection_added_at` | First or latest time the release became active. |
| `collection_removed_at` | Time the release was removed from active collection. |
| `last_collection_sync_at` | Last sync that touched metadata or membership. |

### Phase 2: Collection Settings API

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Add settings read endpoint | 2-4h | Phase 1 | Android can load current source of truth. |
| Add settings update endpoint | 2-4h | Phase 1 | Android can toggle between `APP` and `DISCOGS`. |
| Add validation | 1-2h | API endpoints | Invalid source values return a clear 4xx error. |
| Add focused tests | 2-4h | API endpoints | Default, update, persistence, and invalid-value paths are covered. |

Draft contract:

```http
GET /api/v1/collection/settings
```

```json
{
  "source_of_truth": "APP"
}
```

```http
PUT /api/v1/collection/settings
```

```json
{
  "source_of_truth": "DISCOGS"
}
```

### Phase 3: Collection Membership API

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Update collection list query | 2-4h | Phase 1 | Records Collection returns active releases only by default. |
| Expose detail membership state | 2-4h | Phase 1 | Record Detail can tell whether the release is in collection. |
| Add deactivate endpoint | 2-4h | Phase 1 | Record can be removed from visible collection without deleting history. |
| Add reactivate endpoint | 2-4h | Phase 1 | Removed record can be restored to collection. |
| Guard session creation | 2-4h | Detail membership state | New session logging is rejected for inactive collection records. |
| Add focused tests | 4-6h | Endpoints and guard | Deactivate/reactivate/list/detail/session guard behavior is covered. |

Draft contract:

```http
POST /api/v1/releases/{release_id}/collection/deactivate
```

```http
POST /api/v1/releases/{release_id}/collection/reactivate
```

Record detail should include a compact state such as:

```json
{
  "id": 123,
  "in_collection": false,
  "collection_removed_at": "2026-06-15T12:00:00Z"
}
```

### Phase 4: Sync Behavior Update

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Load source-of-truth setting inside sync | 2-4h | Phase 2 | Sync branches by `APP` vs `DISCOGS`. |
| Preserve membership in `APP` mode | 2-4h | Sync branch | Missing Discogs items never deactivate local records. |
| Keep metadata enrichment safe | 2-4h | Existing Discogs import | Sync may update release metadata without changing membership in `APP` mode. |
| Define `DISCOGS` mirror placeholder | 1-2h | Sync branch | Code clearly isolates future mirror behavior. |
| Add sync tests | 4-6h | Sync branch | Empty Discogs collection and removed Discogs item cases are safe in `APP` mode. |

`DISCOGS` mirror behavior should be implemented only when the UX is ready for explicit destructive-feeling reconciliation. Until then, the backend should persist the setting and keep the branch obvious.

### Phase 4A: Discogs Folder Discovery

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Add Discogs folder client method | 2-4h | Existing `DiscogsService` config/client | Backend can call Discogs collection folders endpoint with configured username/token. |
| Add folder DTO/schema | 1-2h | Folder client method | API response includes stable folder id, name, item count if available, and default-folder flag. |
| Add folder persistence | 4-6h | Folder DTO/schema | Backend stores Discogs folder id/name/count/default metadata. |
| Add release-folder membership persistence | 4-8h | Folder persistence and collection sync | Backend stores which imported releases belong to which Discogs folders without duplicating releases. |
| Sync folder memberships | 4-8h | Release-folder persistence | Collection sync imports folder membership for non-default folders after the main collection import. |
| Add collection folders endpoint | 2-4h | Folder DTO/schema | Android can request folders from `/api/v1/collection/folders`. |
| Add folder filter to collection list | 2-4h | Release-folder persistence | `GET /collection/releases` supports `folder_id` and returns active releases in that folder. |
| Add folder filter count | 1-2h | Folder filter query | Filtered collection response `total` reflects folder item count for the green chip counter. |
| Gate response by Discogs configuration | 2-4h | Existing Discogs settings handling | Missing Discogs token/username returns a safe empty/not-configured response instead of surfacing a menu option. |
| Filter display eligibility | 1-2h | Folder response | Backend or Android can tell whether folders contain more than default folder `0`. |
| Add focused tests | 4-8h | Endpoint/service/filtering | Configured, missing-token, default-only, extra-folder, membership persistence, and folder-filter paths are covered. |

Draft contract:

```http
GET /api/v1/collection/folders
```

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

Folder-filtered collection list:

```http
GET /api/v1/collection/releases?folder_id=123&limit=25&offset=0
```

The response shape stays the same as the unfiltered collection list. `total` is the number of active collection records in the selected folder so Android can display the filter-chip counter.

For this slice, folder rows filter the current collection only. Persisting a selected folder as the default sync scope remains out of scope.

### Phase 4B: Identify Candidate Import to Collection

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Add import-to-collection service method | 2-4h | Existing release import service and membership repository | Backend can fetch full Discogs release data with saved credentials, save/update the release row, and mark it active in collection. |
| Add import-to-collection endpoint | 2-4h | Service method | Token-backed callers can submit a confirmed `discogs_release_id` and receive the saved release id/status. |
| Preserve import error mapping | 1-2h | Existing import endpoint | Missing Discogs token, invalid payload, 404, and Discogs upstream errors map to the same clear statuses as `/releases/import`. |
| Add idempotency coverage | 2-4h | Service method | Existing active releases update without duplicates; inactive releases reactivate with `collection_removed_at=null`. |
| Add focused API tests | 2-4h | Endpoint | Endpoint returns `201` for new releases, `200` for existing releases, and calls the collection activation path. |

Draft contract:

```http
POST /api/v1/releases/import-to-collection
```

```json
{
  "discogs_release_id": 555123,
  "force_refresh": false
}
```

```json
{
  "release_id": "release-123",
  "discogs_release_id": 555123,
  "status": "created"
}
```

This endpoint should reuse the full Discogs release import path rather than saving search-result/candidate summary data. It should set `in_collection=true`, clear `collection_removed_at`, set `collection_added_at` to the current time, and update `last_discogs_sync_at`. `discogs_instance_id` remains `null` for records added from identify/search rather than a Discogs collection item instance. It remains token-backed because the backend performs the Discogs fetch.

## Android Implementation

### Phase 5: API Client and Models

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Add collection settings DTOs | 1-2h | Backend Phase 2 | App can parse and send source setting. |
| Add membership fields to record detail model | 1-2h | Backend Phase 3 | UI can distinguish active and inactive records. |
| Add deactivate/reactivate calls | 2-4h | Backend Phase 3 | ViewModels can remove and restore collection membership. |
| Add repository methods | 2-4h | API client updates | UI screens do not call API client directly. |

### Phase 6: Collection Settings Entry

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Add **Collection settings** action | 1-2h | Existing Collection action menu | New option appears first in Records Collection actions. |
| Navigate to Settings screen | 1-2h | Existing navigation | Tapping the action opens Settings. |
| Add settings row and toggle | 2-4h | API client settings | Screen shows `Collection source of truth: App/Discogs`. |
| Persist toggle changes | 2-4h | Settings endpoint | Toggle update survives screen reload. |

### Phase 7: Add-to-Collection Entry Points

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Add green CTA above search | 2-4h | Collection screen layout | CTA appears above search without disrupting filters/list. |
| Add expand/collapse behavior | 2-4h | CTA | Plus turns into X and options expand left from the right side. |
| Add camera option | 1-2h | Existing identify navigation | Camera icon opens existing identify camera flow. |
| Add manual option | 2-4h | Navigation | Pencil icon opens new manual-entry placeholder screen. |
| Add placeholder manual screen | 1-2h | Navigation | Screen has header text for manual release info entry and saving into collection. |

### Phase 7A: Identify-to-Collection Confirmation

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Add collection-add identify mode | 2-4h | Existing identify navigation | Camera CTA launches the existing identify flow with a mode flag or route argument that distinguishes collection add from session logging. |
| Call collection save on candidate confirmation | 2-4h | Backend Phase 4B and existing client Discogs import | Confirming a local candidate reactivates membership; confirming a Discogs-only candidate fetches full metadata on-device, imports the client payload, and marks collection membership active. |
| Navigate to Record Details after save | 1-2h | Import response | Successful import opens the saved release's Record Details screen. |
| Refresh Collection on return | 1-2h | Collection refresh key | Returning from details shows the newly added record without manual sync/reload. |
| Add focused ViewModel/navigation tests | 2-4h | Repository method and route mode | Confirmation path calls the correct repository method and handles success/error states. |

### Phase 8: Record Detail Remove/Restore

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Add **Delete from collection** action | 1-2h | Existing Record Detail action menu | Active records show trash-bin action. |
| Add confirmation dialog | 2-4h | Delete action | Dialog explains history and analytics are preserved. |
| Call deactivate endpoint | 2-4h | Backend Phase 3 | Confirming removal updates backend and UI state. |
| Hide log-session CTA for inactive records | 2-4h | Detail membership field | User cannot start a new session from inactive release detail. |
| Swap to **Add to collection** action | 1-2h | Inactive detail state | Inactive records show plus action instead of delete action. |
| Call reactivate endpoint | 2-4h | Backend Phase 3 | Re-added record can log sessions again and appears in Collection. |
| Refresh collection list after membership changes | 1-2h | Deactivate/reactivate | Records disappear/reappear without duplicate rows. |

### Phase 9: Collection Action Menu Polish and Folders

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Add settings action icon | 1-2h | Existing Collection action menu | **Collection settings** shows a green settings gear icon on the right. |
| Add sync/load action icon | 1-2h | Existing Collection action menu | **Sync Items**, **Syncing...**, and **Load Discogs collection** use a green sync/refresh arrows icon on the right. |
| Add folders API client model | 2-4h | Backend Phase 4A | Android parses Discogs folder response and hides folders UI when not configured or default-only. |
| Load folders after collection import/list load | 2-4h | Folders API client model | Collection screen fetches folders after a Discogs-backed collection is available without blocking the collection list. |
| Add folder filter request support | 2-4h | Backend folder filter query | Collection list API client can request `folder_id` and parse filtered totals. |
| Add expandable **Collection folders** action | 2-4h | Folder load state | Action behaves like Record Detail expandable action rows and shows folder names as selectable sub-options. |
| Apply folder filter from menu | 2-4h | Expandable folders action | Tapping a folder reloads Records Collection with `folder_id`. |
| Add folder filter chip | 2-4h | Folder filter state | Header shows green folder chip with folder name and filtered count, matching artist/label chips. |
| Clear folder filter | 1-2h | Folder filter chip | Dismissing the chip reloads unfiltered active collection. |
| Hide folders action when ineligible | 1-2h | Folder load state | No **Collection folders** row appears when Discogs is not configured, folders fail safely, or only default folder exists. |
| Add focused UI/parser tests | 4-6h | Models, menu state, filter state | Parser, menu visibility, folder selection, chip copy/count, and clear behavior are covered. |

## Dependencies Map

```text
Schema and settings state
  -> Settings API
  -> Android settings toggle

Schema and membership state
  -> Collection list/detail API
  -> Deactivate/reactivate API
  -> Android Record Detail remove/restore

Collection source setting
  -> Sync behavior branch
  -> Safe APP-mode sync tests

Existing identify flow
  -> Collection add CTA camera option
  -> Identify collection-add mode
  -> Import confirmed candidate to collection
  -> Record Details for saved release

Navigation shell
  -> Manual-entry placeholder screen

Discogs credentials and folder endpoint
  -> Android folder API client
  -> Collection folders action visibility
  -> Folder membership persistence
  -> Folder-filtered collection API
  -> Expandable folder names in action menu
  -> Green folder filter chip and counter
```

## Validation Plan

### Backend

Current focused verification:

- `poetry run pytest tests/api/test_collection_api.py tests/api/test_releases_api.py tests/services/test_collection_sync_service.py tests/services/test_sessions_service.py tests/migrations/test_schema_migration.py`
- `poetry run pytest tests/services/test_release_import_service.py tests/api/test_releases_api.py`
- `poetry run ruff check app tests/api/test_collection_api.py tests/api/test_releases_api.py tests/services/test_collection_sync_service.py tests/services/test_release_import_service.py tests/services/test_sessions_service.py tests/migrations/test_schema_migration.py`
- `poetry run alembic heads`

Checklist:

- Migration applies cleanly to existing dev database.
- Existing releases default to active collection membership.
- `GET /collection/settings` returns `APP` by default.
- `PUT /collection/settings` persists `APP` and `DISCOGS`.
- Collection list excludes inactive releases.
- Record detail includes active/inactive collection state.
- Deactivate preserves release row and sessions.
- Reactivate restores collection membership without duplicates.
- Session creation fails or no-ops clearly for inactive records.
- `Sync Items` in `APP` mode does not remove, deactivate, or re-add local records when Discogs is empty or missing items.
- `GET /collection/folders` returns a safe not-configured/empty response when Discogs token or username is missing.
- `GET /collection/folders` marks default folder `0` and reports `has_extra_folders=false` when Discogs has only the default folder.
- `GET /collection/folders` reports `has_extra_folders=true` and folder names when Discogs returns additional folders.
- Collection sync stores release-folder membership for Discogs folders without creating duplicate releases.
- `GET /collection/releases?folder_id=...` returns only active collection records in that folder.
- Folder-filtered `total` matches the folder-filtered active record count.
- Folder filter ignores inactive/deleted collection records.
- `POST /releases/import-to-collection` imports full Discogs metadata before saving membership.
- Import-to-collection marks new releases active in collection.
- Import-to-collection reactivates inactive releases without duplicate rows.
- Import-to-collection preserves existing import error behavior for Discogs token/upstream failures.

### Android

Current focused verification:

- `./gradlew :app:compileDebugKotlin`
- `./gradlew :app:ktlintCheck`
- `JAVA_HOME=/Applications/Android Studio.app/Contents/jbr/Contents/Home ./gradlew :app:testDebugUnitTest --tests com.example.vinyllistenapp.data.api.CollectionParsingTest --no-configuration-cache`
- `JAVA_HOME=/Applications/Android Studio.app/Contents/jbr/Contents/Home ./gradlew :app:lintDebug --no-configuration-cache`

Checklist:

- Collection actions menu shows **Collection settings** first.
- Settings screen shows the correct source text and toggle state.
- Toggle ON displays `App`; toggle OFF displays `Discogs`.
- Discogs sync actions show confirmation copy before starting a sync job.
- Collection add CTA expands left and collapses back to plus.
- Camera option opens identify camera flow in collection-add mode.
- Confirming an identify candidate imports and saves the full release to collection.
- Successful candidate import opens Record Details for the saved release.
- Returning to Collection shows the added release without manual refresh.
- Pencil option opens manual-entry placeholder.
- Active Record Detail shows **Delete from collection** and log-session CTA.
- Delete confirmation appears before backend mutation.
- Inactive Record Detail hides log-session CTA and shows **Add to collection**.
- Re-adding restores active detail state.
- Records Collection list excludes inactive records.
- Collection actions menu shows green settings icon for **Collection settings**.
- Collection actions menu shows green sync/refresh arrows icon for **Sync Items** / **Load Discogs collection**.
- **Collection folders** action is hidden when Discogs is not configured or only the default folder exists.
- **Collection folders** action expands and collapses like Record Detail expandable action groups.
- Expanded **Collection folders** lists Discogs folder names as selectable filter options.
- Expanded **Collection folders** shows at most 10 folders, then a **View all folders** overflow row when more folders exist.
- **View all folders** opens a full Discogs folder list, and folder rows navigate back to a filtered Collection view.
- Tapping a folder reloads Records Collection with that folder filter.
- Folder filter chip uses the same green chip style and counter behavior as artist/label chips.
- Clearing the folder chip reloads the unfiltered active collection.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Source-of-truth toggle implies Discogs mirroring before it is safe | User may expect removal behavior that is not fully implemented | Persist setting now, but clearly isolate full mirror reconciliation as the next backend sync task. |
| Deactivate accidentally deletes history | Analytics and insights lose context | Use logical membership fields only; add regression tests around sessions and analytics visibility. |
| Sync in `APP` mode mutates membership | Local collection becomes unreliable | Add explicit tests for empty/missing Discogs collection responses. |
| Re-add creates duplicates | Collection and analytics become noisy | Reactivate by stable release identity before creating any new release. |
| Manual-entry placeholder looks like complete functionality | User confusion | Keep copy minimal and route-only until the real form is planned. |
| Folder list implies folder import or sync-scope selection | User may expect tapping a folder to change source-of-truth or future sync target | Treat folders as collection filters only in this slice; do not persist folder choice as sync scope. |
| Missing Discogs credentials create noisy errors | Collection menu feels broken for app-only users | Backend returns safe not-configured state and Android hides the folders action. |
| Default-only folders clutter the action menu | User sees a menu item with no useful options | Hide **Collection folders** unless `has_extra_folders=true`. |
| Folder membership sync is expensive | Sync may slow down for large Discogs accounts with many folders | Fetch folder membership after the main import, reuse pagination/progress patterns, and keep folder filtering dependent on stored membership. |
| Folder-filtered totals differ from Discogs folder counts | Deleted/inactive local records may be excluded from app collection filters | Use app active-membership count in the chip and document backend response semantics through tests. |
| Manual-entry form grows into full Discogs submission | Slice becomes too large and hard to validate | Keep first save path limited to release identity, basic label/catalog/barcode, coarse format, genre/style, and tracklist. |
| Manual release cannot be matched to Discogs later | User gets stuck with sparse metadata | Store normalized matching fields and keep manual releases separate from Discogs releases until explicit replacement. |
| Drafts become junk data | User sees stale partial records | Cap saved manual drafts at 5 per user/device account and expose delete/resume actions. |

## Future Phase 10: Minimal Manual Release Entry

### Goal

Replace the placeholder manual-entry screen with a small, app-owned release creation flow. The first version should let a user add a known release to their collection without Discogs, while preserving enough normalized metadata to support a later "replace with Discogs release" workflow.

### Product Requirements

- Entry point stays under the Collection add CTA pencil option.
- User can save a completed manual release directly into the active app collection.
- User can save a partially completed manual release as a draft and resume it later.
- Drafts appear on a dedicated manual release drafts screen.
- Saved drafts are capped at 5. When the cap is reached, creating another draft requires deleting or completing an existing draft.
- User can attach release cover art during manual entry.
- Manual releases are app-owned records, not Discogs releases. They must not be auto-merged into shared Discogs metadata.
- Later Discogs replacement should be an explicit user-confirmed action that can preserve listening history, ratings, notes, and collection membership.

### Minimal Field Set

| Area | Required for Save | Draft Behavior | Notes |
| --- | --- | --- | --- |
| Artist | Yes | Optional | Support one or more display artists; model as a list even if the first UI starts simple. |
| Title | Yes | Optional | Release title, not collection nickname. |
| Year | Optional | Optional | Store as a bounded integer matching Discogs-style release year for later matching/search. |
| Label | Yes | Optional | Store display label name separately from catalog number. |
| Catalog number | Optional | Optional | Important matching hint for later Discogs search. |
| Barcode | Optional | Optional | Normalize digits for matching, preserve display value if needed. |
| Format | Yes | Optional | Start with `Vinyl`, `CD`, `Tape`, `Other`. |
| Vinyl details | Required only when format is `Vinyl` | Optional | Size, speed, and disc count for first slice. |
| Cover art | Optional | Optional | Allow one uploaded image as the manual release cover; validate file type and size before upload/save. |
| Tracklist | At least one track title for save; vinyl tracks also require position | Optional | Duration can remain optional; track credits are optional. |
| Track credits | Optional | Optional | Use a constrained role dropdown such as `Featuring`, `Remix`, `Producer`, `Written-By`, `Other`. |
| Genre | Yes | Optional | Keep first genre list small and stable. |
| Style | Required only when genre is `Electronic` | Optional | First version can use a constrained style list. |

### Input Validation and Limits

Backend validation is the source of truth. Android must mirror the same limits for immediate feedback and disabled/enabled button state, but backend errors must still be handled as field-level validation results.

- Trim leading/trailing whitespace before validation and persistence.
- Reject blank required strings after trimming.
- Reject control characters in text fields. Allow normal punctuation, accented characters, and non-English artist/title text.
- Collapse repeated internal whitespace only for matching/search helper fields; preserve user-entered display text for release fields.
- Reject unknown enum values and invalid data types instead of coercing them silently.
- When a field-level validation error exists, do not also show a generic save/search failure for the same action.

| Field | Type | Limit | Backend Requirement | Android Requirement |
| --- | --- | --- | --- | --- |
| Artist name | string list | 1-20 artists; 1-200 chars each | Require at least one artist for release save. | Validate list count and per-name length before enabling **Save Release**. |
| Title | string | 1-200 chars | Required for release save. | Validate after trim and show inline error. |
| Year | integer | 1900-2100 | Optional; reject non-integer values and years outside the supported range. | Use numeric input and block out-of-range values before save. |
| Label name | string | 1-200 chars | Required for release save. | Validate after trim and show inline error. |
| Catalog number | string | 0-80 chars | Optional; preserve display value and store normalized value for matching. | Warn/block over-limit values. |
| Barcode | string | 0 or 8-14 digits after normalization | Optional; strip spaces/hyphens for normalized value. | Allow common pasted formats, then validate normalized digits. |
| Format | enum | `Vinyl`, `CD`, `Tape`, `Other` | Required for release save. | Use dropdown only; do not allow free text. |
| Vinyl size | enum | `7`, `10`, `12`, `Other` | Required when format is `Vinyl`. | Show only for Vinyl and require selection. |
| Vinyl speed | enum | `33 1/3`, `45`, `78`, `Other` | Required when format is `Vinyl`. | Show only for Vinyl and require selection. |
| Vinyl disc count | integer | 1-6 | Required when format is `Vinyl`; covers common 2xLP/3xLP without box-set modeling. | Use stepper/input with min/max guard. |
| Track count | list | 1-100 tracks | Require at least one track title for release save. | Prevent adding over 100 tracks. |
| Track title | string | 1-200 chars | Required per saved track. | Validate each visible track row. |
| Track position | string | 0-16 chars | Required for each saved vinyl track; optional for non-vinyl formats; reject control characters. | Show required state when format is `Vinyl`; keep length-limited. |
| Track duration | string | `m:ss` or `h:mm:ss`; 0-8 chars | Optional; validate only when present. | Validate format before save when entered. |
| Track credit role | enum | `Featuring`, `Remix`, `Producer`, `Written-By`, `Other` | Optional; reject unknown roles. | Use dropdown only. |
| Track credit name | string | 1-200 chars when role is present | Required when a credit role is added. | Validate paired role/name rows. |
| Genre | enum | Small app-defined list | Required for release save. | Use dropdown only. |
| Style | enum | Small app-defined Electronic style list | Required only when genre is `Electronic`. | Show and require only for Electronic. |
| Cover image | binary file | One file; `JPEG`, `PNG`, or `WebP`; max 500 KB; longest side 100..1200 px | Validate MIME/content type, size, readable image data, and dimensions before storing. | Validate picker metadata and image bounds before upload when available. |

### Manual Submissions Screen Requirements

- The existing manual-entry route becomes the **Manual Submissions** draft hub screen.
- Screen title is **Manual Submissions**.
- Screen subheader explains that the user can manually add releases to the collection and save or manage drafts.
- Show up to 5 saved manual release draft cards.
- Draft cards should be about double the height of the Recent Session cards so they can show more release detail.
- Draft cards should show the strongest available summary fields: cover thumbnail when present, artist, title, optional year, label/catalog number, format, draft updated time, and required-field completion state.
- Draft cards include a top-right delete icon button.
- Tapping a draft delete button opens a confirmation dialog before deleting the draft.
- Place an **Add Release** CTA in the lower-right corner, following the existing CTA treatment used elsewhere in the app.
- Tapping **Add Release** opens a manual release form overflow screen when fewer than 5 drafts exist.
- If 5 drafts already exist, tapping **Add Release** shows a dialog explaining that only 5 drafts are allowed and the user must delete or complete a draft before starting another.
- Tapping an existing draft opens the same overflow form populated with the draft values.
- The overflow form contains all manual release inputs, dropdowns, tracklist editing, vinyl size/speed/disc count controls, and cover image upload.
- Cover upload accepts one image only. First implementation should allow `JPEG`, `PNG`, and `WebP`, max 500 KB, with longest side between 100 px and 1200 px.
- Cover validation errors should be shown before save/upload when possible and returned from the backend as field-level errors when server validation fails.

### Manual Form Bottom Actions

- Bottom action layout should follow the Log Session button pattern.
- Secondary action is always **Cancel** and closes the overflow form after confirming if there are unsaved changes.
- Primary action starts as disabled **Save** while the form is empty.
- Once the user enters at least one field but required release fields are incomplete or invalid, primary action becomes **Save Draft**.
- Once all required release fields are valid, primary action becomes **Save Release**.
- **Save Draft** persists a draft, closes the form, and shows/updates the card on the **Manual Submissions** screen.
- **Save Release** creates the manual release, adds it to the active collection, removes the draft if saving from one, and navigates to Record Details. From Record Details, the back action returns to Collection.

### Data and Architecture Requirements

- Store committed manual releases in separate user-owned manual release tables, not in the shared Discogs-backed `releases` catalog.
- Keep manual release persistence behind the same repository/service boundary as imported releases where practical, but avoid overloading Discogs-specific mappers.
- Store core release fields in a Discogs-adjacent shape: artists, labels, identifiers, formats, genres/styles, and tracklist as separate structured data instead of one freeform blob.
- Model vinyl disc count explicitly so common 2xLP/3xLP releases do not require a later schema break.
- Keep cover art as a single optional manual-release image, with storage, validation, and response shape reusable for later image replacement/removal.
- Keep draft persistence separate from committed collection membership so drafts do not appear in collection, analytics, listening history, or insights.
- Design create/update draft APIs so Android can autosave later, even if the first UI uses explicit **Save draft**.
- Add validation in the backend/domain layer, with Android mirroring required-field state for user feedback.

### Manual Release Session Support Requirements

- Manual releases must become first-class session targets without moving them into the shared Discogs-backed `releases` table.
- A listening session must target exactly one release source: either a shared Discogs-backed release or a user-owned manual release.
- Backend schema should add an explicit manual release session target, such as nullable `sessions.manual_release_id`, make the existing shared-release target nullable, and enforce an exactly-one-target database check.
- Manual session writes must validate that the manual release belongs to the current user and is active in the user's collection.
- Existing Discogs-backed sessions must migrate unchanged and keep using the shared `releases.id` foreign key.
- Session create, update, delete, and release-history APIs must work for both release sources using the same user-facing behavior.
- Analytics repositories must stop assuming every session joins directly to the shared `releases` table. Aggregations should combine Discogs-backed sessions and manual-release sessions through an explicit source-aware query or adapter.
- Manual release metadata available for analytics includes artist, title, year, label, format, genre, style, cover, and tracklist. Missing optional fields must not break analytics rows.
- Record Details for manual releases must support **Log Session**, session history, and post-save refresh behavior, but must continue hiding Discogs-only external actions.
- Manual track positions must be preserved from user input. Plain numeric positions like `1`, `2`, `3` must not be converted into default A/B side options.
- When manual track positions include side prefixes such as `A1`, `B2`, or `C1`, backend and Android may derive side selectors from those prefixes.
- When manual track positions do not include side prefixes, Android Log Session should show a neutral track selector without the default Discogs A/B side fallback.
- Multi-disc vinyl support remains limited to a single manual release with a vinyl disc count and track positions entered by the user. Box sets and multiple-release packages remain out of scope.

### First-Slice Non-Goals

- No Discogs search, match suggestions, or replacement UI.
- No production/company credits, copyright fields, mastering/cutting details, matrix/runout identifiers, marketplace data, or submission-quality Discogs validation.
- No box set or multiple-release package modeling. Common single-release 2xLP/3xLP vinyl entries are in scope through disc count.
- No import/export of manual drafts.
- No automatic draft cleanup beyond the 5-draft cap.

### Phase 10A: Backend Manual Release Domain and Schema

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Define manual release persistence shape | 4-6h | Phase 10 requirements | Manual releases are user-owned rows in separate manual tables with structured artists/labels/identifiers/formats/genres/tracks, vinyl disc count, and optional cover reference. |
| Define shared validation constants | 2-4h | Input validation requirements | Backend exposes or documents the same limits Android uses for strings, counts, enums, barcode, durations, and cover upload. |
| Add manual draft persistence | 4-8h | Persistence shape | Drafts store partial form state separately from committed collection releases and include draft timestamps. |
| Add draft cap enforcement | 2-4h | Draft persistence | Backend prevents creating a sixth draft and returns a typed validation error. |
| Add cover image storage policy | 4-6h | Persistence shape | Backend accepts one cover image, validates `JPEG`/`PNG`/`WebP`, enforces 500 KB max and 100..1200 px longest-side bounds, and stores a reusable cover reference. |
| Add migration and rollback notes | 2-4h | Schema decisions | Migration applies cleanly and documents how manual release/draft data maps to existing release tables. |

### Phase 10B: Backend Manual Entry API Contracts

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Add draft list contract | 2-4h | Phase 10A | API returns up to 5 drafts with card summary fields, cover thumbnail reference, updated time, and completion state. |
| Add create/update draft contract | 4-8h | Phase 10A | API saves partial manual release data and returns field-level validation warnings without adding the draft to collection. |
| Add delete draft contract | 2-4h | Draft list contract | API deletes a draft and frees one draft slot. |
| Add save manual release contract | 4-8h | Phase 10A | API validates required fields, creates an app-owned manual release, activates collection membership, and removes the source draft when provided. |
| Add cover upload contract | 4-8h | Cover storage policy | API supports cover upload with typed errors for size, type, and storage failures. |

### Phase 10C: Backend Validation and Tests

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Add domain validation tests | 4-6h | Phase 10B | Tests cover required fields, Electronic style requirement, Vinyl size/speed/disc count, draft partial saves, and 5-draft cap. |
| Add API tests | 4-8h | Phase 10B | Tests cover draft CRUD, cover validation, save-to-collection, draft removal after save, and user ownership isolation for manual releases. |
| Add collection/history guard tests | 2-4h | Save manual release contract | Manual release save preserves collection semantics and does not create listening history or analytics until the user logs sessions. |
| Update backend docs | 2-4h | API tests | API spec, database schema, backend-services, and repository-structure docs describe manual entry endpoints, validation errors, cover constraints, storage/schema ownership, and source ownership. |

Current Phase 10C status:

- Covered now: service/API/repository tests cover required fields, Electronic style validation, Vinyl size/speed/disc count, duration/barcode/track role validation, draft partial saves, serialized 5-draft cap checks, locked draft consumption for save-from-draft behavior, draft CRUD, user scoping, cover validation policy, and list-item normalization.
- Covered now: persistence-level collection/history guard coverage proves a saved manual release creates only the intended user-owned manual release/collection state and does not create listening history, session rows, or analytics-visible activity until the user logs a session.
- Deferred until cover storage exists: successful cover persistence tests. Current implementation validates the upload contract and returns a typed storage-not-configured error for otherwise valid files.

### Phase 10D: Android API Models and Repository

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Add manual entry DTOs | 3-5h | Backend contracts | Android models represent drafts, draft summaries, manual release form data, field errors, and cover references. |
| Add repository methods | 4-6h | DTOs | Repository can list/create/update/delete drafts, upload cover, and save manual release to collection. |
| Add local form state model | 4-6h | DTOs | UI state tracks dirty fields, shared validation limits, required-field validity, cover validation state, and primary action mode. |
| Add parser/unit coverage | 2-4h | Repository methods | Tests cover draft summary parsing, validation error parsing, and manual release save response parsing. |

### Phase 10E: Android Manual Submissions Draft Hub

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Replace placeholder with draft hub | 4-6h | Phase 10D | **Manual Submissions** screen loads drafts and shows empty, loading, error, and populated states with title and subheader copy. |
| Build draft card layout | 4-6h | Draft hub | Cards are roughly double Recent Session card height and show cover, artist/title, label/catalog, format, updated time, completion state, and a top-right delete icon. |
| Add **Add Release** CTA | 2-4h | Draft hub | Lower-right CTA follows existing collection CTA styling and opens the form when fewer than 5 drafts exist. |
| Add draft cap dialog | 2-3h | Add Release CTA | When 5 drafts exist, CTA shows a dialog asking the user to delete or complete a draft before adding another. |
| Add draft delete confirmation | 2-4h | Draft card layout | Delete icon opens a confirmation dialog and removes the draft only after confirmation. |
| Add draft resume navigation | 2-4h | Draft card layout | Tapping a draft opens the overflow form with saved values. |

### Phase 10F: Android Manual Release Form

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Build overflow form shell | 4-6h | Phase 10D | Form opens as an overflow screen with bottom actions matching Log Session patterns. |
| Add release identity inputs | 4-8h | Form shell | Artist, title, optional year, label, catalog number, barcode, genre, and Electronic style inputs validate in UI state. |
| Add format controls | 4-6h | Form shell | Format dropdown supports `Vinyl`, `CD`, `Tape`, `Other`; vinyl exposes size, speed, and disc count. |
| Add tracklist editor | 6-8h | Form shell | User can add at least one track title and optional track role credits from the constrained dropdown. |
| Add button state behavior | 2-4h | Form validation | Empty form shows disabled **Save**; partial valid input shows **Save Draft**; complete valid input shows **Save Release**. |
| Add cancel/unsaved changes handling | 2-4h | Form shell | **Cancel** closes immediately when clean and asks for confirmation when unsaved changes exist. |

### Phase 10G: Android Cover Upload and Save Flows

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Add cover picker and preview | 4-6h | Form shell | User can choose one cover image and see a preview before saving. |
| Add client-side cover validation | 2-4h | Cover picker | Android blocks unsupported file types, files over 500 KB, and images outside 100..1200 px longest-side bounds before upload when metadata is available. |
| Wire **Save Draft** | 4-6h | Form state + repository | Partial form saves a draft, closes the form, and shows/updates the draft card. |
| Wire **Save Release** | 4-8h | Backend save contract | Complete form creates the manual release, adds it to collection, removes the draft when applicable, opens Record Details, and keeps the back path returning to Collection. |
| Add Android verification | 4-6h | Save flows | Focused tests or compile checks cover draft hub state, form action state, validation, and save response handling. |

### Phase 10H: Backend Manual Release Session Domain

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Add source-aware session target schema | 4-8h | Phase 10A | Sessions can reference either `releases.id` or `manual_releases.id`, with an exactly-one-target constraint, indexes for both targets, and unchanged migration behavior for existing Discogs-backed sessions. |
| Update session target resolution | 4-8h | Session target schema | Session create/update paths resolve manual release IDs for the current user, reject another user's manual release, and reject inactive or missing collection items. |
| Update session persistence and history queries | 4-8h | Target resolution | Session create, update, delete, and release-history queries work for manual releases without joining manual IDs through the shared `releases` table. |
| Add manual session API tests | 4-8h | Persistence updates | Tests cover successful manual session logging, ownership isolation, inactive/manual-missing errors, delete behavior, and release-history retrieval. |
| Update session API docs | 2-4h | API tests | API docs describe how session endpoints represent Discogs-backed and manual release targets. |

### Phase 10I: Manual Track Mapping and Android Log Session

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Define manual track side derivation | 2-4h | Phase 10H | Backend preserves manual track positions, derives side options only from prefixed positions, and avoids default A/B sides for plain numeric positions. |
| Update manual Record Details track response | 4-6h | Side derivation | Manual release details expose tracklist and available side/track options that Android can consume without Discogs-specific fallback logic. |
| Update Android Log Session manual release state | 4-8h | Track response | Log Session opens for manual releases, shows the correct track dropdown, avoids default A/B for plain positions, and saves manual sessions successfully. |
| Add track mapping tests | 4-6h | Android state | Backend tests cover numeric and prefixed positions; Android tests cover manual track dropdown state and save request mapping. |

### Phase 10J: Manual Sessions in Analytics and Insights

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Refactor analytics queries for mixed session targets | 6-12h | Phase 10H | Monthly plays, top records, recent activity, and session rollups include both Discogs-backed and manual sessions. |
| Add manual release metadata to analytics rows | 4-8h | Mixed target queries | Analytics responses can render manual artist, title, year, label, format, cover, genre, and style where available. |
| Update style and record drilldowns | 4-8h | Metadata rows | Style, mood, rating, and record-level drilldowns include manual sessions without requiring Discogs release joins. |
| Extend deterministic insight facts | 4-8h | Analytics support | Insight fact builders include manual sessions through the same combined analytics layer used for UI summaries. |
| Add analytics and insight tests | 6-10h | Query updates | Tests prove manual sessions affect expected counts, top-record rankings, style filters, history, and insight facts. |

### Phase 10 Dependency Map

```text
Backend schema/domain
  -> Draft and manual release API contracts
  -> Backend validation/tests/docs
  -> Android DTOs/repository
  -> Draft hub
  -> Overflow form
  -> Cover upload and save flows
  -> Backend manual release session domain
  -> Manual track mapping and Android Log Session
  -> Manual sessions in analytics and insights
```

## Recommended Implementation Order

1. Backend schema and defaults.
2. Backend settings API.
3. Backend active/inactive membership API.
4. Backend `APP`-mode sync safety.
5. Android API models/repository methods.
6. Android Collection settings action and Settings toggle.
7. Android add CTA and placeholder manual-entry route.
8. Android Record Detail delete/reactivate behavior.
9. Backend Discogs folders service/API.
10. Backend folder membership persistence and sync.
11. Backend folder-filtered collection query.
12. Android folders API model and parser.
13. Android Collection action menu icon polish.
14. Android expandable **Collection folders** row and visibility rules.
15. Android folder filter state, green chip, counter, and clear behavior.
16. Android folder overflow screen and sync confirmation.
17. Backend import-to-collection service/API for confirmed identify candidates.
18. Android identify collection-add mode, import confirmation, detail navigation, and collection refresh.
19. Backend manual release domain/schema, draft persistence, draft cap, and cover storage policy.
20. Backend manual entry API contracts for drafts, cover upload, and save-to-collection.
21. Backend validation, API tests, and docs updates.
22. Android manual entry DTOs, repository methods, and form state model.
23. Android **Manual Submissions** draft hub, draft cards, **Add Release** CTA, draft delete confirmation, and draft cap dialog.
24. Android overflow form, inputs, dropdowns, tracklist editor, and bottom action states.
25. Android cover picker, cover validation, **Save Draft**, **Save Release**, and focused verification.
26. Backend manual release session target schema, migration, ownership validation, session persistence, and release-history queries.
27. Backend manual track side derivation and Record Details track response for numeric and prefixed manual positions.
28. Android Log Session support for manual releases, including track dropdown mapping and save request handling.
29. Backend analytics query refactor for mixed Discogs/manual session targets.
30. Manual session analytics, drilldowns, insight facts, and focused backend/Android verification.

This order keeps data semantics stable before UI depends on them, while still allowing the Android add-entry placeholder work to proceed after navigation contracts are clear.
