# Vinyl Listening App - Repository Structure Specification (MVP)

## Purpose

Define a clear repository structure for both:

* **Backend service (FastAPI)**
* **Android application (Kotlin + Jetpack Compose)**

A consistent structure ensures:

* maintainable codebase
* predictable module boundaries
* easier onboarding
* simpler testing
* scalable architecture as the project grows


---

# Top-Level Repository Structure

```
vinyl-listening-app/
│
├── backend/
│
├── android-app/
│
├── docs/
│
├── scripts/
│
├── .gitignore
├── README.md
└── docker-compose.yml
```

### Directory Purpose

| Directory   | Purpose                              |
| ----------- | ------------------------------------ |
| backend     | FastAPI backend service              |
| android-app | Android mobile application           |
| docs        | Architecture specs and planning docs |
| scripts     | Dev utilities and helper scripts     |

---

# Documentation Folder

All planning artifacts live here.

```
docs/
│
├── repository-structure.md  # this document
│
├── architecture/
│   ├── api-spec.md
│   ├── database-schema.md
│   ├── navigation-graph.md
│   ├── matching-pipeline.md
│   └── roadmap.md
│
└── product/
    ├── mvp-screen-spec.md
    └── feature-notes.md
```

This keeps **engineering documentation versioned with code**.

---

# Backend Project Structure

Backend uses:

```
Python
FastAPI
SQLAlchemy
Alembic
PostgreSQL
```

Structure:

```
backend/
│
├── app/
│
│   ├── main.py
│
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── rate_limiter.py
│
│   ├── api/
│   │   ├── routes/
│   │   │   ├── identify.py
│   │   │   ├── releases.py
│   │   │   ├── sessions.py
│   │   │   ├── health.py
│   │   │   └── analytics.py
│   │   │
│   │   └── router.py
│
│   ├── services/
│   │   ├── discogs_service.py
│   │   ├── identification_service.py
│   │   ├── release_service.py
│   │   ├── session_service.py
│   │   └── analytics_service.py
│
│   ├── pipelines/
│   │   └── identification/
│   │       ├── preprocess.py
│   │       ├── barcode_detector.py
│   │       ├── ocr_extractor.py
│   │       ├── identifier_parser.py
│   │       └── candidate_ranker.py
│
│   ├── models/
│   │   ├── releases.py
│   │   ├── sessions.py
│   │   ├── sessions_moods.py
│   │   └── discogs_release_cache.py
│
│   ├── schemas/
│   │   ├── releases_schema.py
│   │   ├── sessions_schema.py
│   │   └── analytics_schema.py
│
│   ├── repositories/
│   │   ├── releases_repository.py
│   │   ├── sessions_repository.py
│   │   └── discogs_release_repository.py
│
│   ├── database/
│   │   ├── db.py
│   │   └── base.py
│
│   └── utils/
│       ├── image_utils.py
│       └── text_utils.py
│
├── alembic/
│
├── tests/
│
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
└── Dockerfile
```

---

# Backend Layer Responsibilities

### API Layer

```
api/routes
```

Responsible for:

```
HTTP request handling
validation
response formatting
```

Example endpoints:

```
POST /identify
POST /releases/import
POST /sessions
GET /analytics/summary
```

---

### Service Layer

```
services/
```

Contains business logic:

```
Discogs integration
release import
session creation
analytics computation
```

Services coordinate:

```
repositories
external APIs
pipelines
```

---

### Repository Layer

```
repositories/
```

Responsible for:

```
database operations
query abstraction
```

Example:

```
release_repository
session_repository
```

---

### Pipeline Layer

```
pipelines/identification/
```

Encapsulates the image identification system.

Modules:

```
preprocess.py
barcode_detector.py
ocr_extractor.py
identifier_parser.py
candidate_ranker.py
```

This keeps the **image processing pipeline modular**.

---

# Android Application Structure

Technology stack:

```
Kotlin
Jetpack Compose
Compose Navigation
CameraX
Retrofit
```

Structure:

```
android-app/
│
├── app/
│
│   └── src/main/java/com/vinylapp/
│
│       ├── MainActivity.kt
│
│       ├── navigation/
│       │   ├── NavGraph.kt
│       │   └── Routes.kt
│
│       ├── network/
│       │   ├── ApiClient.kt
│       │   ├── VinylApiService.kt
│       │   └── models/
│       │
│       ├── repository/
│       │   └── VinylRepository.kt
│
│       ├── viewmodel/
│       │   ├── CaptureViewModel.kt
│       │   ├── MatchViewModel.kt
│       │   ├── SessionViewModel.kt
│       │   ├── RecordViewModel.kt
│       │   └── AnalyticsViewModel.kt
│
│       ├── ui/
│       │   ├── screens/
│       │   │   ├── home/
│       │   │   ├── capture/
│       │   │   ├── processing/
│       │   │   ├── match/
│       │   │   ├── session/
│       │   │   ├── record/
│       │   │   ├── analytics/
│       │   │   └── settings/
│       │   │
│       │   └── components/
│       │
│       ├── camera/
│       │   └── CameraManager.kt
│
│       ├── charts/
│       │   └── ComposeCharts.kt
│
│       └── util/
│           └── Extensions.kt
│
└── build.gradle
```

---

# Android Architecture Pattern

Flow:

```
UI (Compose Screen)
      ↓
ViewModel
      ↓
Repository
      ↓
API Service
      ↓
Backend
```

Example:

```
SessionLoggingScreen
      ↓
SessionViewModel
      ↓
VinylRepository
      ↓
POST /sessions
```

---

# Network Layer

```
network/
```

Contains:

```
Retrofit client
API interfaces
network models
```

Example API:

```
identifyRecord()
createSession()
getRecordDetails()
getAnalytics()
```

---

# Camera Integration

Camera functionality isolated in:

```
camera/
```

Contains:

```
CameraX setup
image capture
image file conversion
```

Captured image is sent to:

```
POST /identify
```

---

# UI Layer

```
ui/screens/
```

Each screen has its own folder.

Example:

```
ui/screens/session/
```

Contains:

```
SessionLoggingScreen.kt
SessionLoggingView.kt
SessionLoggingState.kt
```

This keeps UI modules **self-contained**.

---

# Testing Structure

Backend tests:

```
backend/tests/
```

Types:

```
API tests
service tests
pipeline tests
```

Android tests:

```
android-app/app/src/test/
```

Types:

```
ViewModel tests
UI tests
integration tests
```

---

# Environment Configuration

Backend environment variables:

```
DATABASE_URL
DISCOGS_TOKEN
API_RATE_LIMIT
IMAGE_UPLOAD_MAX_SIZE
```

Use:

```
.env file
```

Loaded by:

```
pydantic settings
```

---

# Deployment (Future)

Possible deployment setup:

```
backend → Docker container
database → PostgreSQL
hosting → cloud VM or container platform
```

Android app distributed via:

```
APK builds (initial testing)
Play Store (later)
```

---

# Summary

This repository structure provides:

```
clear backend layering
modular image pipeline
clean Android architecture
scalable project layout
```

It supports the complete MVP feature set while remaining **simple enough for rapid development**.
