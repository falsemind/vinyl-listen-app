# Vinyl Listen App Repository Structure

This document describes the current monorepo layout. All project documentation lives under `docs/`.

## Top-Level Layout

```text
.
├── AGENTS.md
├── README.md
├── android-app/
├── backend/
├── docker-compose.yml
├── docs/
└── scripts/
```

| Path | Purpose |
| --- | --- |
| `android-app/` | Android client project. Currently a Gradle/Kotlin app with a starter Compose activity and theme resources. |
| `backend/` | FastAPI backend, database models, repositories, service layer, identification pipeline, migrations, tests, and backend scripts. |
| `docs/` | Product, architecture, implementation, research, and feature documentation. |
| `scripts/` | Repository-level helper scripts. |
| `docker-compose.yml` | Local container orchestration entry point. |
| `AGENTS.md` | Agent workflow and repository guidance. |

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
│   └── release-import-metadata-api-plan.md
├── product/
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
| `product/` | Product-facing screen and MVP specifications. |
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
│   ├── discogs_release_repository.py
│   ├── releases_repository.py
│   ├── sessions_moods_repository.py
│   └── sessions_repository.py
├── schemas/
│   ├── identify.py
│   ├── releases.py
│   └── sessions.py
├── services/
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
| `services/` | Business workflows: identification, Discogs access/cache, release import, release mapping, and listening sessions. |
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
| `GET /sessions/{session_id}` | `api/routes/sessions.py` | `SessionsService`. |
| `GET /analytics` | `api/routes/analytics.py` | Analytics endpoint placeholder/current route behavior. |

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
├── services/
├── conftest.py
├── pytest.ini
└── test-automation-structure.md
```

| Folder | Coverage |
| --- | --- |
| `api/` | FastAPI route behavior and versioned paths. |
| `core/` | Runtime dependency reporting. |
| `fixtures/` | Test clients, database fixtures, and service stubs. |
| `migrations/` | Alembic/schema expectations. |
| `pipelines/` | Identification pipeline units: preprocessing, OCR, parsing, search planning, evidence scoring, and ranking. |
| `services/` | Discogs client/service, identify service, release import, release mapper, and sessions service. |
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

```text
android-app/
├── build.gradle.kts
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
│       │   │   └── ui/theme/
│       │   │       ├── Color.kt
│       │   │       ├── Theme.kt
│       │   │       └── Type.kt
│       │   └── res/
│       ├── test/
│       └── androidTest/
└── gradle/
    ├── libs.versions.toml
    └── wrapper/
```

The Android app is still small compared with the backend. It contains a single main activity, Compose theme files, launcher resources, unit test scaffold, and instrumentation test scaffold.

## Source Of Truth

- API behavior: `backend/app/api/routes/` and `backend/app/schemas/`.
- Business workflows: `backend/app/services/`.
- Identification internals: `backend/app/pipelines/identification/`.
- Database schema intent: `backend/app/models/`, `backend/alembic/`, and `docs/architecture/database-schema.md`.
- Current feature explanations: `docs/features/`.
