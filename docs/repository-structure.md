---
name: repository-structure
description: This document explains the current monorepo detailed layout with most of the files and directories.
---

## Top-Level Layout

```text
.
├── .agents/
├── README.md
├── android-app/
├── backend/
├── docker-compose.yml
├── docs/
├── scripts/
└── spotify_import/
```

| Path | Purpose |
| --- | --- |
| `android-app/` | Android client project. Gradle/Kotlin Compose app with navigation, prototype screens, backend API integration, camera/gallery input, and Android tests. |
| `backend/` | FastAPI backend, database models, repositories, service layer, identification pipeline, migrations, tests, and backend scripts. |
| `docs/` | Product, architecture, implementation, research, and feature documentation. |
| `scripts/` | Repository-level helper scripts. |
| `spotify_import/` | Local-only directory for backend Spotify export imports. JSON exports are ignored; `.gitkeep` preserves the mount point. |
| `docker-compose.yml` | Local container orchestration entry point. |
| `.agents/` | Agent workflows and repository guidance. |

Local artifacts such as `.DS_Store`, `.ruff_cache/`, `backend/.venv/`, `backend/venv/`, `__pycache__/`, and generated OCR debug images may exist in a working tree. They are not part of the intended source layout.

## Documentation

```text
docs/
├── architecture/
│   ├── api-spec.md
│   ├── database-schema.md
│   ├── matching-pipeline.md
│   ├── navigation-graph.md
│   └── roadmap.md
├── features/
│   ├── backend-services.md
│   ├── identify-progress-jobs.md
│   └── identification-pipeline.md
├── implementation-plans/
│   ├── ai-insights-chat-plan.md
│   ├── android-app-implementation-plan.md
│   ├── android-client-rate-limit-backoff-plan.md
│   ├── android-live-barcode-identify-plan.md
│   ├── backend-mvp-stabilization-plan.md
│   ├── backend-rate-limiting-and-throttling-plan.md
│   ├── discogs-integration-plan.md
│   ├── identify-progress-status-plan.md
│   ├── identify-job-cooperative-cancellation-plan.md
│   ├── image-identify-ocr-backend-upgrade-plan.md
│   ├── image-identify-pipeline-plan.md
│   ├── listening-session-api-plan.md
│   ├── manual-search-implementation-plan.md
│   └── release-import-metadata-api-plan.md
├── product/
│   ├── app-design-system.md
│   ├── app-screens-mockups/
│   └── mvp-screen-spec.md
├── research/
│   └── image-identification-pipeline-improvements.md
└── repository-structure.md
```

| Folder | Purpose |
| --- | --- |
| `architecture/` | Stable system design references: API, database, matching, navigation, roadmap. |
| `features/` | Current behavior docs for implemented backend features and pipelines. |
| `implementation-plans/` | Planning docs for completed or upcoming backend/product work. |
| `product/` | Product-facing screen specs, design tokens, and mockup references. |
| `research/` | Investigation notes and improvement ideas. |

## Backend

```text
backend/
├── Dockerfile
├── alembic.ini
├── pyproject.toml
├── app/
├── alembic/
├── scripts/
└── tests/
```

`backend/pyproject.toml` defines the Python backend package, tooling, and test configuration. The current backend requires Python `>=3.13` and uses Black, Ruff, Pytest, and Pytest Asyncio.

### Backend Application

```text
backend/app/
├── main.py
├── ai/
│   ├── chat_adapter.py
│   └── insight_tools.py
├── api/
│   ├── auth_dependencies.py
│   ├── router.py
│   └── routes/
│       ├── ai.py
│       ├── analytics.py
│       ├── auth.py
│       ├── collection.py
│       ├── health.py
│       ├── identify.py
│       ├── integrations.py
│       ├── manual_releases.py
│       ├── releases.py
│       └── sessions.py
├── core/
│   ├── config.py
│   ├── logging.py
│   ├── rate_limit.py
│   └── runtime_dependencies.py
├── database/
│   ├── base.py
│   ├── db.py
│   └── session.py
├── models/
│   ├── ai_chat.py
│   ├── auth.py
│   ├── collection_folders.py
│   ├── collection_settings.py
│   ├── collection_sync_job.py
│   ├── discogs_release_cache.py
│   ├── identify_job.py
│   ├── provider_integration.py
│   ├── releases.py
│   ├── sessions.py
│   ├── sessions_moods.py
│   └── spotify_listening.py
├── pipelines/
│   └── identification/
├── repositories/
│   ├── ai_chat_repository.py
│   ├── analytics_repository.py
│   ├── auth_repository.py
│   ├── collection_folders_repository.py
│   ├── collection_settings_repository.py
│   ├── collection_sync_job_repository.py
│   ├── discogs_release_repository.py
│   ├── identify_job_repository.py
│   ├── manual_release_repository.py
│   ├── provider_integration_repository.py
│   ├── releases_repository.py
│   ├── session_groups_repository.py
│   ├── sessions_moods_repository.py
│   ├── sessions_repository.py
│   └── spotify_listening_repository.py
├── schemas/
│   ├── ai.py
│   ├── analytics.py
│   ├── auth.py
│   ├── collection.py
│   ├── identify.py
│   ├── integrations.py
│   ├── manual_releases.py
│   ├── releases.py
│   └── sessions.py
├── services/
│   ├── ai_insights_service.py
│   ├── analytics_service.py
│   ├── auth_account_service.py
│   ├── auth_email_delivery.py
│   ├── auth_token_service.py
│   ├── collection_sync_job_service.py
│   ├── collection_sync_service.py
│   ├── discogs_integration_service.py
│   ├── discogs_service.py
│   ├── identify_job_service.py
│   ├── identify_service.py
│   ├── manual_release_policy.py
│   ├── manual_release_service.py
│   ├── password_hashing.py
│   ├── release_import_service.py
│   ├── release_mapper.py
│   ├── token_cipher.py
│   ├── session_groups_service.py
│   ├── sessions_service.py
│   ├── spotify_listening_import_service.py
│   └── spotify_listening_rollup_service.py
└── utils/
```

| Layer | Responsibility |
| --- | --- |
| `main.py` | Creates the FastAPI app, attaches `/api/v1`, applies inbound API rate limiting, handles auth/validation errors, and logs runtime dependency status during startup. |
| `ai/` | AI runtime adapters owned by the backend, currently disabled fallback plus LM Studio native chat and OpenAI-compatible chat completions support. |
| `api/auth_dependencies.py` | Bearer token dependency for protected routes and current-user lookup. |
| `api/router.py` | Registers versioned route modules under `/health`, `/auth`, `/identify`, `/releases`, `/manual-releases`, `/collection`, `/integrations`, `/sessions`, `/analytics`, and `/ai`; all non-health/non-auth application routers require auth by default. |
| `api/routes/` | HTTP boundary. Routes read request data, inject database sessions and services, and map service errors to HTTP responses. |
| `core/` | Configuration, logging, inbound rate-limit policies, and optional runtime dependency checks. |
| `database/` | SQLAlchemy base, engine/session setup, and request-scoped DB dependency. |
| `models/` | SQLAlchemy tables for auth accounts/sessions/codes/usage/audit/deletion-audit foundations, shared Discogs releases, user-owned manual releases and drafts, user collection memberships, collection settings, user Discogs collection folders, user release-folder membership, provider integrations, Discogs cache rows, identify jobs, user collection sync jobs, AI chat history, timed session groups, listening sessions, moods, and Spotify listening imports/rollups. |
| `repositories/` | Database access methods. Repositories keep SQLAlchemy queries out of services and routes. |
| `schemas/` | Pydantic request/response models exposed by the API. |
| `services/` | Business workflows: auth account/token/email/password/deletion handling, AI insights chat, analytics, identification, identify job progress, Discogs integration/token storage, Discogs access/cache, collection sync and sync jobs, release import, manual release validation/drafts/save contracts, release mapping, timed session groups, listening sessions, and Spotify listening imports/rollups. |
| `pipelines/identification/` | Image preprocessing, OCR, barcode detection, identifier parsing, search planning, and candidate ranking. |

### API Route Map

All routes are nested under `/api/v1`.

| Route | Handler module | Main service |
| --- | --- | --- |
| `GET /health` | `api/routes/health.py` | Runtime/database health checks. |
| `GET /health/runtime` | `api/routes/health.py` | Optional dependency status. |
| `POST /auth/register` | `api/routes/auth.py` | `AuthAccountService`. |
| `POST /auth/verify-email` | `api/routes/auth.py` | `AuthAccountService`. |
| `POST /auth/resend-verification` | `api/routes/auth.py` | `AuthAccountService`. |
| `POST /auth/login` | `api/routes/auth.py` | `AuthAccountService` plus `AuthTokenLifecycleService`. |
| `POST /auth/refresh` | `api/routes/auth.py` | `AuthTokenLifecycleService`. |
| `POST /auth/logout` | `api/routes/auth.py` | Current auth session revocation. |
| `POST /auth/logout-all` | `api/routes/auth.py` | All-session revocation for the current account. |
| `GET /auth/me` | `api/routes/auth.py` | Current account summary. |
| `POST /auth/password-reset/request` | `api/routes/auth.py` | `AuthAccountService`. |
| `POST /auth/password-reset/confirm` | `api/routes/auth.py` | `AuthAccountService`. |
| `POST /auth/password/change` | `api/routes/auth.py` | `AuthAccountService`. |
| `DELETE /auth/account` | `api/routes/auth.py` | `AuthAccountService`. |
| `POST /identify` | `api/routes/identify.py` | `IdentifyService` plus identify admission guard and `EntitlementService` usage gate. |
| `POST /identify/jobs` | `api/routes/identify.py` | User-owned `IdentifyJobService` with per-user/client admission control and usage gate. |
| `GET /identify/jobs/{job_id}` | `api/routes/identify.py` | User-owned `IdentifyJobService`. |
| `GET /collection/settings` | `api/routes/collection.py` | `CollectionSettingsRepository`. |
| `PUT /collection/settings` | `api/routes/collection.py` | `CollectionSettingsRepository`. |
| `POST /collection/sync` | `api/routes/collection.py` | `CollectionSyncJobService`. |
| `GET /collection/sync/active` | `api/routes/collection.py` | `CollectionSyncJobService`. |
| `GET /collection/sync/{job_id}` | `api/routes/collection.py` | `CollectionSyncJobService`. |
| `GET /collection/folders` | `api/routes/collection.py` | User-scoped `CollectionFoldersRepository` plus Discogs integration state. |
| `GET /collection/releases` | `api/routes/collection.py` | User-scoped `ReleasesRepository` membership query plus `ManualReleaseRepository`; supports artist, label, favorites, and Discogs folder filters. |
| `GET /collection/search` | `api/routes/collection.py` | User-scoped collection-only internal release search across Discogs-backed and manual releases. |
| `GET /manual-releases/drafts` | `api/routes/manual_releases.py` | User-scoped `ManualReleaseService` draft list. |
| `POST /manual-releases/drafts` | `api/routes/manual_releases.py` | `ManualReleaseService` partial draft create with draft cap validation. |
| `PUT /manual-releases/drafts/{draft_id}` | `api/routes/manual_releases.py` | `ManualReleaseService` partial draft update scoped to the current user. |
| `DELETE /manual-releases/drafts/{draft_id}` | `api/routes/manual_releases.py` | `ManualReleaseService` draft delete scoped to the current user. |
| `POST /manual-releases/drafts/{draft_id}/cover` | `api/routes/manual_releases.py` | `ManualReleaseService` cover validation, local storage, and draft metadata update. |
| `POST /manual-releases` | `api/routes/manual_releases.py` | `ManualReleaseService` complete manual release validation and user-owned save. |
| `GET /integrations/discogs` | `api/routes/integrations.py` | `DiscogsIntegrationService`. |
| `PUT /integrations/discogs/token` | `api/routes/integrations.py` | `DiscogsIntegrationService`. |
| `DELETE /integrations/discogs/token` | `api/routes/integrations.py` | `DiscogsIntegrationService`. |
| `GET /releases` | `api/routes/releases.py` | Release listing placeholder/current route behavior. |
| `GET /releases/search` | `api/routes/releases.py` | Token-backed backend Discogs release search. |
| `POST /releases/import` | `api/routes/releases.py` | `ReleaseImportService`. |
| `POST /releases/import-to-collection` | `api/routes/releases.py` | Token-backed `ReleaseImportService` import plus collection activation. |
| `POST /releases/import/client-discogs` | `api/routes/releases.py` | Client-provided Discogs payload import through `ReleaseImportService`. |
| `GET /releases/{release_id}` | `api/routes/releases.py` | `ReleaseImportService` with `ManualReleaseRepository` fallback for user-owned manual releases. |
| `POST /releases/{release_id}/refresh` | `api/routes/releases.py` | `ReleaseImportService`. |
| `POST /releases/{release_id}/collection/deactivate` | `api/routes/releases.py` | `ReleasesRepository` with `ManualReleaseRepository` fallback. |
| `POST /releases/{release_id}/collection/reactivate` | `api/routes/releases.py` | `ReleasesRepository` with `ManualReleaseRepository` fallback. |
| `GET /releases/{release_id}/sessions` | `api/routes/releases.py` | `SessionsService` with empty manual-release fallback until manual sessions are modeled. |
| `POST /sessions` | `api/routes/sessions.py` | `SessionsService`. |
| `GET /sessions/summary` | `api/routes/sessions.py` | `SessionsService` home summary aggregation. |
| `GET /sessions/groups/active` | `api/routes/sessions.py` | `SessionGroupsService` active group lookup and stale auto-finish. |
| `POST /sessions/groups` | `api/routes/sessions.py` | `SessionGroupsService` timed session start. |
| `PATCH /sessions/groups/{group_id}/finish` | `api/routes/sessions.py` | `SessionGroupsService` timed session finish. |
| `GET /sessions/{session_id}` | `api/routes/sessions.py` | `SessionsService`. |
| `GET /analytics/plays/monthly` | `api/routes/analytics.py` | `AnalyticsService` monthly play counts. |
| `GET /analytics/top-records` | `api/routes/analytics.py` | `AnalyticsService` top record aggregation. |
| `GET /analytics/rating-distribution` | `api/routes/analytics.py` | `AnalyticsService` rating frequency aggregation. |
| `GET /analytics/mood-distribution` | `api/routes/analytics.py` | `AnalyticsService` mood frequency aggregation. |
| `GET /analytics/style-distribution` | `api/routes/analytics.py` | `AnalyticsService` release style frequency aggregation. |
| `GET /analytics/sessions` | `api/routes/analytics.py` | `AnalyticsService` month session drilldown with pagination. |
| `GET /analytics/records/by-rating` | `api/routes/analytics.py` | `AnalyticsService` rating drilldown with record counts. |
| `GET /analytics/records/by-mood` | `api/routes/analytics.py` | `AnalyticsService` mood drilldown with record counts. |
| `GET /analytics/records/by-style` | `api/routes/analytics.py` | `AnalyticsService` style drilldown with record counts. |
| `POST /ai/chat` | `api/routes/ai.py` | User-scoped `AiInsightsService` grounded chat service. |
| `POST /ai/spotify/import` | `api/routes/ai.py` | User-scoped `SpotifyListeningImportService`. |

### Identification Pipeline Package

```text
backend/app/pipelines/identification/
├── __init__.py
├── barcode_detector.py
├── candidate_ranker.py
├── extractor.py
├── identifier_parser.py
├── models.py
├── normalization.py
├── ocr_backends.py
├── ocr_extractor.py
├── ocr_layout_analyzer.py
├── preprocess.py
├── search_evidence.py
└── search_planner.py
```

This package is used by `IdentifyService`. It turns an uploaded image into structured identifiers and ranked release candidates. See `docs/features/identification-pipeline.md` for the detailed flow.

## Backend Tests

```text
backend/tests/
├── api/
├── core/
├── data/
│   ├── discogs_responses/
│   └── images/
├── fixtures/
├── migrations/
├── pipelines/
├── repositories/
├── services/
├── utils/
├── conftest.py
└── pytest.ini
```

| Folder | Coverage |
| --- | --- |
| `api/` | FastAPI route behavior and versioned paths. |
| `core/` | Runtime dependency reporting. |
| `fixtures/` | Test clients, database fixtures, and service stubs. |
| `migrations/` | Alembic/schema expectations. |
| `pipelines/` | Identification pipeline units: preprocessing, OCR, parsing, search planning, evidence scoring, and ranking. |
| `repositories/` | Real repository SQL coverage, including dialect-specific analytics queries and manual release collection/history boundary guards. |
| `services/` | Analytics, Discogs client/service, Discogs integration service, token ciphering, collection settings, collection sync, collection sync jobs, identify service, identify job service, release import, manual release service/policy, release mapper, session groups service, sessions service, and Home summary aggregation. |
| `utils/` | Utility-level test coverage. |
| `data/` | Static image and Discogs response fixtures. |

## Backend Migrations And Scripts

```text
backend/alembic/
├── env.py
├── script.py.mako
└── versions/
    ├── 1a8551e314b6_create_models_releases_sessions_.py
    ├── a5427b530a12_latest_db_revision.py
    ├── b7f3c9d2a4e1_add_identify_jobs.py
    ├── 7ab6c5d4e3f2_add_identify_job_client_key.py
    ├── d2b8c7e9f041_add_identify_job_stale_recovery_index.py
    ├── f3a4b5c6d7e8_add_identify_job_cancel_requested_at.py
    ├── c8f2d4a9b6e1_add_ai_chat_history.py
    ├── 4e2a1c9d8b70_add_spotify_listening_import.py
    ├── 8c1d2e3f4a5b_add_session_groups.py
    ├── 9c6e2a1f4b80_add_spotify_rollups_and_matches.py
    ├── c8d9e0f1a2b3_scope_async_ai_spotify.py
    ├── ab12cd34ef56_add_provider_integrations.py
    ├── c4d5e6f7a8b9_add_manual_release_schema.py
    └── eed6974773b8_init.py

backend/scripts/
└── benchmark_ocr_backends.py
```

Alembic owns schema migrations. `benchmark_ocr_backends.py` supports local comparison of OCR backend behavior.

## Android App

High-level Android layout:

```text
android-app/
├── app/
│   ├── build.gradle.kts
│   └── src/
│       ├── main/
│       │   ├── AndroidManifest.xml
│       │   ├── java/com/example/vinyllistenapp/
│       │   └── res/
│       ├── test/
│       └── androidTest/
├── gradle/
├── build.gradle.kts
├── gradle.properties
├── gradlew
├── gradlew.bat
├── local.properties
└── settings.gradle.kts
```

Main Android package layout:

```text
com/example/vinyllistenapp/
├── MainActivity.kt
├── VinylListenApp.kt
├── data/
│   ├── MockVinylData.kt
│   └── api/
├── domain/
├── navigation/
└── ui/
    ├── components/
    ├── screens/
    └── theme/
```

Detailed Android layout:

```text
android-app/
├── build.gradle.kts
├── local.properties
├── gradle.properties
├── gradlew
├── gradlew.bat
├── settings.gradle.kts
├── app/
│   ├── build.gradle.kts
│   ├── proguard-rules.pro
│   └── src/
│       ├── main/
│       │   ├── AndroidManifest.xml
│       │   ├── java/com/example/vinyllistenapp/
│       │   │   ├── MainActivity.kt
│       │   │   ├── VinylListenApp.kt
│       │   │   ├── data/
│       │   │   │   ├── MockVinylData.kt
│       │   │   │   └── api/
│       │   │   │       ├── ApiRetryPolicy.kt
│       │   │   │       ├── DiscogsApiClient.kt
│       │   │   │       └── VinylApiClient.kt
│       │   │   ├── domain/
│       │   │   │   └── RecordModels.kt
│       │   │   ├── navigation/
│       │   │   │   ├── VinylNavHost.kt
│       │   │   │   └── VinylRoutes.kt
│       │   │   └── ui/
│       │   │       ├── components/
│       │   │       │   ├── PrototypeComponents.kt
│       │   │       │   ├── StatusFeedback.kt
│       │   │       │   └── VinylComponents.kt
│       │   │       ├── screens/
│       │   │       │   ├── AiInsightsScreen.kt
│       │   │       │   ├── AnalyticsScreen.kt
│       │   │       │   ├── CaptureRecordScreen.kt
│       │   │       │   ├── HomeScreen.kt
│       │   │       │   ├── ManualSearchScreen.kt
│       │   │       │   ├── MatchConfirmationScreen.kt
│       │   │       │   ├── ProcessingScreen.kt
│       │   │       │   ├── RecordDetailScreen.kt
│       │   │       │   ├── RecordDisplayFormatters.kt
│       │   │       │   ├── RelativeDateFormatter.kt
│       │   │       │   ├── ScreenPreviews.kt
│       │   │       │   ├── SessionLoggingScreen.kt
│       │   │       │   ├── SettingsScreen.kt
│       │   │       │   └── ViewAllScreens.kt
│       │   │       └── theme/
│       │   │           ├── Theme.kt
│       │   │           ├── Type.kt
│       │   │           ├── VinylColors.kt
│       │   │           └── VinylTokens.kt
│       │   └── res/
│       │       ├── drawable/
│       │       ├── mipmap-*/
│       │       ├── values/
│       │       └── xml/
│       │           └── file_paths.xml
│       ├── test/
│       │   └── java/com/example/vinyllistenapp/
│       │       ├── ExampleUnitTest.kt
│       │       ├── data/api/
│       │       │   ├── ApiRetryPolicyTest.kt
│       │       │   ├── CollectionParsingTest.kt
│       │       │   └── IdentifyJobStateParsingTest.kt
│       │       ├── navigation/
│       │       │   └── VinylNavHostStateTest.kt
│       │       └── ui/screens/
│       │           ├── AnalyticsMonthsTest.kt
│       │           ├── MatchConfirmationScreenTest.kt
│       │           ├── RelativeDateFormatterTest.kt
│       │           └── SessionSideOptionsTest.kt
│       └── androidTest/
│           └── java/com/example/vinyllistenapp/
│               ├── ExampleInstrumentedTest.kt
│               └── VinylNavigationSmokeTest.kt
└── gradle/
    ├── libs.versions.toml
    └── wrapper/
```

`android-app/local.properties` is local-only and ignored by Git. It can override `vinylApiBaseUrl` or `VINYL_API_BASE_URL` for non-emulator testing. The default debug base URL remains `http://10.0.2.2:8000/api/v1`, which targets the host machine from the Android emulator. For a USB-connected physical device, run `adb reverse tcp:8000 tcp:8000`, set the debug base URL to `http://localhost:8000/api/v1`, use the Android Studio bundled JBR if the system JDK is too new, and rebuild/reinstall because the value is compiled into `BuildConfig`.

### Android Source Packages

| Package | Responsibility |
| --- | --- |
| `data/` | Prototype fallback data and backend API client code. |
| `data/api/` | Lightweight HTTP clients for backend API calls and direct Discogs access. `VinylApiClient` covers identify jobs, integration status/token save/delete, token-backed release import, client-provided Discogs payload import, detail/refresh/history, collection records/folders/settings/sync APIs, session create, timed session groups, Home summary, analytics calls, and safe GET retry/backoff behavior. `DiscogsApiClient` handles device-side manual/barcode Discogs search and selected-release fetch with local unauthenticated rate limiting. |
| `domain/` | UI-facing domain models for records, collection folders, release side options, sessions, timed session groups, candidates, Home summaries, and analytics dashboard data. |
| `navigation/` | Compose navigation host, active timed-session state, and route helpers for Home, capture, image/barcode processing, match confirmation, manual search, logging, detail, analytics, AI insights, collection, settings, and View All screens. |
| `ui/components/` | Shared Compose components, buttons, cards, rating controls, active timed-session banner, and navigation chrome. |
| `ui/screens/` | Home, analytics, AI insights, collection, capture, image/barcode processing, match confirmation, manual search, session logging, record detail, integration settings, View All lists, grouped timed-session history, and small screen-specific formatters. |
| `ui/theme/` | Compose colors, typography, shapes, spacing, and app theme. |

### Android Runtime Notes

- Camera capture uses `androidx.core.content.FileProvider` with `res/xml/file_paths.xml` for temporary image URIs.
- The Home screen loads `GET /api/v1/sessions/summary` and falls back to `MockVinylData` if the backend is unavailable.
- `VinylNavHost` loads active timed sessions with `GET /api/v1/sessions/groups/active`, starts sessions with `POST /api/v1/sessions/groups`, finishes sessions with `PATCH /api/v1/sessions/groups/{group_id}/finish`, and shows the global active-session banner outside the identify flow.
- The Analytics screen loads the `/api/v1/analytics/*` chart endpoints and falls back to local mock dashboard data when the backend is unavailable.
- The Recent Sessions, Top Records, Mood Distribution, and Style Distribution expanded screens live in `ViewAllScreens.kt`; list-style screens show up to 25 sessions or records, while distribution screens show the full loaded distribution.
- View All Recent Sessions groups fetched rows with the same `session_group_id` into a green outlined timed-session container with metadata chips. Grouping applies to the loaded page window, so a very long timed session can continue on the next page if its rows cross a pagination boundary.
- Settings calls `GET /api/v1/integrations/discogs`, `PUT /api/v1/integrations/discogs/token`, and `DELETE /api/v1/integrations/discogs/token` for Discogs token state, identity validation, token removal, and source-of-truth controls.
- The Records Collection screen starts `POST /api/v1/collection/sync`, polls `GET /api/v1/collection/sync/{job_id}`, loads active records with `GET /api/v1/collection/releases?limit=25&offset=0`, and searches only active local collection records with `GET /api/v1/collection/search`. Discogs sync actions are hidden until a saved token exists. Discogs folder filters come from `GET /api/v1/collection/folders`; the action menu shows 10 folders plus a `View all folders` route when more folders exist. The add camera CTA launches identify with `flowMode=collection_add`; confirming a Discogs-only candidate fetches the full release on-device, imports it through `POST /api/v1/releases/import/client-discogs`, reactivates collection membership, and opens Record Detail.
- Manual search uses `DiscogsApiClient` for direct device-side Discogs search, paginates in 10-result pages, fetches the selected full release on the device, imports that payload through the backend, and displays the release format returned by Discogs.
- Capture can enter barcode scan mode on the existing CameraX preview. ML Kit bundled barcode scanning reads UPC/EAN frames locally, shows a short captured confirmation, then opens barcode processing.
- Image Processing starts `POST /api/v1/identify/jobs`, polls `GET /api/v1/identify/jobs/{job_id}`, blocks normal back navigation while active, and sends `POST /api/v1/identify/jobs/{job_id}/cancel` from the top-left cancel action.
- Barcode processing uses `DiscogsApiClient` for direct device-side barcode search, shows the same green processing language, routes successful candidates to Match Confirmation, fetches the confirmed full release on the device, and offers Try Again, Manual Search with the barcode prefilled, or Cancel on no result, API failure, or timeout.
- Session logging uses release-provided side options so repeated side names across discs can display friendly labels while saving unique option values.
- Session logging can optionally attach a listen to the active timed session when auto-add is enabled, sending the active `session_group_id` with the regular side/rating/mood payload.
- `RelativeDateFormatter.kt` prefers backend `played_at` timestamps for device-timezone-aware compact labels such as `Today`, `1d`, `1w`, and `1m`; date strings remain a fallback.
- Local Android unit tests live under `android-app/app/src/test/`; focused coverage includes API retry policy, identify job state parsing, collection API parsing, navigation saved-state encoding, analytics month padding, match confirmation selection, relative date labels, historical collection states, and side-option selection.
- Android navigation smoke coverage lives under `android-app/app/src/androidTest/`.

## Source Of Truth

- API behavior: `backend/app/api/routes/` and `backend/app/schemas/`.
- Business workflows: `backend/app/services/`.
- Identification internals: `backend/app/pipelines/identification/`.
- Database schema intent: `backend/app/models/`, `backend/alembic/`, and `docs/architecture/database-schema.md`.
- Current feature explanations: `docs/features/`.
