# Implementation Plan: Backend Rate Limiting And Identify Throttling

## Goal

Protect the backend from accidental overload and intentional abuse, especially around image identification.

This plan separates three concerns:

1. General API request rate limiting.
2. Heavy identify pipeline admission control.
3. Optional distributed throttling for production deployment.

The Discogs service already has outbound API throttling. This plan is for inbound backend traffic and local compute protection.

## Current Behavior

The backend currently accepts requests without a global inbound limiter.

Relevant current pieces:

- `Settings.api_rate_limit_per_minute` exists, but it is currently used by the Discogs client limiter.
- `POST /api/v1/identify` runs the identify pipeline synchronously.
- `POST /api/v1/identify/jobs` validates the upload, creates an `identify_jobs` row, and starts processing through FastAPI `BackgroundTasks`.
- `GET /api/v1/identify/jobs/{job_id}` lets Android poll status.
- Identify jobs are DB-backed for status/result/error, but execution is still local process background work.
- Image bytes are not stored in the database.

This is fine for MVP traffic, but it leaves gaps:

- A client can create many expensive identify jobs quickly.
- Multiple clients can overload OCR/VLM resources at the same time.
- Polling can create noisy request traffic.
- In-process background jobs are not coordinated across workers.
- The sync identify endpoint can still run heavy work inline.

## Design Principles

- Protect expensive work first. Identify uploads matter more than cheap reads.
- Keep normal Android usage smooth.
- Prefer explicit `429 Too Many Requests` responses over silent slowdowns.
- Return `Retry-After` when the backend rejects or delays a client.
- Keep Phase 1 simple and local-process safe.
- Use Redis for distributed general API rate limiting when the need is clear.
- Use the database only for limits tied to business state already stored there.
- Keep the synchronous identify endpoint for compatibility, but limit it more strictly.
- Skip durable identify queueing for now.

## Target Behavior

The backend should enforce:

- A default per-client request quota.
- Endpoint-specific quotas for identify creation and polling.
- A global cap on concurrently running identify pipelines.
- A per-client cap on active identify jobs.
- Clear structured errors for rate-limited requests.
- Metrics/logs for accepted, rejected, queued, completed, failed, and expired jobs.

For MVP, distributed correctness is required only for identify limits that already depend on `identify_jobs`. General distributed request limiting should wait for Redis or another external limiter.

## Client Identity

Use a stable `client_key` abstraction from the start.

Phase 1 can derive `client_key` from:

1. Trusted proxy header when explicitly enabled.
2. `request.client.host` as the default.
3. A future authenticated user or device id when auth exists.

Do not trust `X-Forwarded-For` by default. Add settings before using proxy headers:

- `trusted_proxy_headers_enabled`
- `trusted_proxy_header_name`

## Error Contract

Rate-limited responses should use the existing structured error shape:

```json
{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Too many requests. Retry later."
  }
}
```

Identify admission rejections should use a more specific code:

```json
{
  "error": {
    "code": "identify_capacity_exceeded",
    "message": "Identify processing is busy. Retry shortly."
  }
}
```

Responses should include:

```text
HTTP 429 Too Many Requests
Retry-After: <seconds>
```

Polling requests can also receive `429`, but the Android client should keep the current job and retry after the server-provided delay.

## Configuration

Add new settings instead of overloading `api_rate_limit_per_minute`.

Suggested defaults:

| Setting | Default | Purpose |
| --- | ---: | --- |
| `api_rate_limiting_enabled` | `true` | Master switch. |
| `inbound_rate_limit_backend` | `memory` | Selects the general API limiter backend. Use `redis` for shared limits across workers. |
| `inbound_rate_limit_redis_url` | unset | Redis connection URL required only when `inbound_rate_limit_backend=redis`. |
| `inbound_rate_limit_redis_key_prefix` | `vinyl-listen-app:rate-limit` | Prefix for Redis limiter keys. |
| `inbound_rate_limit_redis_fail_open` | `true` | Allows requests when Redis limiter checks fail. Revisit before public launch. |
| `inbound_rate_limit_redis_timeout_seconds` | `0.25` | Short Redis socket/connect timeout so fail-open does not stall requests. |
| `api_default_rate_limit_per_minute` | `120` | General API quota per client. |
| `api_default_burst_size` | `40` | Allows short normal bursts. |
| `api_rate_limit_window_seconds` | `60` | Fixed-window/token-bucket window. |
| `identify_create_rate_limit_per_minute` | `6` | New identify jobs per client. |
| `identify_create_burst_size` | `2` | Small burst for retries. |
| `identify_poll_rate_limit_per_minute` | `120` | Polling quota per client. |
| `identify_sync_rate_limit_per_minute` | `3` | Strict sync identify quota. |
| `identify_max_concurrent_jobs` | `2` | Global local-process pipeline cap. |
| `identify_max_active_jobs_per_client` | `2` | Per-client active job cap. |
| `identify_admission_retry_after_seconds` | `15` | Retry hint when capacity is full. |
| `trusted_proxy_headers_enabled` | `false` | Avoid spoofed client identity by default. |
| `trusted_proxy_header_name` | `X-Forwarded-For` | Header to read only when enabled. |

Keep the existing Discogs limiter settings separate from inbound API settings.

## Endpoint Policy

| Endpoint group | Policy |
| --- | --- |
| `GET /health`, `GET /health/runtime` | Exempt or very high quota. |
| `GET /identify/jobs/{job_id}` | Poll quota, no heavy-work admission. |
| `POST /identify/jobs` | Strict create quota plus identify admission control. |
| `POST /identify` | Strict sync identify quota plus identify admission control. |
| `GET /releases/search` | Moderate quota because it can call Discogs. |
| `POST /releases/import` | Moderate quota because it can call Discogs and write DB rows. |
| Analytics/session/release reads | Default quota. |
| Session writes | Default quota or slightly stricter write quota. |

## Phase 0: Contract And Test Harness

Purpose: define the exact contract before implementation.

Tasks:

1. Add a small rate-limit policy module design.
2. Define error codes and `Retry-After` behavior.
3. Add API spec notes for `429`.
4. Add test helpers for client IP, fake time, and repeated requests.
5. Decide which routes are exempt, default-limited, or identify-limited.

Done criteria:

- A route policy table exists in docs and tests.
- Test helpers can simulate repeated requests without sleeping.
- No production behavior changes yet.

Risk:

- Over-documenting before implementation.

Mitigation:

- Keep Phase 0 focused on behavior needed for tests.

Phase 0 contract:

| Route pattern | Methods | Policy | Notes |
| --- | --- | --- | --- |
| `/` | `GET` | Exempt | Root metadata endpoint. |
| `/favicon.ico` | `GET` | Exempt | Browser convenience endpoint. |
| `/api/v1/health*` | `GET` | Exempt | Health probes must keep working during load. |
| `/api/v1/identify` | `POST` | Identify | Synchronous heavy identify work. |
| `/api/v1/identify/jobs` | `POST` | Identify | Async identify job creation. |
| `/api/v1/identify/jobs/{job_id}` | `GET` | Default | Polling is cheaper than job creation. |
| `/api/v1/**` | Any | Default | All other versioned API routes. |

Phase 1 `429` contract:

- Response body: `{"error": {"code": "rate_limited", "message": "Too many requests. Please retry later."}}`
- `Retry-After` header: integer seconds until the next request can be accepted.
- `X-RateLimit-Limit` header: active policy limit.
- `X-RateLimit-Remaining` header: remaining whole tokens for accepted requests, `0` for rejected requests.

Client behavior:

- Clients should honor `Retry-After` before applying local backoff.
- If `Retry-After` is absent or invalid, clients should use exponential backoff with jitter.
- Clients should not automatically retry non-idempotent uploads or writes unless an idempotency contract exists.

## Phase 1: In-Process API Rate Limiter

Purpose: add simple inbound protection for one backend process.

Implementation shape:

- Add `backend/app/core/rate_limit.py`.
- Implement an in-memory token bucket or fixed-window limiter.
- Key buckets by `(client_key, policy_name)`.
- Use a monotonic clock for refill/window math.
- Return remaining delay when a request is rejected.
- Add FastAPI middleware or route dependency.

Recommended approach:

- Use middleware for broad default limits.
- Use route dependencies for endpoint-specific limits.
- Exempt health endpoints explicitly.

Tasks:

1. Add limiter settings in `backend/app/core/config.py`.
2. Add `ClientKeyResolver`.
3. Add `RateLimitPolicy` dataclass.
4. Add `InMemoryRateLimiter`.
5. Add middleware or dependency wiring in `backend/app/main.py` and route modules.
6. Return structured `429` responses with `Retry-After`.
7. Add unit tests for bucket refill, rejection, and independent client keys.
8. Add API route tests for default limit and identify create limit.

Done criteria:

- Repeated requests over quota return `429`.
- Different client keys have independent quotas.
- Health endpoints remain usable.
- `Retry-After` is present and non-negative.
- Tests do not sleep.
- API documentation tells clients to honor `Retry-After` and use jittered backoff when needed.

Validation:

```bash
cd backend
DISCOGS_TOKEN=test .venv/bin/pytest backend/tests/core backend/tests/api
DISCOGS_TOKEN=test .venv/bin/ruff check app tests
DISCOGS_TOKEN=test .venv/bin/black --check app tests scripts
```

Limitations:

- Limits are per process.
- Restarting the backend resets counters.
- Multiple Uvicorn workers do not share state.

## Phase 2: Identify Admission Control

Purpose: protect CPU/OCR/VLM work, not just HTTP request count.

Implementation shape:

- Add `IdentifyAdmissionController`.
- Enforce global local-process concurrency with a semaphore.
- Enforce per-client active jobs by checking DB rows.
- Store `client_key` on `identify_jobs`.
- Add active terminal status helpers.
- Add `identify_capacity_retry_after_seconds` for client retry guidance.

Active statuses:

```text
queued
upload_received
preprocessing_image
extracting_text
parsing_identifiers
searching_local
searching_discogs
ranking_candidates
```

Terminal statuses:

```text
completed
failed
expired
```

Tasks:

1. Add `client_key` column to `identify_jobs`.
2. Add repository query for active jobs by client.
3. Add repository query for active jobs globally, if needed.
4. Add admission check before creating or starting a job.
5. Return `429 identify_capacity_exceeded` when active job capacity is full.
6. Include `Retry-After` on identify capacity rejects.
7. Wrap job execution in a concurrency guard.
8. Ensure semaphore release happens in `finally`.
9. Keep failed jobs terminal if processing raises.
10. Add tests for per-client active job rejection.
11. Add tests for global concurrency rejection or queued behavior.

Design choice:

- For Phase 2, reject when capacity is full.
- Do not queue yet. Queueing needs stronger worker semantics.

Done criteria:

- A single client cannot create more than the configured active job count.
- Total running local jobs cannot exceed `identify_max_concurrent_jobs`.
- Sync identify also respects the same heavy-work guard.
- Jobs are never stuck active because of admission or worker exceptions.

Validation:

```bash
cd backend
DISCOGS_TOKEN=test .venv/bin/pytest backend/tests/services/test_identify_job_service.py backend/tests/api/test_identify_api.py backend/tests/migrations/test_schema_migration.py
DISCOGS_TOKEN=test .venv/bin/pytest
```

Limitations:

- Semaphore is per process.
- Per-client admission is serialized with an in-process keyed lock around active-count check and job creation.
- Multiple backend workers still need a database transaction/advisory lock before the active-count check and insert.

## Phase 3: DB-Backed Business Limits For Identify Jobs

Purpose: use database state where it naturally fits, without turning every API request into a database write.

This phase should not implement general API request limiting in the database. It should focus on low-frequency limits tied to existing business state.

Good DB-backed fits:

- max active identify jobs per client.
- max active identify jobs globally.
- stale active identify job recovery.
- optional low-frequency write limits such as release import abuse protection.
- optional retry/attempt limits for identify jobs.

Poor DB-backed fits:

- every request to every API route.
- high-frequency polling.
- public high-scale traffic.
- anything where abuse would create heavy database write pressure.

Implementation shape:

- Keep general request limiting in-process for now.
- Keep per-process heavy-work protection with a local semaphore.
- Store `client_key` on `identify_jobs`.
- Use indexed DB queries for active identify job counts.
- Add stale-active cleanup or expiry so crashed jobs do not block clients forever.

Tasks:

1. Add `client_key` to `identify_jobs`.
2. Add indexes for `client_key`, `status`, and `expires_at` if query plans need them.
3. Add repository methods for active jobs by client and active jobs globally.
4. Add stale-active recovery using `updated_at` or `expires_at`.
5. Enforce per-client active job cap before creating new jobs.
6. Optionally enforce global active job cap from DB for multi-worker awareness.
7. Keep the local semaphore as the immediate per-process OCR/VLM concurrency guard.
8. Add tests for active-job counting, stale recovery, and capacity rejection.

Done criteria:

- Identify job admission uses DB state for per-client active job limits.
- A crashed or stale job does not block the client forever.
- No generic `rate_limit_buckets` table is added.
- General API request limiting remains separate from DB-backed business limits.
- `identify_capacity_exceeded` responses expose a stable retry hint for clients.

Tradeoff:

- This does not solve distributed general request limiting.
- It does solve the most important MVP risk: too many expensive identify jobs.

## Phase 4: Redis-Backed Distributed API Rate Limiting

Purpose: add real distributed request limiting when the backend runs multiple workers or instances.

Use Redis before DB-backed counters for general API traffic.

Why Redis:

- request counters are fast ephemeral state.
- abuse creates Redis pressure instead of database write pressure.
- expiry is native and avoids cleanup jobs.
- token bucket or sliding-window algorithms are standard.
- multiple workers and instances can share limits.

Tasks:

1. Add Redis dependency and settings. **Done.**
2. Add config to choose limiter backend: `memory` or `redis`. **Done.**
3. Implement Redis token bucket or use a maintained rate-limit library. **Done with Redis token bucket.**
4. Preserve the same rate-limiter interface from Phase 1. **Done.**
5. Define fail-open or fail-closed behavior for Redis outages. **Done: default fail-open for MVP.**
6. Add integration tests guarded by optional Redis availability.
7. Update deployment docs.

Done criteria:

- Backend can switch limiter backend by config.
- Existing route tests pass against memory and Redis implementations.
- Production can share limits across workers or instances.
- Redis key TTL prevents unbounded limiter state growth.

Decision:

- Fail open is the MVP default because it keeps the app usable when Redis is down.
- Fail closed favors protection when Redis is down.
- Revisit fail closed before public launch or if abuse risk increases.

## Future Phase: Durable Identify Queue

Purpose: move from background tasks to controlled workers.

This is explicitly out of scope for the next implementation slice.

Implementation shape:

- `POST /identify/jobs` creates a `queued` job.
- Worker claims queued jobs with row-level locking.
- Worker updates statuses through the existing progress reporter.
- Concurrency is controlled by worker count and claim limits.

Required DB changes:

- `client_key`
- `locked_at`
- `locked_by`
- `attempt_count`
- `next_attempt_at`
- optional `priority`

Hard problem:

- Image bytes are currently not stored.
- Durable queued jobs need durable input storage.

Input storage options:

1. Store upload bytes in object/file storage with short TTL.
2. Store compressed image bytes in DB for MVP only.
3. Keep Phase 4 unavailable until an object storage path exists.

Recommended path:

- Use local filesystem storage only for local development.
- Design an `IdentifyJobInputStore` interface.
- Keep object storage compatible for future deployment.

Tasks:

1. Add job input storage interface.
2. Add local filesystem input store with cleanup.
3. Add job claim repository method.
4. Add worker loop script or process entrypoint.
5. Add retry policy for transient failures.
6. Add stale lock recovery.
7. Change API create endpoint to return `queued` when worker capacity is full.
8. Update Android docs to allow longer `queued` state.
9. Add tests for claim, lock, retry, and stale lock recovery.

Done criteria:

- Backend can accept jobs without running all of them immediately.
- Workers process jobs up to configured concurrency.
- A crashed worker does not leave jobs permanently locked.
- Job input is cleaned after terminal state or expiry.

## Phase 6: Observability And Operations

Purpose: make throttling visible and tunable.

Add structured logs for:

- Rate-limit allow/reject.
- Identify admission allow/reject.
- Current active identify job count.
- Job start, completion, failure, and duration.
- Retry-after values.
- Client-visible throttle error codes.

Add health/runtime fields:

- rate limiter enabled.
- limiter backend.
- identify max concurrency.
- active identify jobs.
- queued identify jobs, once queueing exists.

Optional metrics:

- `api_rate_limit_rejected_total`
- `identify_jobs_active`
- `identify_jobs_rejected_total`
- `identify_jobs_duration_seconds`
- `identify_jobs_failed_total`

Done criteria:

- Local logs explain why a request was rejected.
- Runtime health output shows limiter configuration without secrets.
- Tests cover response shape, not log text.

## Android Impact

Android should handle:

- `429` from `POST /identify/jobs` by showing a retryable busy state.
- `429` from `GET /identify/jobs/{job_id}` by waiting for `Retry-After` and polling again.
- Existing job failures through `status="failed"` and `failed_step`.

No Android change is required for Phase 1 if only backend returns normal HTTP errors. Android improvements become useful in Phase 2, because identify creation can return `429 identify_capacity_exceeded`.

## Documentation Updates By Phase

Phase 1:

- `docs/architecture/api-spec.md`: add general `429` response contract.
- `docs/features/backend-services.md`: document inbound rate limiter.
- `docs/repository-structure.md`: add new core/repository files if created.

Phase 2:

- `docs/features/identify-progress-jobs.md`: document admission control and active job caps.
- `docs/architecture/database-schema.md`: add `client_key` to `identify_jobs`.

Phase 3:

- `docs/features/identify-progress-jobs.md`: document DB-backed active-job limits.
- `docs/architecture/database-schema.md`: add `client_key` and any identify job indexes.
- `docs/features/backend-services.md`: document identify admission control.

Phase 4:

- `docs/features/backend-services.md`: document Redis-backed limiter backend.
- `docs/architecture/api-spec.md`: clarify distributed `429` behavior.

Future durable queue phase:

- `docs/features/identify-progress-jobs.md`: document queued jobs, input storage, retries, and worker behavior.
- `docs/architecture/api-spec.md`: clarify longer-lived `queued` status.
- `docs/repository-structure.md`: add worker/input-store files.

## Test Plan

Unit tests:

- token bucket or fixed-window math.
- retry-after calculation.
- client key resolver.
- route policy matching.
- admission controller.
- repository active job counts.

API tests:

- default quota returns `429`.
- identify create quota returns `429`.
- identify poll quota has higher allowance.
- health endpoints are exempt.
- structured error response matches contract.
- `Retry-After` header exists.

Service tests:

- identify job creation rejected when per-client active count is exceeded.
- identify processing releases global semaphore after success.
- identify processing releases global semaphore after failure.
- sync identify respects heavy-work guard.

Migration tests:

- `identify_jobs.client_key` exists after Phase 2.
- SQLite-compatible JSON and timestamp behavior remains valid.

Regression tests:

- existing identify success path.
- existing identify validation errors.
- existing Android polling API contract.
- existing Discogs limiter tests.

## Rollout Plan

1. Merge Phase 1 with conservative defaults.
2. Run backend tests and Android compile checks.
3. Test local Android identify flow manually.
4. Merge Phase 2 with strict but adjustable identify caps.
5. Observe local logs during repeated uploads.
6. Add Phase 3 when DB-backed identify/business limits need stronger cross-worker behavior.
7. Add Redis-backed Phase 4 when distributed general API limiting matters.
8. Keep durable queueing out of scope until queued jobs and image input storage are explicitly needed.

## Risks And Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Limits too strict for normal Android use. | Frustrating retries. | Start with conservative defaults and higher poll quota. |
| Polling gets rate limited too aggressively. | Processing screen appears broken. | Separate poll policy from create policy. |
| Client IP is wrong behind proxy. | Many users share one bucket. | Disable trusted proxy headers by default; configure per deployment. |
| In-memory limiter gives false confidence in multi-worker deployment. | Abuse can bypass per-process limits. | Document Phase 1 limitation; use Redis before multi-worker public deployment. |
| Identify jobs stay active after crash. | Per-client admission blocks future work. | Expire old active jobs and add stale-job recovery in Phase 3. |
| Durable queue needs image storage. | Queue cannot survive process restart. | Add `IdentifyJobInputStore` before enabling durable queued workers. |
| DB-backed general limiter adds write load. | Abuse can pressure the primary database. | Do not use DB for general request limiting; reserve DB for identify/business-state limits. |
| Redis adds operational complexity. | New dependency can fail or be misconfigured. | Keep Redis as a later phase with explicit fail-open/fail-closed behavior. |

## Recommended First Implementation Slice

Start with Phase 1 and part of Phase 2:

1. Add in-memory limiter and endpoint policies.
2. Add `429` structured errors and tests.
3. Add identify global semaphore.
4. Add per-client active job cap only if `client_key` can be stored cleanly in `identify_jobs`.

This gives immediate protection for the heavy identify path without committing to Redis or a durable worker queue too early. General distributed API limiting should wait for Redis, while DB-backed work should stay focused on identify-job state.
