# Implementation Plan: Identify Job Cooperative Cancellation

## Goal

Allow Android to cancel an async identify job when the user leaves the processing flow or explicitly taps cancel, while keeping the backend implementation MVP-sized.

This plan adds cooperative cancellation. The backend records a cancellation request and stops work at safe checkpoints. It does not attempt to forcibly kill an OCR, VLM, HTTP, or database call that is already in progress.

## Current Behavior

- `POST /api/v1/identify/jobs` validates the upload, creates an `identify_jobs` row, and starts `IdentifyJobService.process_job` with FastAPI `BackgroundTasks`.
- The uploaded image bytes are held in process memory for the background task.
- `GET /api/v1/identify/jobs/{job_id}` lets Android poll job status.
- Active identify statuses count against admission limits until the job reaches `completed`, `failed`, or `expired`.
- The durable identify queue remains future work. Jobs are not yet claimed by separate workers.

## Design Principles

- Prefer predictable user experience over hard process interruption.
- Keep cancellation idempotent so Android can retry safely.
- Do not free backend capacity until the running job actually reaches a terminal status.
- Preserve the current phase status while cancellation is pending.
- Check cancellation before expensive phase boundaries.
- Treat app-close cancellation as best effort; Android process death is not a reliable delivery mechanism.

## API Contract

Add:

```text
POST /api/v1/identify/jobs/{job_id}/cancel
```

Behavior:

- If the job is active, record `cancel_requested_at` and return the current job status with `cancel_requested=true`.
- If the job is already `canceled`, return the current job status.
- If the job is already `completed`, `failed`, or `expired`, return the current terminal status. The backend should not rewrite completed work to canceled.
- If the job does not exist, return `404`.

Extend `IdentifyJobStatusResponse`:

```json
{
  "job_id": "uuid",
  "status": "extracting_text",
  "cancel_requested": true
}
```

Add terminal status:

```text
canceled
```

Recommended DB change:

- `cancel_requested_at TIMESTAMP NULL`

Use a timestamp instead of a transient `cancel_requested` status so the current processing phase remains visible while cancellation is pending.

## Backend Phases

### P1 - Contract, schema, and repository

Tasks:

1. Add `canceled` to `IdentifyJobStatus`.
2. Add `cancel_requested_at` to `identify_jobs`.
3. Add `cancel_requested` to `IdentifyJobStatusResponse`.
4. Add repository methods:
   - `request_cancel(job_id, requested_at)`
   - `is_cancel_requested(job_id)`
   - `mark_canceled(job_id, message, updated_at)`
5. Add tests for idempotent cancel behavior and terminal-job behavior.

Done criteria:

- Cancel request can be persisted without changing the current phase status.
- Terminal statuses include `completed`, `failed`, `expired`, and `canceled`.
- Active-job queries continue to count cancel-requested jobs until they become `canceled`.

Estimated effort: 0.5-1 day.

### P2 - Cancel endpoint

Tasks:

1. Add `POST /api/v1/identify/jobs/{job_id}/cancel`.
2. Return the same structured job response shape as the polling endpoint.
3. Keep the endpoint idempotent for active and canceled jobs.
4. Add API tests for active, canceled, completed, expired, and missing jobs.
5. Document `404` and terminal no-op behavior in `docs/architecture/api-spec.md`.

Done criteria:

- Android can safely call cancel more than once.
- A cancel request does not report success as `canceled` until processing acknowledges it.

Estimated effort: 0.5-1 day.

### P3 - Cooperative backend checkpoints

Tasks:

1. Add an `IdentifyJobCancellationToken` or callback owned by `IdentifyJobService`.
2. Check cancellation before:
   - preprocessing image
   - extracting text
   - parsing identifiers
   - searching local releases
   - searching Discogs
   - ranking candidates
   - writing completed results
3. When cancellation is detected, mark the job `canceled` with a message such as `Identify canceled`.
4. Ensure the admission semaphore and active-job capacity are released in the existing `finally` path.
5. Avoid storing a failure payload for canceled jobs.
6. Add service tests for cancellation before first work, mid-pipeline, and before completion write.

Done criteria:

- Cancellation stops work at the next backend-controlled checkpoint.
- Long blocking calls may still finish, but their result is discarded if cancellation was requested before completion.
- Canceled jobs are terminal and no longer count as active.

Estimated effort: 1-2 days.

### P4 - Backend docs and observability

Tasks:

1. Update `docs/features/backend-services.md`.
2. Update `docs/features/identification-pipeline.md`.
3. Update `docs/architecture/api-spec.md`.
4. Add structured logs:
   - cancel requested
   - cancel acknowledged
   - cancel ignored because job was terminal
5. Optionally expose canceled job counts in later runtime/operations metrics.

Done criteria:

- Docs explain that cancellation is cooperative, not a hard interrupt.
- Logs distinguish requested cancellation from acknowledged cancellation.

Estimated effort: 0.5 day.

## Android Phases

### P5 - Client API and domain model

Tasks:

1. Add `cancelRequested: Boolean` to the Android job status model.
2. Add `cancelIdentifyJob(jobId)` to `VinylApiClient`.
3. Treat cancel as a safe retryable request.
4. Add parsing coverage for `status=canceled` and `cancel_requested=true`.

Done criteria:

- Android can call the backend cancel endpoint.
- Existing polling still works for jobs without cancellation fields if needed during local rollout.

Estimated effort: 0.5-1 day.

### P6 - Processing screen UX

Tasks:

1. Add an explicit cancel action to `ProcessingScreen`.
2. On cancel tap:
   - call the cancel endpoint
   - stop creating new polling pressure
   - show a canceling state until `status=canceled` or another terminal status arrives
3. While the job is active, block normal back navigation away from Processing, including:
   - Android system back
   - gesture/swipe back
   - navigation-bar back behavior
4. Use a top-left cancel button as the only supported way to intentionally leave an active Processing job.
5. After the user taps cancel, send the best-effort cancel request and then allow navigation once the local cancel flow has started or a terminal status is received.
6. Do not rely on app process close as the only cancellation signal.
7. If cancel fails because the backend is unreachable, stop local polling and let backend stale expiry clean up.

Done criteria:

- The user can leave Processing without waiting for identify to finish.
- Active Processing cannot be dismissed accidentally with system back or swipe back.
- The top-left cancel control is the intentional exit path for active jobs.
- The UI handles `canceled`, `completed-before-cancel`, `failed`, and network-error cases.

Estimated effort: 1-2 days.

### P7 - Android tests and product docs

Tasks:

1. Add tests for cancel button state and navigation-away behavior.
2. Add tests for canceled job response mapping.
3. Update `docs/product/mvp-screen-spec.md`.
4. Update `docs/architecture/navigation-graph.md` if navigation behavior changes.

Done criteria:

- Product docs describe the Processing cancel behavior.
- Tests cover the expected user-visible state transitions.

Estimated effort: 0.5-1 day.

### P8 - Full stale documentation refresh

Tasks:

1. Re-inventory stale docs after backend and Android implementation are complete.
2. Update backend workflow docs:
   - `docs/features/backend-services.md`
   - `docs/features/identification-pipeline.md`
3. Update API and schema docs:
   - `docs/architecture/api-spec.md`
   - `docs/architecture/database-schema.md`
4. Update Android and product docs:
   - `docs/product/mvp-screen-spec.md`
   - `docs/architecture/navigation-graph.md`
   - `docs/product/app-design-system.md` if the Processing cancel UI introduces new component behavior
5. Update repo inventory docs:
   - `docs/repository-structure.md`
6. Search the docs tree for stale identify-job language, including:
   - status lists that omit `canceled`
   - Processing screen flows that omit cancel behavior
   - backend descriptions that imply jobs can only end as `completed`, `failed`, or `expired`
   - durable queue notes that should reference cooperative cancellation as an existing prerequisite
7. Add a short changelog-style note to this implementation plan summarizing which docs were aligned.

Done criteria:

- Project documentation consistently describes cooperative cancellation across backend, API, Android, product, database, and repo-structure docs.
- No stale status contract omits `canceled`.
- Durable queue documentation remains future-scoped but acknowledges the existing cancellation contract.

Estimated effort: 0.5-1.5 days, depending on how much stale documentation is found.

## Relationship To Durable Identify Queue

This plan is compatible with the future durable queue.

When the durable queue exists:

- `cancel_requested_at` still works for running jobs.
- Queued jobs can be skipped before a worker claims them.
- `canceled` remains the terminal status.
- Worker claim logic should exclude canceled jobs.

Additional durable-queue work still required later:

- durable image input storage
- worker claiming with row-level locking
- `locked_at`, `locked_by`, `attempt_count`, and `next_attempt_at`
- retry and stale-lock behavior

Cooperative cancellation should not require those durable-queue changes for MVP.

## End-To-End Validation

Backend:

- `POST /identify/jobs/{job_id}/cancel` is idempotent.
- Cancel requested before processing becomes terminal `canceled`.
- Cancel requested during a phase becomes terminal `canceled` at the next checkpoint.
- Cancel requested after completion leaves the completed result intact.
- Canceled jobs do not count against active identify capacity.

Android:

- Cancel button calls backend once and handles retries.
- Processing blocks normal back and swipe navigation while a job is active.
- Processing exits cleanly through the top-left cancel flow.
- Polling stops or slows while cancellation is pending.
- Completed-before-cancel navigates to the normal match flow.
- Canceled response does not show a failure screen.

## Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Android process is killed before sending cancel | Backend keeps working | Treat app-close cancel as best effort and keep stale-job expiry. |
| OCR/VLM call is already blocking | Compute continues briefly | Check cancellation before and after blocking calls. |
| Capacity is released too early | More concurrent jobs than intended | Keep cancel-requested jobs active until terminal `canceled`. |
| User cancels after job completed | Confusing result state | Return completed status and do not rewrite terminal success. |
| User accidentally leaves Processing with system back or gesture navigation | Backend keeps working without a clear user action | Block normal back navigation while active and route intentional exit through the cancel button. |
| Contract expands into durable queue work | Scope creep | Keep image storage and worker claiming out of this plan. |

## Recommended MVP Slice

Implement P1 through P6 together. P7 and P8 can follow in the same PR or a small docs/test follow-up, but P8 should be completed before considering the feature fully done.

Expected total effort: 3.5-6.5 development days, depending on test coverage, Processing screen polish, and documentation drift.
