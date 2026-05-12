---
name: project-entry-point
description: Always use this for quick references when working on the tasks and need to find a specific location of a file, app's features, or documentation.
---

## Project's Main Directories

### Documentation

All project's documantion lives in - `docs/` directory where you can find and use additional docs depending on current task and information needed:
- `docs/architecture/` - High level architecture documentation like api spec, database schema, roadmap, etc.
- `docs/audit-artifacts/` - In this directory you write temporary auditing files when given such a task to do.
- `docs/features/` - Documentation for implemented features.
- `docs/implementation-plans/` - This where you write new, or update existing, plans and fetch required information when beginning a new code implementation or continue with the next phase of already started work.
- `docs/product/` - All product related documentation lives here, e.g. Android app design system, screens spec.
- `docs/research/` - When asked to do a research related to the project use this dir to write documents with findings.
- `docs/repository-structure.md` - Document with detailed project structure and directories.

### Backend

Directory `backend/` contains all the server side business logic with: Python, FastAPI, PostgreSQL.

### Android UI Client

Directory `android-app/` contains code implementation of the Android client with: Kotlin, Jetpack Compose.
