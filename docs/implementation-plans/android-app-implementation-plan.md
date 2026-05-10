# Code Implementation Plan: Milestones 7-8 — Android App Prototype

## M7/M8 Goal

Build the Android MVP prototype in Kotlin + Jetpack Compose using the completed screen mockups, product specs, navigation graph, and backend API contracts.

Current scope includes:

- Home
- Capture Record
- Processing
- Match Confirmation
- Manual Search
- Session Logging
- Record Detail

Current scope excludes:

- Analytics screen implementation
- Settings screen implementation
- Backend analytics integration

Analytics remains a later roadmap item after backend analytics work is ready.

## Source Documents

- `docs/architecture/roadmap.md`
- `docs/architecture/navigation-graph.md`
- `docs/product/mvp-screen-spec.md`
- `docs/product/app-design-system.md`
- `docs/product/app-screens-mockups/*.tsx`
- `docs/product/app-screens-mockups/*.png`
- `docs/features/backend-services.md`
- `docs/features/identification-pipeline.md`

## Current Android Baseline

The Android project exists under `android-app/` and already has:

- Android Gradle project structure
- Kotlin + Compose enabled
- Material 3 dependency
- `activity-compose`
- ktlint and detekt wiring
- Starter `MainActivity.kt` with placeholder `Greeting`

The app still needs:

- Compose Navigation dependency and route setup
- UI package/module structure
- Design-system primitives
- Prototype data models and mock data
- Backend API client layer
- Camera/gallery image flow
- Real screen implementations

## Backend API Alignment

Android navigation routes are not backend paths.

`releaseId` in Android routes must mean the backend internal `release_id`, not `discogs_release_id`.

Current backend endpoints to support this implementation:

| Flow | Backend API |
| :--- | :--- |
| Identify uploaded/captured image | `POST /api/v1/identify` |
| Import Discogs release before logging | `POST /api/v1/releases/import` |
| Load record detail metadata | `GET /api/v1/releases/{release_id}` |
| Load record session history | `GET /api/v1/releases/{release_id}/sessions` |
| Create listening session | `POST /api/v1/sessions` |
| Load one session by id | `GET /api/v1/sessions/{session_id}` |

Manual Search is UI-only for the current prototype because the backend does not yet expose a dedicated manual Discogs search endpoint. Implement it with mock results or local prototype data first.

## Implementation Phases & Tasks

### Phase 1: Android Foundation Cleanup

*(Goal: replace starter app structure with a maintainable Compose app skeleton.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **1.1** | `MainActivity` | Replace the starter `Greeting` content with the real app root. Keep `enableEdgeToEdge()` and wrap the app in the project theme. | Existing Android project | `MainActivity` launches `VinylListenApp()` |
| **1.2** | Package Structure | Add packages for `ui.theme`, `ui.components`, `ui.screens`, `navigation`, `data`, and `domain`. | 1.1 | Clear app structure for prototype work |
| **1.3** | Dependencies | Add Compose Navigation. Add image loading and HTTP dependencies only if used in the first implementation pass. | Gradle version catalog | Build can support routing and planned API/image work |
| **1.4** | App State Strategy | Define simple screen-level state holders. Use mock data first; avoid overbuilding architecture before the prototype screens exist. | 1.2 | Lightweight state model ready for UI |

### Phase 2: Design System Implementation

*(Goal: implement reusable Compose primitives before screens so visual consistency is not hand-coded per screen.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **2.1** | `VinylColors` | Implement color tokens from `app-design-system.md`: dark background/surfaces, green/orange/purple accents, text colors, border colors. | Design system doc | Central color source |
| **2.2** | `VinylSpacing` / `VinylShapes` | Add spacing and shape tokens matching the mockups: 12dp, 16dp, 24dp radii; 24dp screen padding; bottom inset padding. | Design system doc | Shared layout tokens |
| **2.3** | Glass Buttons | Build `GlassPrimaryButton` for full-width CTAs and `FloatingGlassButton` for `Log Session` / `Add Session`. Approximate CSS blur with translucent gradient, soft shadow, and green border. | 2.1, 2.2 | Reusable glass CTA components |
| **2.4** | Core Components | Build `AccentCard`, `SecondaryButton`, `IconCircleButton`, `ConfidenceChip`, `MoodChip`, `RatingStars`, `BottomNavBar`. | 2.1-2.3 | Components needed by all screens |
| **2.5** | Preview Fixtures | Add preview/mock records, candidates, sessions, and moods. | 2.4 | Compose previews render realistic UI |

### Phase 3: Navigation Graph

*(Goal: implement the current prototype route graph with correct identifiers and placeholder future tabs.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **3.1** | Routes | Define route constants for `home`, `capture_record`, `processing`, `match_confirmation`, `manual_search`, `session_logging/{releaseId}`, and `record_detail/{releaseId}`. | Phase 1 | Typed route helpers where useful |
| **3.2** | NavHost | Implement Compose `NavHost` from `docs/architecture/navigation-graph.md`. | 3.1 | Main app navigation runs |
| **3.3** | Placeholder Tabs | Keep Stats/Analytics and Settings bottom-nav items inert or placeholder-only. Do not implement analytics screens in this phase. | 3.2 | Bottom nav matches mockup without expanding scope |
| **3.4** | Route Arguments | Treat `releaseId` as backend internal `release_id`. Do not pass `discogs_release_id` into `record_detail/{releaseId}`. | 3.1 | Correct backend/client ID contract |

### Phase 4: Static Screen Implementation

*(Goal: translate the TSX/PNG mockups into Compose screens with mock data and real navigation.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **4.1** | Home | Implement recent sessions, collection snapshot, top records, bottom nav, and floating `Log Session` glass button. | Phase 2, 3 | Home matches mockups |
| **4.2** | Capture Record | Implement camera-preview layout shell, hint card, `Take Photo`, `Upload`, and `Manual Search`. | Phase 2, 3 | Capture screen matches mockup |
| **4.3** | Processing | Implement progress states: uploading image, extracting text, searching candidates. | Phase 2, 3 | Processing screen matches mockup |
| **4.4** | Match Confirmation | Implement candidate cards, confidence chips, confirm buttons, details affordance placeholder, show more, manual search. The details affordance should represent pre-confirmation candidate/release details, not the saved record detail screen. | Phase 2, 3 | Match screen matches mockup |
| **4.5** | Manual Search | Implement fields, search CTA, and mock result list. | Phase 2, 3 | Manual search screen matches mockup |
| **4.6** | Session Logging | Implement release summary, side selector, rating stars, mood chips, custom mood affordance, notes, cancel/save actions. | Phase 2, 3 | Logging screen matches mockup |
| **4.7** | Record Detail | Implement record metadata, Discogs button, stats cards, mood bars, history list, floating `Add Session`, bottom home action. | Phase 2, 3 | Record detail screen matches mockups |
| **4.8** | Scroll Safety | Add bottom padding to scrollable screens so floating CTAs and bottom bars do not cover content. | 4.1-4.7 | No blocked final list rows/actions |

### Phase 5: Device Capabilities And API Integration

*(Goal: replace prototype-only transitions with real capture/upload/identify/session flows where backend support exists.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **5.1** | Camera Permission | Add runtime camera permission handling. | Phase 4 | Capture can request camera access |
| **5.2** | Image Capture / Upload | Implement camera capture and gallery picker. Pass selected image into processing flow. | 5.1 | Real image input path |
| **5.3** | API Client | Add backend client with base URL config for emulator/local dev. | Phase 1 | Android can call `/api/v1` |
| **5.4** | Identify Flow | Upload image to `POST /api/v1/identify`, show candidates, handle empty/error states. | 5.2, 5.3 | Real identify-to-match flow |
| **5.5** | Release Import Flow | If identify candidate has no `release_id`, call `POST /api/v1/releases/import` before navigating to logging/detail. | 5.4 | Correct Discogs-to-internal ID flow |
| **5.6** | Session Flow | Create session with `POST /api/v1/sessions`; then navigate to `record_detail/{releaseId}`. | 5.3, 5.5 | Real session logging |
| **5.7** | Record Detail Flow | Load release metadata and session history via release endpoints. | 5.3 | Detail screen shows backend data |
| **5.8** | Candidate Detail Flow | Replace the Match Confirmation details placeholder with candidate release details before confirmation: Discogs metadata, catalog/format data, and match evidence from identify/OCR. Keep this separate from saved Record Detail, which includes listening stats and session history. | 5.3, 5.4, 5.5 | Candidate details clarify a match before import/logging |

### Phase 6: Error, Empty, And Loading States

*(Goal: make the prototype usable beyond the happy path.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **6.1** | Identify Errors | Show retry/manual-search options for upload, OCR, or backend failures. | 5.4 | Recoverable processing failures |
| **6.2** | Empty Matches | Navigate to Manual Search or show no-match state when identify returns no candidates. | 5.4 | Clear no-results behavior |
| **6.3** | Manual Search Placeholder | Label/manual-code the mock-data limitation internally so it can be swapped when backend search exists. | 4.5 | Future backend route has clean insertion point |
| **6.4** | Session Validation | Surface rating/side/mood validation errors from backend responses. | 5.6 | User sees actionable form errors |
| **6.5** | Offline / Base URL Failure | Add a friendly backend unavailable state for local development. | 5.3 | Easier dev testing |

### Phase 7: Verification And Polish

*(Goal: ensure the app builds, screens match mockups, and flow regressions are caught.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **7.1** | Static Previews | Add previews for key screens and core components. | Phase 4 | Visual review without running full app |
| **7.2** | Compose UI Tests | Add smoke tests for navigation and important CTAs. | Phase 3, 4 | Basic UI safety net |
| **7.3** | Build Checks | Run Android lint, ktlint, detekt, unit tests, and assemble. | All implementation | Clean verification pass |
| **7.4** | Mockup Review | Compare implemented screens against TSX/PNG mockups, focusing on color tokens, glass CTAs, spacing, scroll behavior, and route flow. | 7.3 | Prototype ready for user review |

## Recommended Initial Commit Boundaries

1. Android dependency and app skeleton setup.
2. Design-system primitives and preview data.
3. Navigation graph and static mock screens.
4. Camera/gallery and processing flow.
5. Backend API integration for identify, release import, sessions, and record detail.
6. Error states and verification polish.

## Open Questions Before API Wiring

- What base URL should Android use for local backend development on emulator and physical device?
- Should Manual Search remain fully mocked until a backend endpoint exists, or should Android call Discogs directly for prototype testing?
- Should the first Android pass use real camera preview, or a capture intent/gallery picker first to reduce complexity?
- Should album thumbnails use remote URLs directly, or should the app cache them after backend response?

## Done Criteria

The Android prototype is ready when:

- App launches into Home.
- User can navigate through Home -> Capture -> Processing -> Match Confirmation -> Session Logging -> Record Detail.
- Manual Search route works with prototype data.
- Glass buttons, dark surfaces, chips, ratings, and bottom nav match the TSX mockups closely.
- `releaseId` route arguments use backend internal `release_id`.
- Analytics and Settings are not implemented beyond placeholder/inert navigation affordances.
- App builds and passes configured formatting/lint/test checks.
