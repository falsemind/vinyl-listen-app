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
│   ├── router.py
│   └── routes/
│       ├── ai.py
│       ├── analytics.py
│       ├── health.py
│       ├── identify.py
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
│   ├── discogs_release_cache.py
│   ├── identify_job.py
│   ├── releases.py
│   ├── sessions.py
│   ├── sessions_moods.py
│   └── spotify_listening.py
├── pipelines/
│   └── identification/
├── repositories/
│   ├── ai_chat_repository.py
│   ├── analytics_repository.py
│   ├── discogs_release_repository.py
│   ├── identify_job_repository.py
│   ├── releases_repository.py
│   ├── session_groups_repository.py
│   ├── sessions_moods_repository.py
│   ├── sessions_repository.py
│   └── spotify_listening_repository.py
├── schemas/
│   ├── ai.py
│   ├── analytics.py
│   ├── identify.py
│   ├── releases.py
│   └── sessions.py
├── services/
│   ├── ai_insights_service.py
│   ├── analytics_service.py
│   ├── discogs_service.py
│   ├── identify_job_service.py
│   ├── identify_service.py
│   ├── release_import_service.py
│   ├── release_mapper.py
│   ├── session_groups_service.py
│   ├── sessions_service.py
│   ├── spotify_listening_import_service.py
│   └── spotify_listening_rollup_service.py
└── utils/
```

| Layer | Responsibility |
| --- | --- |
| `main.py` | Creates the FastAPI app, attaches `/api/v1`, applies inbound API rate limiting, handles validation errors, and logs runtime dependency status during startup. |
| `ai/` | AI runtime adapters owned by the backend, currently disabled fallback plus LM Studio native chat and OpenAI-compatible chat completions support. |
| `api/router.py` | Registers versioned route modules under `/health`, `/identify`, `/releases`, `/collection`, `/sessions`, `/analytics`, and `/ai`. |
| `api/routes/` | HTTP boundary. Routes read request data, inject database sessions and services, and map service errors to HTTP responses. |
| `core/` | Configuration, logging, inbound rate-limit policies, and optional runtime dependency checks. |
| `database/` | SQLAlchemy base, engine/session setup, and request-scoped DB dependency. |
| `models/` | SQLAlchemy tables for releases, Discogs cache rows, identify jobs, collection sync jobs, AI chat history, timed session groups, listening sessions, moods, and Spotify listening imports/rollups. |
| `repositories/` | Database access methods. Repositories keep SQLAlchemy queries out of services and routes. |
| `schemas/` | Pydantic request/response models exposed by the API. |
| `services/` | Business workflows: AI insights chat, analytics, identification, identify job progress, Discogs access/cache, collection sync, release import, release mapping, timed session groups, listening sessions, and Spotify listening imports/rollups. |
| `pipelines/identification/` | Image preprocessing, OCR, barcode detection, identifier parsing, search planning, and candidate ranking. |

### API Route Map

All routes are nested under `/api/v1`.

| Route | Handler module | Main service |
| --- | --- | --- |
| `GET /health` | `api/routes/health.py` | Runtime/database health checks. |
| `GET /health/runtime` | `api/routes/health.py` | Optional dependency status. |
| `POST /identify` | `api/routes/identify.py` | `IdentifyService` plus identify admission guard. |
| `POST /identify/jobs` | `api/routes/identify.py` | `IdentifyJobService` with per-client admission control. |
| `GET /identify/jobs/{job_id}` | `api/routes/identify.py` | `IdentifyJobService`. |
| `POST /collection/sync` | `api/routes/collection.py` | `CollectionSyncJobService`. |
| `GET /collection/sync/{job_id}` | `api/routes/collection.py` | `CollectionSyncJobService`. |
| `GET /collection/releases` | `api/routes/collection.py` | `ReleasesRepository`. |
| `GET /collection/search` | `api/routes/collection.py` | Collection-only internal release search. |
| `GET /releases` | `api/routes/releases.py` | Release listing placeholder/current route behavior. |
| `GET /releases/search` | `api/routes/releases.py` | Manual Discogs release search. |
| `POST /releases/import` | `api/routes/releases.py` | `ReleaseImportService`. |
| `GET /releases/{release_id}` | `api/routes/releases.py` | `ReleaseImportService`. |
| `POST /releases/{release_id}/refresh` | `api/routes/releases.py` | `ReleaseImportService`. |
| `GET /releases/{release_id}/sessions` | `api/routes/releases.py` | `SessionsService`. |
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
| `POST /ai/chat` | `api/routes/ai.py` | `AiInsightsService` grounded chat service. |
| `POST /ai/spotify/import` | `api/routes/ai.py` | `SpotifyListeningImportService`. |

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
| `repositories/` | Real repository SQL coverage, including dialect-specific analytics queries. |
| `services/` | Analytics, Discogs client/service, collection sync, collection sync jobs, identify service, identify job service, release import, release mapper, session groups service, sessions service, and Home summary aggregation. |
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
| `data/api/` | Lightweight HTTP client for identify jobs, manual search, release import/detail/refresh/history, session create, timed session groups, Home summary, analytics calls, and safe GET retry/backoff behavior. |
| `domain/` | UI-facing domain models for records, release side options, sessions, timed session groups, candidates, Home summaries, and analytics dashboard data. |
| `navigation/` | Compose navigation host, active timed-session state, and route helpers for Home, capture, processing, match confirmation, manual search, logging, detail, analytics, AI insights, collection, settings, and View All screens. |
| `ui/components/` | Shared Compose components, buttons, cards, rating controls, active timed-session banner, and navigation chrome. |
| `ui/screens/` | Home, analytics, AI insights, collection, capture, processing, match confirmation, manual search, session logging, record detail, settings placeholder, View All lists, grouped timed-session history, and small screen-specific formatters. |
| `ui/theme/` | Compose colors, typography, shapes, spacing, and app theme. |

### Android Runtime Notes

- Camera capture uses `androidx.core.content.FileProvider` with `res/xml/file_paths.xml` for temporary image URIs.
- The Home screen loads `GET /api/v1/sessions/summary` and falls back to `MockVinylData` if the backend is unavailable.
- `VinylNavHost` loads active timed sessions with `GET /api/v1/sessions/groups/active`, starts sessions with `POST /api/v1/sessions/groups`, finishes sessions with `PATCH /api/v1/sessions/groups/{group_id}/finish`, and shows the global active-session banner outside the identify flow.
- The Analytics screen loads the `/api/v1/analytics/*` chart endpoints and falls back to local mock dashboard data when the backend is unavailable.
- The Recent Sessions, Top Records, Mood Distribution, and Style Distribution expanded screens live in `ViewAllScreens.kt`; list-style screens show up to 25 sessions or records, while distribution screens show the full loaded distribution.
- View All Recent Sessions groups fetched rows with the same `session_group_id` into a green outlined timed-session container with metadata chips. Grouping applies to the loaded page window, so a very long timed session can continue on the next page if its rows cross a pagination boundary.
- The Records Collection screen starts `POST /api/v1/collection/sync`, polls `GET /api/v1/collection/sync/{job_id}`, loads active records with `GET /api/v1/collection/releases?limit=25&offset=0`, and searches only active local collection records with `GET /api/v1/collection/search`.
- Manual search calls `GET /api/v1/releases/search`, paginates in 10-result pages, imports selected Discogs candidates, and displays the release format returned by the backend.
- The Processing screen starts `POST /api/v1/identify/jobs`, polls `GET /api/v1/identify/jobs/{job_id}`, blocks normal back navigation while active, and sends `POST /api/v1/identify/jobs/{job_id}/cancel` from the top-left cancel action.
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
