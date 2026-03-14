# Vinyl Listening App

A mobile-first system for **identifying vinyl records from photos and logging listening sessions**.

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

* Python 3.10+
* Docker (recommended)
* PostgreSQL

---

## 1. Start Database

From the repository root:

```
docker compose up -d
```

This launches a PostgreSQL container used by the backend.

---

## 2. Create Python Virtual Environment

```
cd backend
python3 -m venv venv
```

Activate environment:

Mac/Linux:

```
source venv/bin/activate
```

---

## 3. Install Dependencies

```
pip install -r requirements.txt
```

---

## 4. Environment Variables

Create file:

```
backend/.env
```

Example configuration:

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vinyl
DISCOGS_TOKEN=your_discogs_token
API_RATE_LIMIT=60
IMAGE_UPLOAD_MAX_SIZE=10MB
```

---

## 5. Run Backend Server

```
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

Server will start at:

```
http://localhost:8000
```

API documentation available at:

```
http://localhost:8000/docs
```

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

---

# API Overview

Main backend endpoints:

### Identify Record

```
POST /identify
```

Upload record photo to detect candidate releases.

---

### Import Release

```
POST /releases/import
```

Import Discogs release metadata into the local database.

---

### Get Release

```
GET /releases/{release_id}
```

Retrieve stored release metadata.

---

### Create Listening Session

```
POST /sessions
```

Log a new listening session.

---

### Analytics

```
GET /analytics/summary
```

Retrieve listening statistics.

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
* Discogs OAuth authentication
* collection management
* social listening features
* advanced analytics
* cloud deployment

---

# License

This project is currently private and under active development.
