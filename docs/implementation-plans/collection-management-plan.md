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

Still intentionally placeholder/future:

- Full manual release entry form and save flow.
- Full Discogs mirror reconciliation when `DISCOGS` is selected.
- Scheduled sync and multi-folder Discogs selection.

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

### Out of Scope

- Full manual release entry form.
- Full manual-entry persistence flow.
- Scheduled sync.
- Multi-folder Discogs selection.
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

Navigation shell
  -> Manual-entry placeholder screen
```

## Validation Plan

### Backend

Current focused verification:

- `poetry run pytest tests/api/test_collection_api.py tests/api/test_releases_api.py tests/services/test_collection_sync_service.py tests/services/test_sessions_service.py tests/migrations/test_schema_migration.py`
- `poetry run ruff check app tests/api/test_collection_api.py tests/api/test_releases_api.py tests/services/test_collection_sync_service.py tests/services/test_sessions_service.py tests/migrations/test_schema_migration.py`
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

### Android

Current focused verification:

- `./gradlew :app:compileDebugKotlin`
- `./gradlew :app:ktlintCheck`
- `./gradlew :app:testDebugUnitTest --tests ...` is currently blocked locally by the JDK 26 / Android SDK 36 `JdkImageTransform` `jlink` failure before tests execute.

Checklist:

- Collection actions menu shows **Collection settings** first.
- Settings screen shows the correct source text and toggle state.
- Toggle ON displays `App`; toggle OFF displays `Discogs`.
- Collection add CTA expands left and collapses back to plus.
- Camera option opens identify camera flow.
- Pencil option opens manual-entry placeholder.
- Active Record Detail shows **Delete from collection** and log-session CTA.
- Delete confirmation appears before backend mutation.
- Inactive Record Detail hides log-session CTA and shows **Add to collection**.
- Re-adding restores active detail state.
- Records Collection list excludes inactive records.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Source-of-truth toggle implies Discogs mirroring before it is safe | User may expect removal behavior that is not fully implemented | Persist setting now, but clearly isolate full mirror reconciliation as the next backend sync task. |
| Deactivate accidentally deletes history | Analytics and insights lose context | Use logical membership fields only; add regression tests around sessions and analytics visibility. |
| Sync in `APP` mode mutates membership | Local collection becomes unreliable | Add explicit tests for empty/missing Discogs collection responses. |
| Re-add creates duplicates | Collection and analytics become noisy | Reactivate by stable release identity before creating any new release. |
| Manual-entry placeholder looks like complete functionality | User confusion | Keep copy minimal and route-only until the real form is planned. |

## Recommended Implementation Order

1. Backend schema and defaults.
2. Backend settings API.
3. Backend active/inactive membership API.
4. Backend `APP`-mode sync safety.
5. Android API models/repository methods.
6. Android Collection settings action and Settings toggle.
7. Android add CTA and placeholder manual-entry route.
8. Android Record Detail delete/reactivate behavior.
9. Focused backend and Android verification.

This order keeps data semantics stable before UI depends on them, while still allowing the Android add-entry placeholder work to proceed after navigation contracts are clear.
