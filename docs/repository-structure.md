---
name: repository-structure
description: This document describes the current monorepo layout. Use this when need a quick reference to find a specific file or directory.
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
└── scripts/
```

| Path | Purpose |
| --- | --- |
| `android-app/` | Android client project. Gradle/Kotlin Compose app with navigation, prototype screens, backend API integration, camera/gallery input, and Android tests. |
| `backend/` | FastAPI backend, database models, repositories, service layer, identification pipeline, migrations, tests, and backend scripts. |
| `docs/` | Product, architecture, implementation, research, and feature documentation. |
| `scripts/` | Repository-level helper scripts. |
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
│   └── identification-pipeline.md
├── implementation-plans/
│   ├── discogs-integration-plan.md
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
├── api/
│   ├── router.py
│   └── routes/
│       ├── analytics.py
│       ├── health.py
│       ├── identify.py
│       ├── releases.py
│       └── sessions.py
├── core/
│   ├── config.py
│   ├── logging.py
│   └── runtime_dependencies.py
├── database/
│   ├── base.py
│   ├── db.py
│   └── session.py
├── models/
│   ├── discogs_release_cache.py
│   ├── releases.py
│   ├── sessions.py
│   └── sessions_moods.py
├── pipelines/
│   └── identification/
├── repositories/
│   ├── analytics_repository.py
│   ├── discogs_release_repository.py
│   ├── releases_repository.py
│   ├── sessions_moods_repository.py
│   └── sessions_repository.py
├── schemas/
│   ├── analytics.py
│   ├── identify.py
│   ├── releases.py
│   └── sessions.py
├── services/
│   ├── analytics_service.py
│   ├── discogs_service.py
│   ├── identify_service.py
│   ├── release_import_service.py
│   ├── release_mapper.py
│   └── sessions_service.py
└── utils/
```

| Layer | Responsibility |
| --- | --- |
| `main.py` | Creates the FastAPI app, attaches `/api/v1`, handles validation errors, and logs runtime dependency status during startup. |
| `api/router.py` | Registers versioned route modules under `/health`, `/identify`, `/releases`, `/sessions`, and `/analytics`. |
| `api/routes/` | HTTP boundary. Routes read request data, inject database sessions and services, and map service errors to HTTP responses. |
| `core/` | Configuration, logging, and optional runtime dependency checks. |
| `database/` | SQLAlchemy base, engine/session setup, and request-scoped DB dependency. |
| `models/` | SQLAlchemy tables for releases, Discogs cache rows, listening sessions, and moods. |
| `repositories/` | Database access methods. Repositories keep SQLAlchemy queries out of services and routes. |
| `schemas/` | Pydantic request/response models exposed by the API. |
| `services/` | Business workflows: analytics, identification, Discogs access/cache, release import, release mapping, and listening sessions. |
| `pipelines/identification/` | Image preprocessing, OCR, barcode detection, identifier parsing, search planning, and candidate ranking. |

### API Route Map

All routes are nested under `/api/v1`.

| Route | Handler module | Main service |
| --- | --- | --- |
| `GET /health` | `api/routes/health.py` | Runtime/database health checks. |
| `GET /health/runtime` | `api/routes/health.py` | Optional dependency status. |
| `POST /identify` | `api/routes/identify.py` | `IdentifyService`. |
| `GET /releases` | `api/routes/releases.py` | Release listing placeholder/current route behavior. |
| `POST /releases/import` | `api/routes/releases.py` | `ReleaseImportService`. |
| `GET /releases/{release_id}` | `api/routes/releases.py` | `ReleaseImportService`. |
| `GET /releases/{release_id}/sessions` | `api/routes/releases.py` | `SessionsService`. |
| `POST /sessions` | `api/routes/sessions.py` | `SessionsService`. |
| `GET /sessions/summary` | `api/routes/sessions.py` | `SessionsService` home summary aggregation. |
| `GET /sessions/{session_id}` | `api/routes/sessions.py` | `SessionsService`. |
| `GET /analytics/plays/monthly` | `api/routes/analytics.py` | `AnalyticsService` monthly play counts. |
| `GET /analytics/top-records` | `api/routes/analytics.py` | `AnalyticsService` top record aggregation. |
| `GET /analytics/rating-distribution` | `api/routes/analytics.py` | `AnalyticsService` rating frequency aggregation. |
| `GET /analytics/mood-distribution` | `api/routes/analytics.py` | `AnalyticsService` mood frequency aggregation. |

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
| `services/` | Analytics, Discogs client/service, identify service, release import, release mapper, sessions service, and Home summary aggregation. |
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
│       │   │   │       └── VinylApiClient.kt
│       │   │   ├── domain/
│       │   │   │   └── RecordModels.kt
│       │   │   ├── navigation/
│       │   │   │   ├── VinylNavHost.kt
│       │   │   │   └── VinylRoutes.kt
│       │   │   └── ui/
│       │   │       ├── components/
│       │   │       ├── screens/
│       │   │       │   ├── AnalyticsScreen.kt
│       │   │       │   ├── CaptureRecordScreen.kt
│       │   │       │   ├── HomeScreen.kt
│       │   │       │   ├── ManualSearchScreen.kt
│       │   │       │   ├── MatchConfirmationScreen.kt
│       │   │       │   ├── PlaceholderScreen.kt
│       │   │       │   ├── ProcessingScreen.kt
│       │   │       │   ├── RecordDetailScreen.kt
│       │   │       │   ├── RecordDisplayFormatters.kt
│       │   │       │   ├── RelativeDateFormatter.kt
│       │   │       │   ├── ScreenPreviews.kt
│       │   │       │   └── SessionLoggingScreen.kt
│       │   │       └── theme/
│       │   └── res/
│       │       └── xml/
│       │           └── file_paths.xml
│       ├── test/
│       └── androidTest/
└── gradle/
    ├── libs.versions.toml
    └── wrapper/
```

`android-app/local.properties` is local-only and ignored by Git. It can override `vinylApiBaseUrl` for non-emulator testing. The default debug base URL remains `http://10.0.2.2:8000/api/v1`, which targets the host machine from the Android emulator.

### Android Source Packages

| Package | Responsibility |
| --- | --- |
| `data/` | Prototype fallback data and backend API client code. |
| `data/api/` | Lightweight HTTP client for identify, release import/detail/history, session create, Home summary, and analytics calls. |
| `domain/` | UI-facing domain models for records, sessions, candidates, Home summaries, and analytics dashboard data. |
| `navigation/` | Compose navigation host and route helpers. |
| `ui/components/` | Shared Compose components, buttons, cards, rating controls, and navigation chrome. |
| `ui/screens/` | Home, analytics, capture, processing, match confirmation, manual search, session logging, record detail, placeholders, and small screen-specific formatters. |
| `ui/theme/` | Compose colors, typography, shapes, spacing, and app theme. |

### Android Runtime Notes

- Camera capture uses `androidx.core.content.FileProvider` with `res/xml/file_paths.xml` for temporary image URIs.
- The Home screen loads `GET /api/v1/sessions/summary` and falls back to `MockVinylData` if the backend is unavailable.
- The Analytics screen loads the `/api/v1/analytics/*` chart endpoints and falls back to local mock dashboard data when the backend is unavailable.
- `RelativeDateFormatter.kt` formats backend date strings for compact UI labels such as `Today`, `1d`, `1w`, and `1m`.
- Local Android unit tests live under `android-app/app/src/test/`; current formatter coverage is in `ui/screens/RelativeDateFormatterTest.kt`.
- Android navigation smoke coverage lives under `android-app/app/src/androidTest/`.

## Source Of Truth

- API behavior: `backend/app/api/routes/` and `backend/app/schemas/`.
- Business workflows: `backend/app/services/`.
- Identification internals: `backend/app/pipelines/identification/`.
- Database schema intent: `backend/app/models/`, `backend/alembic/`, and `docs/architecture/database-schema.md`.
- Current feature explanations: `docs/features/`.
