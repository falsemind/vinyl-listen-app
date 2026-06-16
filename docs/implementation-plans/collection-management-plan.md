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

### Out of Scope

- Full manual release entry form.
- Full manual-entry persistence flow.
- Manual-entry save/persistence.
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
19. Focused backend and Android verification.

This order keeps data semantics stable before UI depends on them, while still allowing the Android add-entry placeholder work to proceed after navigation contracts are clear.
