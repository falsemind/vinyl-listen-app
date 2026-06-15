# Code Implementation Plan: Milestone 3 - Optional Discogs Integration

## M3 Goal
Introduce optional Discogs integration for single-user collection management while keeping the design ready for later multi-user auth. The app must work without a Discogs token, but token-backed features can unlock deeper backend integration, including image identify/OCR and collection sync.

Discogs request ownership is explicit:

- Backend owns authenticated Discogs requests made with a saved user token.
- Android owns unauthenticated direct-to-Discogs requests when no token is saved.
- Each caller applies its own Discogs rate limiter and respects Discogs response headers.

## Key Deliverables
1. **Integration Settings:** Add a Settings section named "Integrations" with an expandable Discogs card.
2. **Token Validation and Storage:** Validate tokens through `GET https://api.discogs.com/oauth/identity`, then securely store the token plus returned Discogs username and ID.
3. **Source of Truth Control:** Allow Discogs as collection source of truth only after a valid token is saved, with a destructive-impact confirmation dialog.
4. **Feature Gating:** Hide or disable Discogs-only actions when no token or Discogs release ID is available.
5. **Authenticated Backend Discogs Client:** Backend client, cache, mapper, and authenticated rate limiter for token-backed flows.
6. **Unauthenticated Android Discogs Client:** Device-side Discogs client with unauthenticated rate limiting for barcode/manual search flows that do not require a token.
7. **Capture Image Gate:** Disable "Take Photo" when no token is saved and explain that Integration Settings are required.

## Implementation Phases & Tasks

### Phase 1: Backend Integration Foundation
*(Goal: Store and validate Discogs credentials in a single-user shape that can become user-scoped later.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **1.1** | `Discogs Integration Model` | Add backend persistence for provider integration state. For now this can be a singleton/single-user row, but name the model so it can later be scoped by `user_id`. Store `provider = DISCOGS`, encrypted access token, Discogs `external_user_id`, `external_username`, timestamps, and active status. | Existing DB setup | Migration and repository/service contract for Discogs integration settings. |
| **1.2** | `Token Encryption` | Store the Discogs token encrypted or through the backend's secure secret mechanism. Never return the raw token to Android after save. | 1.1 | Secure token persistence helper and tests. |
| **1.3** | `Token Validation` | On token submit, call `GET https://api.discogs.com/oauth/identity`. Save the token only when the response returns usable username and ID. | 1.1, 1.2 | Backend endpoint that validates, saves, and returns sanitized integration status. |
| **1.4** | `Integration Status API` | Expose sanitized state for Android: token saved boolean, Discogs username/ID, source-of-truth value, and whether backend identify is enabled. | 1.3 | `GET`/`PUT` style settings endpoints without raw token exposure. |

### Phase 2: Settings UX and Source of Truth
*(Goal: Make Discogs optional and explicit in Settings.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **2.1** | `Settings Integrations Section` | Add a Settings section with header "Integrations". Add an expandable "Discogs" card/spoiler styled like Record Details Insights. | Existing Settings UI | Settings UI section and expanded/collapsed state. |
| **2.2** | `Token Entry State` | When no token is saved, show token input plus `Add` button. Disable submit while blank. Show backend validation errors inline. | 1.4, 2.1 | Add-token state wired to backend validation. |
| **2.3** | `Token Saved State` | When a token is saved, show a green checkmark, "Access token saved", optionally "for <username>", and an `Update` button. `Update` returns to token input state. | 2.2 | Saved-token state and update flow. |
| **2.4** | `Source of Truth Toggle` | Show "Collection source of truth" only after a valid token is saved. Allow switching to Discogs only after confirmation. | Existing collection settings | Toggle UI and confirmation dialog. |
| **2.5** | `Discogs Source Confirmation` | Warn that changing source of truth to Discogs may override the active in-app collection and records missing from the Discogs collection may be removed from the active collection/inactivated. | 2.4 | Confirmation dialog copy and acceptance handling. |

### Phase 3: Backend Authenticated Discogs Client
*(Goal: Support token-backed server flows such as image identify/OCR and collection sync.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **3.1** | `Authenticated Discogs Client` | Create backend Discogs client using the saved token for authenticated requests. Include base URL, authenticated headers, User-Agent, JSON error parsing, and sanitized logging. | 1.3 | Backend client that can call Discogs with the saved token. |
| **3.2** | `Backend Rate Limiter` | Apply rate limiting at the backend caller boundary for authenticated requests. Default to 60 requests/minute, use a moving 60-second window, and update behavior from Discogs rate-limit headers when present. | 3.1 | Backend limiter keyed by singleton integration now, later by app user. |
| **3.3** | `Discogs Headers Handling` | Read `X-Discogs-Ratelimit`, `X-Discogs-Ratelimit-Used`, and `X-Discogs-Ratelimit-Remaining`. Respect headers over local defaults when they are stricter or indicate lower remaining capacity. | 3.2 | Header-aware limiter state and tests. |
| **3.4** | `Release Cache` | Add or update `discogs_release_cache` for release metadata payloads and cache expiration. Cache must not expose private token data. | 3.1 | Migration/repository/service logic for cached release payloads. |
| **3.5** | `Search and Fetch Methods` | Implement backend search/fetch methods needed by token-backed flows: barcode search, structured search where needed, and full release fetch by Discogs release ID. | 3.4 | Backend service methods returning normalized results. |
| **3.6** | `Identify Pipeline Integration` | When token is saved, image capture can send to backend OCR/identify. Backend performs Discogs calls and returns candidates/results to Android. | 3.5 | Token-backed image identify flow; Android receives final candidates only. |

### Phase 4: Android Unauthenticated Discogs Client
*(Goal: Preserve limited Discogs functionality without requiring a token.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **4.1** | `Device Discogs Client` | Add/update Android API client for direct unauthenticated Discogs calls used by barcode/manual search when no token is saved. | Existing manual search/barcode flows | Device-side client separate from backend API client. |
| **4.2** | `Android Rate Limiter` | Apply unauthenticated local rate limiting on Android. Default to 25 requests/minute, use a moving 60-second window, and update from Discogs headers when present. | 4.1 | Device-side limiter with tests. |
| **4.3** | `User-Agent` | Send a unique User-Agent containing app name/version and a stable per-install ID. Generate the install ID once and store locally; do not use hardware identifiers. | 4.1 | User-Agent provider and install ID storage. |
| **4.4** | `Unauthenticated Error UX` | If rate limit or Discogs access fails, show a clear retry/limit message without suggesting backend token-backed flows are running. | 4.2 | User-facing error handling for direct Discogs calls. |

### Phase 5: Feature Gating and Collection Actions
*(Goal: Keep UI actions consistent with whether Discogs token/release data exists.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **5.1** | `Collection Actions Gate` | If no token is saved, hide or disable Load/Sync Discogs collection actions. | 1.4 | Collection screen action state tied to integration status. |
| **5.2** | `Record Detail Import Gate` | If no token is saved, do not allow import-full-release for records created manually through the placeholder/manual-entry path. | 1.4 | Record detail action filtering. |
| **5.3** | `View on Discogs Gate` | Show "View on Discogs" only when a record has a known Discogs release ID, such as records imported from identify/barcode/manual Discogs search. Do not show for manual-entry records without release ID. | Existing record model fields | Action-menu rules based on release ID presence. |
| **5.4** | `Capture Image Gate` | When no token is saved, keep `Take Photo` visible but disabled. Add an info icon near the capture action. On tap, show: "To enable this feature, please provide your Discogs access token in the app's Integration Settings." | 1.4 | Disabled button state and explanatory dialog. |

### Phase 6: Testing
*(Goal: Verify security, request ownership, rate limiting, and UI gates.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **6.1** | `Backend Integration Tests` | Cover token validation success/failure, identity response parsing, sanitized status responses, source-of-truth updates, and token storage without raw-token reads. | Phases 1-3 | Focused backend API/service tests. |
| **6.2** | `Backend Rate Tests` | Simulate authenticated Discogs responses with rate-limit headers and quota exhaustion. | 3.2, 3.3 | Header-aware limiter tests. |
| **6.3** | `Android Parser/API Tests` | Cover integration status parsing, token saved/unsaved states, and unauthenticated rate-limit header handling. | Phases 2, 4 | Focused Android tests. |
| **6.4** | `Android UI State Tests` | Cover Settings Discogs card states, source-of-truth confirmation, disabled Take Photo state, and record action visibility. | Phases 2, 5 | UI/state tests around gated actions. |

## Flow Summary

### Token Saved
1. Android reads integration status from backend.
2. Capture image is enabled.
3. Image identify sends capture to backend OCR/identify pipeline.
4. Backend calls Discogs with saved token.
5. Backend authenticated limiter applies 60/min default and respects Discogs headers.
6. Backend returns candidates/results to Android.

### No Token Saved
1. Backend does not perform Discogs-backed image identify/import work.
2. Capture image `Take Photo` is disabled with an info dialog pointing to Integration Settings.
3. Barcode/manual Discogs search can call Discogs directly from Android.
4. Android unauthenticated limiter applies 25/min default and respects Discogs headers.

### Collection Source of Truth
1. App remains the default source of truth.
2. Discogs source of truth is available only after a valid token and identity are saved.
3. Switching to Discogs requires confirmation because active in-app collection records missing from Discogs may be inactivated.
