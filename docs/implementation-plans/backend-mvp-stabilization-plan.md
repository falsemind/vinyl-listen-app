# Code Implementation Plan: Milestone 10 — Backend MVP Stabilization

## Goal

Prepare the backend for real-world MVP testing without changing the Android client yet.

Milestone 10 asks for stronger error handling, performance, logging, validation, and API documentation. Backend work should start with low-risk consolidation before deeper parser refactors because the identification path already contains many OCR and Discogs edge cases.

## Source Documents

- `docs/architecture/roadmap.md`
- `docs/features/backend-services.md`
- `docs/features/identification-pipeline.md`
- `docs/architecture/matching-pipeline.md`
- `docs/architecture/api-spec.md`

## Findings

The backend identification flow is already split into focused pipeline modules, but one duplication stands out:

- `backend/app/pipelines/identification/search_planner.py` owns Discogs search step construction.
- `backend/app/services/identify_service.py` still contains a near-copy of the same search-planning helpers.
- The service now delegates `_build_search_plan()` to `build_search_plan()`, so the duplicated helpers in the service are dead or redundant.

`identifier_parser.py` is large and edge-case heavy. It should not be split in the first stabilization pass unless behavior is locked down with focused regression tests for each extracted helper group.

## Implementation Phases

| Phase | Scope | Deliverable | Risk |
| --- | --- | --- | --- |
| P1 | Remove duplicated search-planning helpers from `IdentifyService`. | One source of truth for search planning. | Low |
| P2 | Track Discogs response rate-limit headers and throttle when the observed quota is exhausted. | Header-aware Discogs throttling with local pacing fallback. | Medium |
| P3 | Review parser helper groups and extract only behavior-preserving catalog/barcode helpers with tests. | Smaller parser surface without parser behavior drift. | Medium |
| P4 | Fill OpenAPI/API documentation gaps after backend behavior is stable. | API docs aligned with implemented endpoints. | Low |

## Phase P1 Tasks

1. Import `candidates_contain_identity_context` from `search_planner.py`.
2. Remove duplicated search-planning constants and helpers from `identify_service.py`.
3. Keep Discogs result mapping helpers in `identify_service.py`.
4. Run focused service and planner tests.

## Phase P2 Tasks

1. Capture `X-Discogs-Ratelimit`, `X-Discogs-Ratelimit-Used`, and `X-Discogs-Ratelimit-Remaining` from Discogs responses.
2. Store the latest observed rate-limit state in `DiscogsRateLimiter`.
3. Keep the existing local request spacing as the fallback path for missing or malformed headers.
4. When headers report no remaining quota, delay the next request until the conservative one-minute window estimate has elapsed.
5. Log observed rate-limit state so API usage is visible during identify and release import workflows.
6. Add tests for header capture, exhausted quota throttling, and malformed header tolerance.

## Validation

Run:

```bash
cd backend
DISCOGS_TOKEN=test ../.venv/bin/pytest tests/pipelines/test_search_planner.py tests/services/test_identify_service.py
DISCOGS_TOKEN=test ../.venv/bin/ruff check app/services/identify_service.py app/pipelines/identification/search_planner.py
DISCOGS_TOKEN=test ../.venv/bin/pytest tests/services/test_discogs_service.py
DISCOGS_TOKEN=test ../.venv/bin/ruff check app/services/discogs_service.py tests/services/test_discogs_service.py
```
