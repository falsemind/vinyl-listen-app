---
name: roadmap
description: Roadmap with scoped milestones to implement new features.
---

# Vinyl Listening App — GitHub Roadmap & Milestones (MVP)

## Purpose

Define the implementation roadmap for building the **Vinyl Listening App MVP**.

The roadmap organizes development into **milestones**, each representing a logical step toward a working system.

Development strategy:

Backend-first architecture.

This ensures:

* stable API contracts
* minimal Android rework
* predictable integration points
* incremental system validation

---

# Milestone Overview

```
M1 — Backend Project Foundation
M2 — Database & Models
M3 — Discogs Integration
M4 — Release Import & Metadata API
M5 — Listening Session API
M6 — Image Identification Pipeline
M7 — Android App Foundation
M8 — Android Feature Implementation
M9 — Analytics
M10 — MVP Stabilization
M11 — AI Insights
```

---

# Milestone 1 — Backend Project Foundation

Goal: create the backend skeleton and infrastructure.

Tasks:

```
Initialize backend repository

Setup FastAPI project structure

Configure environment variables

Setup dependency management (Poetry or pip)

Configure logging

Add basic health endpoint
```

Example issue list:

```
Create FastAPI project skeleton
Add health check endpoint
Add configuration management
Setup development environment
```

Deliverable:

```
Running FastAPI server
```

---

# Milestone 2 — Database & Models

Goal: implement the database schema.

Tasks:

```
Setup PostgreSQL connection
Configure SQLAlchemy models
Create Alembic migrations
Implement tables
```

Tables:

```
releases
sessions
session_moods
discogs_release_cache
```

Example issues:

```
Implement releases model
Implement sessions model
Add genres and styles arrays
Create Alembic initial migration
Setup database connection layer
```

Deliverable:

```
Working database with migrations
```

---

# Milestone 3 — Discogs Integration

Goal: build the Discogs API client.

Tasks:

```
Create Discogs service module
Implement authenticated requests
Implement search endpoints
Implement release metadata fetch
Add rate limiting
```

Example issues:

```
Implement Discogs API client
Add token authentication
Implement barcode search
Implement catalog number search
Implement artist/title search
Add API throttling
```

Deliverable:

```
Stable Discogs integration service
```

---

# Milestone 4 — Release Import & Metadata API

Goal: allow importing Discogs releases into the local database.

Endpoints:

```
POST /releases/import
GET /releases/{release_id}
```

Tasks:

```
Implement release import logic
Fetch metadata from Discogs
Store release metadata locally
Store genres and styles
Cache Discogs JSON payload
```

Example issues:

```
Create release importer service
Add Discogs cache table integration
Implement /releases/import endpoint
Implement release retrieval endpoint
```

Deliverable:

```
Release metadata storage working
```

---

# Milestone 5 — Listening Session API

Goal: implement session logging.

Endpoints:

```
POST /sessions
GET /sessions/summary
GET /sessions/{session_id}
GET /releases/{release_id}/sessions
```

Tasks:

```
Create session service
Validate release references
Implement mood handling
Store session notes
Implement Home summary aggregation
```

Example issues:

```
Create sessions API endpoint
Add rating validation
Add mood support
Implement session retrieval
Implement sessions summary endpoint for Android Home
```

Deliverable:

```
Listening sessions can be stored, retrieved, and summarized for Home
```

---

# Milestone 6 — Image Identification Pipeline

Goal: identify records from photos.

Endpoint:

```
POST /identify
```

Pipeline stages:

```
image upload
image preprocessing
barcode detection
OCR fallback
Discogs search
candidate ranking
```

Tasks:

```
Implement image upload endpoint
Add preprocessing pipeline
Integrate barcode detection
Integrate OCR extraction
Implement candidate ranking
Return candidate releases
```

Example issues:

```
Create identify endpoint
Add barcode detection module
Add OCR module
Implement identifier parsing
Implement Discogs search pipeline
```

Deliverable:

```
Photo identification working
```

---

# Milestone 7 — Android App Foundation

Goal: create the Android project skeleton.

Stack:

```
Kotlin
Jetpack Compose
CameraX
Compose Navigation
```

Tasks:

```
Create Android project
Implement navigation graph
Setup project architecture
Configure networking layer
```

Example issues:

```
Initialize Android project
Implement navigation routes
Create API client
Setup dependency injection
```

Deliverable:

```
Android project builds and runs
```

---

# Milestone 8 — Android Feature Implementation

Goal: implement MVP user flows.

Screens:

```
Home
Capture Record
Processing
Match Confirmation
Manual Search
Session Logging
Record Detail
Analytics (placeholder until M9 backend is ready)
Settings (placeholder)
```

Tasks:

```
Implement CameraX capture
Integrate identify endpoint
Display candidate matches
Implement session logging UI
Load Home data from /sessions/summary
Display record detail screen
```

Example issues:

```
Implement CaptureRecord screen
Implement MatchConfirmation screen
Implement SessionLogging screen
Implement RecordDetail screen
Wire Home screen to real session summary data
```

Deliverable:

```
Complete MVP user flow
```

---

# Milestone 9 — Analytics

Goal: implement listening statistics.

Endpoints:

```
GET /analytics/plays/monthly
GET /analytics/top-records
GET /analytics/rating-distribution
GET /analytics/mood-distribution
```

Tasks:

```
Calculate monthly play counts
Calculate most played records
Compute rating frequency
Compute mood frequency
```

Example issues:

```
Create analytics service
Add monthly plays query
Add top records query
Add rating distribution query
Add mood distribution query
```

Deliverable:

```
Backend analytics API ready for the Analytics dashboard
```

---

# Milestone 10 — MVP Stabilization

Goal: prepare the application for real-world testing.

Tasks:

```
Improve error handling
Optimize performance
Improve logging
Add request validation
Add API documentation
```

Example issues:

```
Add retry logic for Discogs API
Improve image processing reliability
Add API documentation (OpenAPI)
Add backend monitoring
```

Deliverable:

```
Stable MVP ready for testing
```

---

# Milestone 11 — AI Insights

Goal: add an AI chat assistant for collection-grounded listening insights.

Status: started.

Scope:

```
Android Insights screen
Backend AI chat API
Local model runtime adapter
Persistent chat history
Read-only insight tools
Privacy clear/export paths
```

Tasks:

```
Add Insights bottom-navigation screen
Implement chat UI with suggested prompts
Connect Android chat to backend API
Support LM Studio/OpenAI-compatible chat runtime
Persist and reload a single local chat thread
Ground answers with listening history, ratings, moods, styles, and notes
Prioritize saved session notes for recommendations and subjective insights
Expose clear and export actions for chat history
Keep recommendations limited to known local releases
```

Example issues:

```
Add AI Insights Android shell
Add backend /ai/chat endpoints
Add configurable AI chat adapter
Add persistent AI chat history
Add read-only analytics and session-note tools
Improve Insights chat navigation and lifecycle behavior
```

Deliverable:

```
AI Insights screen can answer collection-grounded questions from local listening history and notes
```

---

# Development Order Summary

Recommended sequence:

```
Backend foundation
Database
Discogs integration
Release import
Sessions API
Image identification
Android app
Analytics
Stabilization
AI Insights
```

This order minimizes development blockers.

---

# Definition of MVP Completion

The MVP is complete when the user can:

```
take photo of record
identify Discogs release
confirm correct match
log listening session
see logged sessions on Home
view listening history
see basic analytics
```

---

# Future Roadmap (Post-MVP)

Possible next milestones:

```
advanced recommendation workflows
collection management
price tracking
marketplace integration
```

These will build on the stable MVP foundation.
