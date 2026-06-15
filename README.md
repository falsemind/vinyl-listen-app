# Vinyl Listening App

A mobile-first system for **identifying vinyl records from photos and logging listening sessions**.

![identify and session logging flow](docs/product/IdentifyAndLogSessionFlow.jpg)

The project consists of:

* **Android application** built with Kotlin + Jetpack Compose
* **Backend API** built with FastAPI
* **Discogs integration** for vinyl metadata
* **PostgreSQL database** for storing releases and listening sessions

This repository is organized as a **monorepo** containing both the backend and the Android application.

---

# Project Architecture

```
vinyl-listen-app/
│
├── backend/        # FastAPI backend service
│
├── android-app/    # Android mobile application
│
├── docs/           # Architecture and product documentation
│
├── scripts/        # Helper scripts for development
│
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

# Technology Stack

## Backend

* Python
* FastAPI
* SQLAlchemy
* Alembic
* PostgreSQL
* Discogs API

## Android

* Kotlin
* Jetpack Compose
* CameraX
* Retrofit
* Compose Navigation

---

# Core MVP Features

### Record Identification

Users can take a photo of a vinyl record sleeve or label.

The backend attempts to identify the record using:

* barcode detection
* OCR text extraction
* Discogs search

The system returns a list of candidate releases for confirmation.

---

### Release Metadata

Once confirmed, the app imports metadata from Discogs including:

* artist
* title
* label
* year
* genres
* styles
* cover art

Releases are stored locally in the backend database.

---

### Listening Sessions

Users can log listening sessions with:

* rating
* mood
* notes
* vinyl side
* timestamp

These sessions build a personal listening history.

---

### Listening Analytics

The system aggregates listening data to provide insights such as:

* most played artists
* most played genres
* listening activity over time

Charts are rendered in the Android app using Compose charts.

---

# Backend Setup

## Requirements

* Python 3.13+
* Docker and Docker Compose
* PostgreSQL if you are not using Docker

---

## Docker Setup

The repository root keeps `docker-compose.yml` because it orchestrates project-level services in this monorepo.

### 1. Configure environment variables

Create a root `.env` file or export these variables in your shell:

Generate `DISCOGS_TOKEN_ENCRYPTION_KEY` with `openssl rand -base64 32` and keep it stable across backend restarts so saved Discogs tokens remain decryptable.

```env
DISCOGS_TOKEN_ENCRYPTION_KEY=generate_with_openssl_rand_base64_32
DISCOGS_BASE_URL=https://api.discogs.com
IDENTIFY_OCR_BACKEND=auto
IDENTIFY_MLX_VLM_SERVICE_URL=http://host.docker.internal:8111
IDENTIFY_MLX_VLM_ENDPOINT_PATH=/v1/chat/completions
IDENTIFY_MLX_VLM_MODEL_NAME=PaddlePaddle/PaddleOCR-VL-1.5
LOG_LEVEL=DEBUG
```

Docker Compose creates two local PostgreSQL databases:

* `vinyl_dev` for development and test work
* `vinyl_collection` for real listening-session data collection

Set `DATABASE_PROFILE=dev` or `DATABASE_PROFILE=collection` before launching the backend. `DATABASE_URL` can still be set as an explicit one-off override.
The `postgres-init` service idempotently creates both databases, including when an older local Docker volume already exists.
`IDENTIFY_MLX_VLM_SERVICE_URL` points the backend container to a VLM server running on the host machine.

### 2. Start the local VLM OCR server

The backend calls an external OpenAI-compatible vision model server for the `mlx_vlm` OCR path. Start it before testing image identification:

```bash
python3 -m venv .venv-mlx-vlm
source .venv-mlx-vlm/bin/activate
pip install mlx-vlm
```

```bash
mlx_vlm.server --host 127.0.0.1 --port 8111 --model PaddlePaddle/PaddleOCR-VL-1.5 --trust-remote-code
```

Any compatible VLM server can be used if it exposes `/v1/chat/completions`. For example, a local `vllm serve ... --port 8111` process can be used with the same backend URL settings.

### 3. Start the backend and database

From the repository root:

```bash
docker compose up --build
```

To collect real listening-session data, point the backend at the collection database:

```bash
DATABASE_PROFILE=collection docker compose up --build backend
```

This starts:

* `postgres` on `localhost:5432`
* `backend` on `http://localhost:8000`

The backend container installs both `tesseract-ocr` and `zbar`, so OCR and barcode detection work without any macOS-specific setup.
The VLM model itself is not run inside the backend container; keep the local server running separately.

### 4. Check runtime dependencies

You can verify runtime dependency availability with:

```bash
curl http://localhost:8000/api/v1/health/runtime
```

You should also see startup log lines showing whether `tesseract`, `zbar`, and the configured `mlx_vlm_service` are available.
For quieter logs later, set `LOG_LEVEL=INFO` in the root `.env`.

---

## Local Backend Setup

### 1. Start Database

From the repository root:

```bash
docker compose up -d postgres postgres-init
```

This launches PostgreSQL with both `vinyl_dev` and `vinyl_collection` available.

### 2. Create Python Virtual Environment

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip poetry
POETRY_VIRTUALENVS_CREATE=false poetry install --only main --no-root
```

### 4. Environment Variables

Create `backend/.env`:

Generate `DISCOGS_TOKEN_ENCRYPTION_KEY` with `openssl rand -base64 32` and keep it stable across backend restarts so saved Discogs tokens remain decryptable.

```env
DATABASE_PROFILE=dev
DATABASE_DEV_URL=postgresql://vinyl:vinyl@localhost:5432/vinyl_dev
DATABASE_COLLECTION_URL=postgresql://vinyl:vinyl@localhost:5432/vinyl_collection
DISCOGS_TOKEN_ENCRYPTION_KEY=generate_with_openssl_rand_base64_32
DISCOGS_BASE_URL=https://api.discogs.com
API_RATE_LIMIT_PER_MINUTE=60
IDENTIFY_OCR_BACKEND=auto
IDENTIFY_MLX_VLM_SERVICE_URL=http://localhost:8111
IDENTIFY_MLX_VLM_ENDPOINT_PATH=/v1/chat/completions
IDENTIFY_MLX_VLM_MODEL_NAME=PaddlePaddle/PaddleOCR-VL-1.5
AI_CHAT_ENABLED=false
AI_CHAT_BASE_URL=http://localhost:1234
AI_CHAT_ENDPOINT_PATH=/api/v1/chat
AI_CHAT_MODEL=local-model-name
AI_CHAT_API_KEY=
LOG_LEVEL=INFO
```

When the backend runs in Docker and LM Studio runs on the host machine, use `AI_CHAT_BASE_URL=http://host.docker.internal:1234` instead of `localhost`. Inside the backend container, `localhost` points at the container itself.

### 5. Start the local VLM OCR server

Use the same external server from the Docker setup. If it is not already running, start it in a separate terminal:

```bash
mlx_vlm.server --host 127.0.0.1 --port 8111 --model PaddlePaddle/PaddleOCR-VL-1.5 --trust-remote-code
```

The backend only needs an OpenAI-compatible `/v1/chat/completions` endpoint. If you use another server, keep `IDENTIFY_MLX_VLM_SERVICE_URL` pointed at its base URL.

### 6. Run Backend Server

```bash
cd backend
source venv/bin/activate
alembic upgrade head
uvicorn app.main:app --reload
```

Use `DATABASE_PROFILE=collection alembic upgrade head` and `DATABASE_PROFILE=collection uvicorn app.main:app --reload` when you intentionally want the collection database.

Server will start at `http://localhost:8000`

API documentation is available at `http://localhost:8000/docs`

If you run the backend outside Docker, make sure the host machine also has the native `tesseract` binary and `zbar` shared library installed.

---

# Android Setup

## Requirements

* Android Studio Hedgehog or newer
* Android SDK 34+
* Kotlin support enabled

---

## Open Project

Open the Android project located at:

```
android-app/
```

Android Studio will automatically configure Gradle and dependencies.

---

## Running the App

Run the application using:

* Android Emulator
* Physical Android device

During development the backend API should be accessed via:

```
http://10.0.2.2:8000
```

This address allows the Android emulator to reach the host machine.

For a physical device connected over USB, reverse the backend port and build the
debug app with a localhost base URL:

```
adb reverse tcp:8000 tcp:8000
export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
VINYL_API_BASE_URL=http://localhost:8000/api/v1 ./gradlew :app:installDebug
```

You can also put either `vinylApiBaseUrl=http://localhost:8000/api/v1` or
`VINYL_API_BASE_URL=http://localhost:8000/api/v1` in
`android-app/local.properties`, then rebuild and reinstall the app. The value is
compiled into `BuildConfig`, so changing `local.properties` does not affect an
already installed APK.

---

# API Overview

Main backend endpoints:

### Identify Record

```
POST /api/v1/identify
```

Upload a record photo as multipart form data with the `image` field to detect candidate releases.

---

### Import Release

```
POST /api/v1/releases/import
```

Import Discogs release metadata into the local database.

---

### Get Release

```
GET /api/v1/releases/{release_id}
```

Retrieve stored release metadata.

---

### Refresh Release

```
POST /api/v1/releases/{release_id}/refresh
```

Fetch full Discogs metadata for one stored release and update the local database/cache.

---

### Create Listening Session

```
POST /api/v1/sessions/
PATCH /api/v1/sessions/{session_id}
```

Log a new listening session, or edit side/rating/mood/notes during the 15-minute server-enforced edit window.

---

### Analytics

```
GET /api/v1/analytics/plays/monthly
GET /api/v1/analytics/top-records
GET /api/v1/analytics/rating-distribution
GET /api/v1/analytics/mood-distribution
GET /api/v1/analytics/style-distribution
GET /api/v1/analytics/sessions
GET /api/v1/analytics/records/by-rating
GET /api/v1/analytics/records/by-mood
GET /api/v1/analytics/records/by-style
```

Retrieve dashboard chart data and paginated drilldowns for month, rating, mood, and style selections.

---

### Runtime Health

```
GET /api/v1/health/runtime
```

Inspect whether runtime OCR and barcode dependencies are available.

---

# Development Workflow

Typical development loop:

1. Start PostgreSQL with Docker
2. Run backend locally
3. Run Android app in emulator
4. Test full capture → identify → session logging flow

---

# Documentation

Detailed documentation is located in:

```
docs/
```

Key documents include:

* MVP Screen Specification
* Android Navigation Graph
* Backend API Specification
* Database Schema
* Project Roadmap

---

# Future Enhancements

Planned improvements beyond MVP:

* improved record identification accuracy
* multi-user auth, registration, and account-scoped integrations
* deeper collection-management workflows
* social listening features
* advanced analytics
* cloud deployment

---

# License

This project is for personal use and experimentation only. Commercial use is strictly prohibited.
