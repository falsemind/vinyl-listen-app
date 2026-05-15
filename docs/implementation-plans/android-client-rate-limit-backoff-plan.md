# Implementation Plan: Android Client Rate-Limit Backoff

## Goal

Make the Android client behave politely when the backend returns `429`, transient backend errors, or offline failures.

The MVP should honor backend retry guidance, avoid retry storms, and keep the user informed without building a full resilience framework.

## Scope

### In Scope

- Shared retry policy in the Android API layer.
- `Retry-After` parsing for `429` responses.
- Exponential backoff with jitter when no backend retry hint is available.
- Safe retry rules for read and polling calls.
- Clear UI state for identify capacity errors.
- Unit tests for retry decisions and delay calculation.

### Out Of Scope For MVP

- Persistent circuit-breaker state across app restarts.
- Global telemetry dashboards.
- Automatic retries for non-idempotent uploads or session writes.
- Durable client-side request queueing.

## Success Criteria

- Client honors `Retry-After` before local backoff defaults.
- Polling and safe reads retry with exponential backoff and jitter.
- Upload and write calls do not silently duplicate user actions.
- Identify capacity errors surface a retryable UI message.
- Tests cover `429`, `Retry-After`, offline errors, and unsafe-call no-retry behavior.

## Actionable Items

| Task | Effort | Depends On | Done Criteria |
| --- | --- | --- | --- |
| Define retry policy model | 2h | Backend `429` contract | Kotlin model identifies retryable statuses, max attempts, base delay, max delay, jitter range, and safe methods. |
| Parse `Retry-After` | 2h | Retry policy model | API client parses integer seconds and ignores malformed or negative values. |
| Add backoff delay helper | 2h | Retry policy model | Helper returns exponential delays with jitter and clamps to max delay. |
| Apply retry to safe calls | 4h | Delay helper | GET calls and identify status polling use retry policy; uploads and writes stay single-shot. |
| Improve identify capacity UI | 3h | Backend capacity `Retry-After` | Processing and match flows show a retryable message without hammering the backend. |
| Add tests | 4h | Implementation | Unit tests cover retry-after, jitter bounds, max attempts, safe-call rules, and capacity handling. |
| Manual validation | 2h | Tests | Local backend forced to return `429`; client waits, then recovers or shows retry state. |

## Suggested MVP Behavior

### Safe To Retry

- `GET /api/v1/identify/jobs/{job_id}`
- `GET /api/v1/releases/search`
- `GET /api/v1/releases/{release_id}`
- `GET /api/v1/releases/{release_id}/sessions`
- `GET /api/v1/sessions/summary`
- Analytics reads

### Do Not Auto-Retry By Default

- `POST /api/v1/identify`
- `POST /api/v1/identify/jobs`
- `POST /api/v1/releases/import`
- `POST /api/v1/sessions/`

These calls can create work or write state. Show a retry action instead of replaying them automatically.

## Backoff Rules

1. If response has `Retry-After`, wait that duration.
2. If no valid `Retry-After`, use exponential backoff with jitter.
3. Use a low attempt count for foreground UI, such as three attempts.
4. Stop retrying when the user leaves the screen or cancels the operation.
5. Treat `identify_capacity_exceeded` as retryable by the user, not automatically replayed for uploads.

Recommended defaults:

| Setting | Value |
| --- | --- |
| Base delay | 1 second |
| Max delay | 8 seconds |
| Max attempts | 3 |
| Jitter | 0-250 ms for MVP |

## Dependencies

```text
Backend Retry-After contract
  -> Retry policy model
  -> API client retry wrapper
  -> Screen state updates
  -> Unit tests and manual validation
```

## Risks And Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Retrying uploads duplicates backend work. | High | Keep uploads single-shot unless backend adds idempotency keys. |
| Polling retries hide real failures. | Medium | Cap attempts and surface failure state. |
| Jitter makes tests flaky. | Medium | Inject random source or delay provider in tests. |
| Client and backend disagree on retry windows. | Medium | Prefer backend `Retry-After` over local defaults. |

## Future Robust Approach

Later, add a circuit breaker around backend availability and rate-limit failures. The breaker can pause repeated calls after a burst of `429`, timeout, `502`, or `503` responses, then move through half-open recovery after a cooldown.

Durable request queueing, persisted breaker state, telemetry, and idempotency keys should wait until the app has production traffic or background sync.
