# Implementation Plan: Multi-User Support

## Goal

Add first-class user accounts so each person's collection, listening history, analytics, integrations, and future paid-feature access are isolated under their own account.

The first release should make registration mandatory on fresh install, support email verification, provide a secure token lifecycle for Android, and prepare the backend for future subscription-gated usage limits without requiring billing in the MVP.

## Current Context

- The app currently behaves as a single-user system.
- Existing collection behavior should be preserved: local app ownership remains the safe default, while Discogs is an explicit mirror/source option.
- Discogs authenticated requests are backend-owned when a saved token exists; Android may still perform unauthenticated direct manual/barcode calls where that flow already belongs on-device.
- `provider_integrations` already has nullable `user_id` shape for future multi-user scoping.
- Analytics, insights, and AI summaries must be based only on the authenticated user's data.

## Product Requirements

### Account Creation

- On fresh install, show an account registration screen before the main app.
- Required registration fields:
  - Email address.
  - Password.
  - Password confirmation.
- Email must be verified with a short confirmation code before the account can use authenticated app features.
- The code entry screen must support resend with rate limiting and clear expiry behavior.
- After successful verification, show an optional setup suggestion screen that can be skipped.
- Initial optional setup suggestions:
  - Add Discogs access token.
  - Choose collection source of truth.
- Skipping setup must land the user in the normal app with safe defaults.

### Email Delivery

- First slice must support simple local testing without a real email provider.
- Local/dev delivery can expose the verification/reset code through backend logs, a dev-only test endpoint, or a local mail catcher.
- The email sending boundary should be an adapter so production delivery can be swapped without changing auth logic.
- A real provider means an SMTP server or email delivery API that sends messages to real inboxes and handles deliverability concerns such as sender authentication, bounce handling, and suppression lists.
- Candidate real-provider categories:
  - Transactional email services such as Postmark, Resend, SendGrid, Mailgun, or Amazon SES.
  - SMTP from an existing mail provider if deliverability and rate limits are acceptable.
- Current preferred first real provider candidate: Mailgun.
- The plan should not depend on a specific free quota or pricing tier; provider limits can change and should be checked before implementation/deployment.
- The first implementation path should be:
  - Local/dev code delivery for fast testing.
  - Configured real-email delivery to one test email address.
  - Provider choice finalized before production deployment.

Email transport decision:

- Use local/dev delivery first for fast testing.
- Use Mailgun's Provider API for the first real-email test and production path.
- Do not implement SMTP fallback in the first slice.
- Avoiding SMTP keeps the email path smaller and preserves better structured provider feedback for delivery/debugging.
- Keep the app's email sender behind a small adapter so the provider can be swapped later if needed.

### Sign In And Session Access

- App launch starts on a lightweight splash screen while auth state is verified.
- Splash screen can be simple: dark background with the app logo centered.
- The home screen is not shown until local token state and backend refresh/validity checks complete.
- If auth verification fails because of no connection, timeout, server error, or another transient startup problem, keep the user on the splash screen and show an inline error state with retry.
- Retry should re-run the same auth verification/refresh flow without clearing stored tokens.
- After repeated failed retries, the splash error should suggest checking the connection and restarting the app.
- Startup failures must not silently sign the user out unless the backend clearly says the refresh token/session is invalid or revoked.
- Returning users can sign in with email and password.
- The Android app stores tokens securely and should not require password entry on every launch.
- After one week of inactivity, the app must require password re-entry before allowing access to user data.
- Inactivity is measured by authenticated backend activity or successful token refresh, not just opening the Android app locally.
- If the inactivity check fails during splash, route directly to password re-entry instead of briefly showing the home screen.
- Re-entering the password after inactivity should issue a fresh token pair.
- Manual sign out clears locally stored tokens and returns to the auth screen.

### Auth Recommendation

Use an OAuth2-style token lifecycle owned by the backend rather than third-party OAuth as the primary app login.

- Access token:
  - Short-lived bearer token.
  - Recommended lifetime: 15 minutes.
  - Sent on authenticated API requests.
- Refresh token:
  - Opaque server-stored token, not a long-lived JWT.
  - Stored securely on Android.
  - Rotated on every refresh.
  - Concurrent refresh reuse must be treated as token reuse, not as a raw database or server error.
  - Revoked on logout, password change, account deletion, suspicious reuse, or inactivity expiry.
- Session/device record:
  - Tracks user, refresh token hash, creation time, last activity, expiry, device label, and revoked state.
  - Supports multiple devices per account.
- Step-up after inactivity:
  - If `last_activity_at` is older than 7 days, refresh fails with a typed response requiring password re-authentication.
  - Password re-auth creates a new session and token pair.

This gives the app the practical benefits the user expects from OAuth2 token handling without introducing a full external authorization server or social login dependency too early.

### Password Change

- Authenticated users can change password from Settings.
- Password change requires the current password.
- On success, all existing refresh sessions are revoked except the current session unless the user chooses to sign out everywhere.
- User receives a security notification email after password change.

### Password Reset

- Forgot-password flow starts from the sign-in screen.
- User enters email and receives a reset code or reset link.
- Reset codes expire and are rate limited.
- Successful reset revokes all existing sessions.
- Responses must not reveal whether an email is registered.

### Delete Account

- Account deletion is available from Settings.
- Deletion requires password re-authentication.
- UI must clearly warn that collection, listening sessions, analytics, insights/chat history, saved provider tokens, and app-owned preferences will be deleted.
- Deletion should hard-delete user-owned data while retaining only minimal audit records.
- Minimal audit records should not retain collection contents, listening history, provider tokens, notes, analytics inputs, or other user-owned app data.
- Minimal audit records may retain operational facts such as account deletion timestamp, deletion request id, and security/audit event type.
- External provider tokens, including Discogs tokens, must be revoked locally from app storage and deleted from backend encrypted storage.
- Shared public metadata may remain only if it is no longer linked to the deleted user.
- The API should return a deletion receipt/status so Android can clear local auth state and return to registration.

### Future Subscription And Feature Gating

The MVP should include an entitlement-ready model, but not billing implementation.

- Users can have a plan/entitlement state such as `FREE`, `TRIAL`, `PLUS`, or `PRO`.
- Backend feature checks should use capability names rather than hard-coded plan names.
- Usage-limited features should record user-scoped usage events and rolling-window counters.
- OCR/identify usage is the clearest first candidate for usage counters because it can become compute/API-cost heavy.
- AI chat can also be limited or paid later, but the feature is still early-stage and should not drive the first entitlement design by itself.
- Candidate future gated features:
  - AI insight/chat usage.
  - Advanced analytics.
  - BPM/key signature detection for estimated audio metadata, still in early planning.
  - Larger collection sync limits.
  - OCR/identify volume.
  - Export/import features.
- API responses for gated features should use a structured error that Android can map to upgrade messaging later.

## Data Ownership Requirements

### User-Owned Data

These records must be scoped to `user_id`:

- Provider integrations and encrypted tokens.
- Collection settings.
- Collection membership, favorite state, Discogs folder membership, and source-of-truth state.
- Listening sessions and session groups.
- Ratings, moods, styles, notes, and analytics inputs.
- AI chat history, insight summaries, and imported listening-history files.
- Identify jobs that include user uploads, cached results, or user-specific rate limits.
- Collection sync jobs and background progress state.
- Spotify listening imports, rollups, matches, and AI tool inputs.
- Usage counters and future entitlements.

### Shared Or Catalog Data

Release metadata may be shared only if it is safe and does not encode user-specific collection state.

- Shared release rows can represent canonical Discogs/internal metadata.
- User-specific fields such as collection membership, notes, ratings, and ownership state should live in user-owned tables.
- If current schema stores user-specific state directly on shared release rows, the migration plan must split that state before true multi-user rollout.
- Personal/manual release entries should be user-owned and deleted with the account.
- Manual release entries should stay separate from the centralized Discogs/catalog metadata model.
- The first multi-user release should not automatically merge, cross-reference, or reconcile manual releases with Discogs releases.
- A later enhancement can search Discogs by key identifiers from a manual entry and offer a user-controlled replacement with richer Discogs metadata.
- Replacement should be explicit: the user chooses whether to keep the manual entry, replace it with the Discogs variant, or keep both.
- If the user chooses to keep both, store any relationship as a user-owned association from the manual release to the shared Discogs/catalog release.
- The association is not a merge and must be deleted with the user's account/manual release.
- Account deletion must remove the user's manual release and association rows while preserving shared Discogs/catalog metadata if no user-owned data remains attached.
- Existing sessions/history should remain attached to the user's record even if a later replacement flow points future collection behavior at a Discogs/catalog release.
- Shared Discogs/catalog metadata is preferred over per-user duplication for long-term storage and cache efficiency.
- Per-user duplicated releases may reduce migration complexity in an early slice, but can create storage bloat, stale duplicate metadata, and slower cross-user catalog enrichment over time.
- The shared-metadata model depends on correct indexing and strict `user_id` scoping for membership/session tables, not on duplicating the full release row per user.

## Backend Requirements

### Auth API

Add versioned endpoints for:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/verify-email`
- `POST /api/v1/auth/resend-verification`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/password-reset/request`
- `POST /api/v1/auth/password-reset/confirm`

Later account-management endpoints:

- `POST /api/v1/auth/password/change`
- `DELETE /api/v1/account`

### Authorization

- All user data endpoints require an authenticated user.
- For production deployment, all application endpoints require authentication by default.
- Public endpoints must be explicitly allowlisted.
- Expected public endpoints:
  - Registration.
  - Email verification and resend.
  - Login.
  - Token refresh.
  - Password reset request/confirm.
  - Minimal health/readiness endpoints that expose no user data or sensitive configuration.
- Repositories and services must receive the current user context or explicit `user_id`.
- Queries must filter by `user_id` before returning collection, sessions, analytics, integrations, AI history, or usage data.
- Cross-user access attempts return `404` or `403` consistently.
- Background jobs must store and run with the owning `user_id`.
- Job status, cancel, active-job, and progress endpoints must filter by owner before returning job metadata.

### Security

- Passwords are hashed with Argon2id by default.
- Bcrypt is an acceptable fallback only if deployment/runtime constraints make Argon2id impractical.
- Password hashing parameters must be configurable so production can tune memory, time, and parallelism cost without a schema change.
- Stored password hashes must include algorithm/version metadata so future rehash upgrades can happen at login.
- Confirmation/reset codes are stored hashed, expire quickly, and are single-use.
- Refresh tokens are stored hashed server-side.
- Access tokens include only minimal claims.
- Provider tokens remain encrypted at rest.
- Rate limits apply to registration, verification, login, reset, token refresh, and high-cost features.
- Structured audit events are recorded for auth-sensitive operations.

## Android Requirements

### First-Run Flow

- App launch checks for a valid local auth session.
- If no session exists, route to registration/sign-in instead of the main navigation graph.
- Registration, email verification, and optional setup are separate states in the auth flow.
- Optional setup can reuse existing Settings/Discogs token behavior where practical.

### Token Handling

- Store refresh tokens in Android secure storage.
- Keep access token in memory where possible.
- Refresh automatically on `401` when the refresh token is still valid.
- If refresh returns inactivity re-auth required, show password re-entry instead of a generic error.
- Clear tokens on logout, account deletion, or unrecoverable refresh failure.

### Local Data

- Any cached user data must be keyed by account or cleared on sign out.
- After account deletion, local collection/session/cache state must be cleared.
- Offline behavior should be explicit: previously loaded data can be shown only if it is clearly tied to the current authenticated account and does not bypass the one-week re-auth requirement.
- Limited offline read-only mode is not part of the first multi-user auth slice unless a separate local caching/read-only storage plan is approved.
- For this plan, password re-entry after one week should block the app rather than exposing cached user data behind a stale session.

## Migration Requirements

- Existing single-user data needs an owner before multi-user becomes mandatory.
- Because the project is still early, local development can use a full data reset for a clean multi-user migration test.
- Production rollout should define whether the first registered account claims existing unowned data or whether existing data is migrated through a future admin process.
- Unowned provider integration rows should be assigned to the migrated owner or rejected until resolved.
- Migration must preserve collection membership, listening history, analytics, and Discogs settings.

## Resolved Planning Decisions

- Email delivery starts with local/dev code delivery, then a configurable path for sending to one real test email, with production provider choice finalized later.
- Mailgun is the preferred first real provider candidate, with provider API favored for the first real-email test.
- SMTP fallback is out of scope for the first slice.
- Account deletion uses hard deletion for user-owned data plus minimal audit records.
- One-week inactivity blocks the app for this plan; limited offline read-only mode requires separate local caching work.
- Shared Discogs/catalog metadata is preferred long term, while personal/manual entries remain separate and user-owned.
- Manual releases are not automatically merged with Discogs; later Discogs matching should be an explicit suggestion/replacement flow.
- OCR/identify is the first obvious usage-counter candidate; AI chat can also be limited later but remains early-stage.

## Backend Implementation Phases

### Phase 1: Auth Schema And Core Domain

- Add user/account tables with email, verification state, password hash metadata, timestamps, and deletion state.
- Add auth session/device table with refresh token hash, last activity, expiry, revoked state, and device label.
- Add email verification and password reset code tables with hashed code, expiry, single-use state, and rate-limit metadata.
- Add entitlement and usage-counter foundation tables without billing integration.
- Add migration strategy for existing single-user data, with local/dev reset allowed if simpler.
- Done when migrations apply cleanly and model/repository tests cover create, lookup, revoke, expiry, and unique email behavior.

### Phase 2: Password Hashing And Token Lifecycle

- Implement Argon2id password hashing with configurable cost parameters and stored algorithm/version metadata.
- Add access-token issue/verify logic with short expiry and minimal claims.
- Add opaque refresh-token generation, hashing, rotation, reuse detection, and revocation.
- Handle concurrent refresh attempts with the same token by detecting duplicate consumed-token writes and revoking the owning session as refresh-token reuse.
- Add one-week inactivity detection based on backend activity/refresh timestamps.
- Done when unit tests cover password verify, future rehash compatibility, token expiry, token rotation, refresh-token reuse, and inactivity re-auth.

### Phase 3: Email Verification And Mailgun Delivery

- Implement email sender adapter with local/dev delivery first.
- Add Mailgun Provider API sender for real-email testing and production path.
- Add register, verify email, resend verification, reset request, and reset confirm service flows.
- Keep SMTP fallback out of scope for the first slice.
- Done when local verification is testable without email, Mailgun can send to a configured test inbox, and API tests cover expired/reused/wrong codes.

### Phase 4: Auth API And Default Protection

- Add versioned auth endpoints for register, verify email, resend verification, login, refresh, logout, current account summary, and password reset request/confirm.
- Add current-user dependency for authenticated routes.
- Deny access to application routers by default unless explicitly public.
- Keep auth bootstrap endpoints and minimal non-sensitive health/readiness endpoints public.
- Add structured error responses for missing auth, invalid/expired access token, revoked session, invalid/reused/expired refresh token, and inactivity re-auth required.
- Add Docker/local-dev auth configuration so local verification can be tested without Mailgun.
- Done when protected endpoint tests reject missing/invalid auth, auth API tests cover expired/reused/wrong codes, and the public allowlist is covered by route tests.

### Phase 5: User Scoping And Data Ownership

Phase 5 is split into explicit backend slices so early session/auth scoping does not imply full multi-user isolation.

#### Phase 5a: Settings, Integrations, Sessions, And Analytics

- Scope provider integrations, collection settings, sessions, session groups, release listening history, home summary, and analytics reads by `user_id`.
- Add nullable `user_id` ownership columns for legacy compatibility, set `user_id` on all new writes, and avoid hardcoded owner id/email assumptions.
- Treat concurrent or cross-account session-group access as not found/inactive by filtering group validation with the authenticated `user_id`.
- Done when User A cannot read or mutate User B integrations, collection settings, sessions, session groups, or session-backed analytics.

#### Phase 5b: Collection Ownership And Sync Jobs

- Split user-specific collection state from shared release/catalog metadata.
- Move `in_collection`, favorite state, collection added/removed timestamps, Discogs instance id, and per-user collection status out of shared `releases` rows.
- Add user-owned collection membership rows keyed by `user_id` and shared release/catalog id.
- Add user-owned folder metadata and release-folder membership for Discogs collection folders.
- Scope `GET /collection/releases`, release favorite updates, collection deactivate/reactivate, folder filters, and collection source-of-truth behavior to the authenticated user.
- Add `user_id` to collection sync jobs, active-job lookup, status lookup, progress updates, and stale-job expiry.
- Run collection sync with the owning user's saved Discogs token and collection settings.
- Done when User A cannot see, mutate, sync, favorite, remove, reactivate, or poll User B collection state or sync jobs.

Implementation note: this slice keeps Discogs/catalog release metadata shared, stores active collection state in `release_collection_memberships`, and scopes folder/sync-job tables by account. Legacy membership columns remain on `releases` for migration compatibility but are not the source of truth for new multi-user collection reads or writes.

Legacy upgrade requirement: existing single-user collection rows must be backfilled into `release_collection_memberships`. If exactly one active account exists, migration can use that account. If multiple active accounts exist, set `VINYL_LEGACY_OWNER_EMAIL` to the intended owner email before upgrading. If legacy collection state exists but no active account can be resolved, the migration must fail loudly instead of silently emptying the collection.

#### Phase 5c: Async Jobs, AI History, Spotify Data, And Usage Inputs

Status: implemented for backend identify jobs, AI chat history/tools, and Spotify import/rollup ownership.

- Add `user_id` to identify jobs and filter create/status/cancel by authenticated user.
- Use `user_id` rather than only client/IP keys for identify job ownership, while keeping client/IP keys for rate limiting where useful.
- Scope AI chat sessions/messages by `user_id`; the default local conversation id must not collide across accounts.
- Scope AI insight tools to user-owned sessions, analytics, collection membership, and imported Spotify data.
- Add `user_id` to Spotify import batches, events, rollups, artist/album stats, and vinyl match tables.
- Keep manual releases user-owned and separate from shared Discogs/catalog releases.
- Add optional user-owned association rows for later manual-to-Discogs "keep both" flows.
- Done when User A cannot read, mutate, cancel, analyze, export, or delete User B async jobs, AI history, Spotify imports, manual releases, or usage inputs.

Implementation note: the Phase 5c migration backfills legacy async/AI/Spotify rows to a resolved owner using `VINYL_LEGACY_OWNER_EMAIL` when needed. If legacy rows exist and no single active owner can be resolved, the migration fails loudly. AI chat stores an internal session id plus a user-scoped public conversation id so `local-single-thread` remains stable without cross-account collisions. Spotify rollups and match rows are rebuilt per user and match only against that user's active collection memberships.

### Phase 6: Account Management And Deletion

- Add password change, sign out, sign out everywhere, password reset, and account deletion flows.
- Account deletion hard-deletes user-owned data and provider tokens while retaining minimal audit records only.
- Shared Discogs/catalog metadata can remain only when no user-owned data remains attached.
- Done when deletion tests prove collection, sessions, analytics, AI history, manual releases, associations, integrations, sessions, and local token state contracts are removed or revoked.

### Phase 7: Entitlement And Usage-Counter Foundation

- Add backend capability checks using capability names rather than hard-coded plan names.
- Add usage event/counter recording for OCR/identify first.
- Add structured gated-feature errors that Android can map to upgrade messaging later.
- Leave billing/subscription provider integration out of scope.
- Done when OCR/identify usage can be counted per user and gated responses are deterministic in tests.

## Android Implementation Phases

### Phase 1: Auth State Gate And Splash

- Add startup auth gate before the main navigation graph.
- Show lightweight splash while local token state and backend refresh/validity checks run.
- Keep Home hidden until auth state is resolved.
- Show retryable splash error for no connection, timeout, server error, or transient startup failure.
- Done when app launch routes to Home, registration, password re-entry, or retryable splash error without briefly exposing user data.

### Phase 2: Registration And Email Verification

- Build registration, email verification, resend code, sign-in, and forgot-password entry screens.
- Keep validation inline and disable/no-op submits while required fields are invalid or requests are running.
- Support local/dev code testing and real Mailgun-delivered code testing.
- Done when fresh install can register, verify email, skip optional setup, and reach the main app.

### Phase 3: Secure Token Storage And Refresh

- Store refresh token in Android secure storage.
- Keep access token in memory where practical.
- Add API client behavior for access-token expiry, silent refresh, refresh rotation, revoked token, and inactivity re-auth required.
- Do not clear tokens on transient network failures.
- Done when normal refresh is silent and 7+ day inactivity routes to password re-entry.

### Phase 4: Optional Setup And Settings Integration

- Add post-verification optional setup screen with skip.
- Reuse existing Discogs token/settings behavior where practical.
- Preserve safe defaults when setup is skipped.
- Done when a verified user can skip setup, add a Discogs token, or return later through Settings.

### Phase 5: Account Security Screens

- Add password change, password reset confirmation, logout, and sign-out-everywhere UI.
- Add clear typed error handling for invalid password, expired reset code, rate limits, and revoked session.
- Done when account security flows match backend contracts and clear local session state when appropriate.

### Phase 6: Account Deletion And Local Cleanup

- Add Settings entry for delete account with explicit warning and password re-authentication.
- Clear secure tokens and user-keyed cached data after successful deletion.
- Return to registration after deletion completes.
- Done when deletion cannot leave the deleted user's data visible locally.

### Phase 7: Entitlement-Aware Client States

- Add client handling for structured gated-feature errors.
- For the first slice, map gated OCR/identify responses to a neutral limit/upgrade placeholder.
- Keep billing UI out of scope.
- Done when Android can display a clear state for a backend-denied usage-limited feature without crashing or retry loops.

## Validation Plan

### Backend

- Registration stores inactive account until email verification succeeds.
- Verification code accepts valid code once and rejects expired, reused, or wrong codes.
- Login rejects unverified accounts.
- Access token expires and refresh creates a rotated token pair.
- Refresh-token reuse revokes the session.
- Concurrent refresh-token reuse returns the typed reuse error and revokes the owning session instead of leaking a database integrity error.
- One-week inactivity returns a typed re-auth-required response.
- Password change/reset revokes expected sessions.
- Account deletion removes user-owned collection, sessions, analytics, AI history, and provider tokens.
- All protected endpoints reject missing/invalid tokens.
- User A cannot read, mutate, sync, or delete User B data.
- Existing single-user data migrates under an owner without losing history.

### Android

- Fresh install opens registration.
- Verified registration flows to optional setup and then main app.
- Skip optional setup leaves Discogs unset and source-of-truth defaults safe.
- Existing token refresh is silent during normal usage.
- One-week inactivity prompts for password and resumes after success.
- Sign out clears tokens and cached account data.
- Account deletion clears local state and returns to registration.

## Risks And Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| User-specific state remains on shared release rows | Cross-user data leakage | Split catalog metadata from collection membership before launch |
| Future async job tables remain global | One user can see or overwrite another user's background progress | Store `user_id` on job rows and run work with owner credentials |
| Identify jobs remain keyed only by client/IP | Job result or cancellation can cross accounts | Store `user_id` on identify jobs and filter status/cancel by owner |
| AI chat or Spotify imports remain global | User-specific insight context leaks between accounts | Scope chat history, Spotify imports, rollups, and insight tools by `user_id` |
| Refresh tokens behave like permanent passwords | Account takeover window grows | Use rotation, hashing, inactivity expiry, and revocation |
| Email verification/reset leaks account existence | Privacy issue | Use generic responses and rate limits |
| Account deletion misses derived analytics or AI history | Privacy and trust issue | Maintain a deletion checklist backed by integration tests |
| Subscription logic spreads into UI/API conditionals | Hard future migration | Centralize backend capability checks and structured gated errors |
| Multi-user migration breaks existing dev data | Lost testing baseline | For local development, allow a clean data reset until production migration rules are defined |
