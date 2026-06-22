---
name: navigation-graph
description: This document explains Android Navigation Graph Specification.
---

# Vinyl Listening App — Android Navigation Graph Specification (MVP)

## Purpose

Define the navigation structure for the Android application built with **Kotlin + Jetpack Compose**.
This specification maps screens to **navigation routes, arguments, and transitions**.

It supports implementation using **Jetpack Compose Navigation**.

---

# Navigation Overview

Primary navigation structure:

```
Home
 ├── RecentSessions
 │      └── RecordDetail
 │             └── SessionLogging
 │
 ├── CaptureRecord
 │     ├── Processing
 │     │     ├── MatchConfirmation
 │     │     │      └── SessionLogging
 │     │     │             └── RecordDetail
 │     │     │                    └── Home
 │     │     │
 │     │     └── ManualSearch
 │     │            └── SessionLogging
 │     │                   └── RecordDetail
 │     │
 │     └── BarcodeProcessing
 │            ├── MatchConfirmation
 │            └── ManualSearch
 │
 ├── RecordDetail
 │      └── SessionLogging
 │
 ├── Analytics
 │      ├── TopRecords
 │      │      └── RecordDetail
 │      └── RecordDetail
 │
 └── Collection
        ├── Settings
        ├── CaptureRecord (collection_add)
        │     ├── Processing
        │     ├── BarcodeProcessing
        │     └── MatchConfirmation
        │            └── RecordDetail
        ├── ManualSubmissions
        │      └── ManualReleaseForm
        │             ├── ManualSubmissions
        │             └── RecordDetail
        └── CollectionManualSearch
```

Home, Analytics, Insights, and Collection are active bottom-navigation routes. Settings is reachable from the Home header icon and from the Collection action menu. Analytics loads the implemented dashboard endpoints, Insights shows the single-thread AI chat shell, and Collection loads active app collection records with optional Discogs metadata sync.

---

# Navigation Routes

|Screen|Route|
|---|---|
|Home|`home`|
|Recent Sessions|`recent_sessions`|
|Capture Record|`capture_record?flowMode={flowMode}`|
|Processing|`processing?imageUri={imageUri}&flowMode={flowMode}`|
|Barcode Processing|`barcode_processing?barcode={barcode}&flowMode={flowMode}`|
|Match Confirmation|`match_confirmation?flowMode={flowMode}`|
|Manual Search|`manual_search?barcode={barcode}`|
|Collection Manual Search|`collection_manual_search`|
|Manual Submissions|`collection_manual_entry`|
|Manual Release Form|`collection_manual_form?draftId={draftId}`|
|Session Logging|`session_logging/{releaseId}`|
|Record Detail|`record_detail/{releaseId}`|
|Analytics|`analytics`|
|AI Insights|`ai_insights`|
|Collection|`collection`|
|Top Records|`top_records`|
|Settings|`settings`|
---

## Backend API Alignment

Navigation routes are client-side Compose routes. They are not backend endpoint paths.

`releaseId` means the backend's internal release identifier, returned as `release_id`. It is not the Discogs release id.

Current backend endpoints used by these routes:

|Client flow|Backend API|
|---|---|
|Load Home dashboard data|`GET /api/v1/sessions/summary`|
|Load Recent Sessions expanded list|`GET /api/v1/sessions/summary?recent_limit=250`|
|Identify uploaded/captured image with progress|`POST /api/v1/identify/jobs`, then `GET /api/v1/identify/jobs/{job_id}`|
|Cancel active identify job|`POST /api/v1/identify/jobs/{job_id}/cancel`|
|Identify uploaded/captured image synchronously|`POST /api/v1/identify`|
|Manual Discogs search|`GET /api/v1/releases/search`|
|Barcode scan release search|`GET /api/v1/releases/search?barcode={barcode}`|
|Import a Discogs release before logging with backend token|`POST /api/v1/releases/import`|
|Import a client-fetched Discogs release|`POST /api/v1/releases/import/client-discogs`|
|Import and activate a Discogs release with backend token|`POST /api/v1/releases/import-to-collection`|
|Load record detail metadata|`GET /api/v1/releases/{release_id}`|
|Deactivate release collection membership|`POST /api/v1/releases/{release_id}/collection/deactivate`|
|Reactivate release collection membership|`POST /api/v1/releases/{release_id}/collection/reactivate`|
|Load record listening history|`GET /api/v1/releases/{release_id}/sessions`|
|Load collection settings|`GET /api/v1/collection/settings`|
|Update collection settings|`PUT /api/v1/collection/settings`|
|Start Discogs collection sync|`POST /api/v1/collection/sync`|
|Resume active Discogs collection sync|`GET /api/v1/collection/sync/active`|
|Poll Discogs collection sync|`GET /api/v1/collection/sync/{job_id}`|
|Load Records Collection list|`GET /api/v1/collection/releases?limit=25&offset={offset}`|
|Manual collection search|`GET /api/v1/collection/search`|
|List manual release drafts|`GET /api/v1/manual-releases/drafts`|
|Create manual release draft|`POST /api/v1/manual-releases/drafts`|
|Update manual release draft|`PUT /api/v1/manual-releases/drafts/{draft_id}`|
|Delete manual release draft|`DELETE /api/v1/manual-releases/drafts/{draft_id}`|
|Upload manual release draft cover|`POST /api/v1/manual-releases/drafts/{draft_id}/cover`|
|Save manual release to collection|`POST /api/v1/manual-releases`|
|Create listening session|`POST /api/v1/sessions`|
|Start timed listening session|`POST /api/v1/sessions/groups`|
|Load active timed listening session|`GET /api/v1/sessions/groups/active`|
|Stop timed listening session|`PATCH /api/v1/sessions/groups/{session_group_id}/finish`|
|Load custom moods|`GET /api/v1/sessions/moods`|
|Create custom mood|`POST /api/v1/sessions/moods`|
|Delete custom mood|`DELETE /api/v1/sessions/moods/{mood_name}`|
|Load one session by id|`GET /api/v1/sessions/{session_id}`|
|Load Analytics dashboard|`GET /api/v1/analytics/plays/monthly`, `GET /api/v1/analytics/top-records`, `GET /api/v1/analytics/rating-distribution`, `GET /api/v1/analytics/mood-distribution`|

The identify job flow returns candidates inside `result` when the job reaches `completed`. The synchronous `POST /api/v1/identify` flow returns the same candidate shape directly.

Barcode scan starts from the existing `CaptureRecord` camera preview. After a stable on-device UPC/EAN read, the client shows a short captured state, opens `barcode_processing?barcode={barcode}`, searches releases by barcode, and routes to the same match confirmation candidates used by image identify. No-result, timeout, and API failure states can retry scanning, open manual search with the barcode prefilled, or cancel back out of the identify flow.

`flowMode` is `session` by default and `collection_add` when the Records Collection add camera option starts the flow. Session mode confirms into Session Logging. Collection-add mode confirms into a collection save: existing local candidates reactivate membership directly, while Discogs-only candidates are fetched on-device, imported with `POST /api/v1/releases/import/client-discogs`, reactivated with `POST /api/v1/releases/{release_id}/collection/reactivate`, and then opened in Record Detail.

Identify candidates include:

```
discogs_release_id
release_id
```

If `release_id` is present, the app can navigate to:

```
session_logging/{releaseId}
record_detail/{releaseId}
```

If only `discogs_release_id` is available in session mode, the app must import the release first. Token-backed callers can use:

```
POST /api/v1/releases/import
then
release_id returned
then
session_logging/{releaseId}
```

Android no-token manual search and barcode search use `DiscogsApiClient` directly on the device. Search results do not have an internal `release_id`, so the app fetches the selected full Discogs release, imports it with `POST /api/v1/releases/import/client-discogs`, then navigates to `session_logging/{releaseId}`.

Collection Manual Search uses the same screen shell but calls `GET /api/v1/collection/search`. Results include internal `release_id`, so selecting one navigates directly to `record_detail/{releaseId}` without importing from Discogs.

Manual Submissions manages user-owned drafts and manual releases. It opens `collection_manual_form` for a new release and `collection_manual_form?draftId={draftId}` to resume a draft. Saving a draft pops back to Manual Submissions and refreshes the draft list. Saving a release creates the manual release, refreshes Manual Submissions and Collection state, then opens `record_detail/{releaseId}`. The Record Detail back action returns to Collection because the form save pops up to the Collection graph entry.

# Screen Navigation Details

---

# 1. Home Screen

### Route

```
home
```

### Possible Navigation Actions

|Action|Destination|
|---|---|
|Log Listening Session|`capture_record`|
|Tap recent session|`record_detail/{releaseId}`|
|Tap Recent Sessions View All|`recent_sessions`|
|Tap record|`record_detail/{releaseId}`|
|Tap Analytics/Stats tab|`analytics`|
|Tap Settings tab|`settings`|

### Backend Data

Home loads real dashboard data from:

```
GET /api/v1/sessions/summary
```

The response provides recent sessions, total session count, records played this month, and top record summaries. Recent session items include nullable `session_group_id`. The Android app keeps local prototype data as a fallback when the backend is unavailable.

The app loads the active timed session with `GET /api/v1/sessions/groups/active` when the nav host starts. While active, a green timer chip appears below screen headers on app screens except the identify camera, processing, and candidate confirmation flow.

---

# 2. Recent Sessions Screen

### Route

```
recent_sessions
```

### Purpose

Expanded recent-listening screen opened from Home.

### Backend Data

```
GET /api/v1/sessions/summary?recent_limit=250
```

Rows with the same non-null `session_group_id` render as one green timed-session container with metadata chips and green-bordered child session cards. Sessions with `session_group_id = null` render as normal standalone cards. Grouping currently happens on the fetched list, so a timed session that extends beyond the fetched limit can still be split until a backend mixed-feed endpoint exists.

### Actions

|Action|Destination|
|---|---|
|Tap session|`record_detail/{releaseId}`|
|Back|previous screen|

---

# 3. Capture Record Screen

### Route

```
capture_record
```

### Actions

|Action|Destination|
|---|---|
|Take photo|`processing`|
|Upload photo|`processing`|
|Manual search|`manual_search`|

### Arguments Passed

```
imageUri
```

---

# 4. Processing Screen

### Route

```
processing?imageUri={imageUri}
```

### Purpose

Displays processing progress while the backend identifies the record.

The screen starts an identify job, polls the job endpoint, and maps backend statuses into upload, text extraction, candidate search, and canceled states. Terminal job errors include `failed_step`, which identifies whether upload, extraction, search, or an unknown backend phase failed.

While the identify job is active, normal system back navigation is consumed by the screen. The top-left cancel button is the only supported active-job exit path. It sends a best-effort cancel request, stops local polling pressure, and returns home once the local cancel flow starts or a terminal backend status is received.

### Possible Results

|Result|Destination|
|---|---|
|Matches found|`match_confirmation`|
|No matches|`manual_search`|
|Cancel active identify|`home`|

---

# 5. Match Confirmation Screen

### Route

```
match_confirmation
```

### Displays

List of candidate releases retrieved from the Discogs search.

### Actions

|Action|Destination|
|---|---|
|Confirm release|`session_logging/{releaseId}`|
|Show more matches|refresh results|
|Manual search|`manual_search`|

### Arguments Passed

```
releaseId
```

---

# 6. Manual Search Screen

### Route

```
manual_search
```

### Purpose

Fallback record search when automatic identification fails.

### Search Fields

```
artist
title
catalog_number
barcode
year
```

### Actions

|Action|Destination|
|---|---|
|Select release|`session_logging/{releaseId}`|
|Show more|same screen with next search page|

---

# 7. Session Logging Screen

### Route

```
session_logging/{releaseId}
```

### Arguments

```
releaseId (required)
```

### Purpose

Log listening session for selected record.

When the active timed-session chip has auto-add enabled, saving a session sends the active `session_group_id` with `POST /api/v1/sessions`. The user can disable auto-add from the chip and still log standalone sessions while the timer runs.

### Actions

|Action|Destination|
|---|---|
|Save session|`record_detail/{releaseId}`|
|Cancel|`home`|

---

# 8. Record Detail Screen

### Route

```
record_detail/{releaseId}
```

### Arguments

```
releaseId (required)
```

### Displays

```
record metadata
listening statistics
session history
```

### Actions

|Action|Destination|
|---|---|
|Add session|`session_logging/{releaseId}`|
|Back|previous screen, or `home` when there is no back stack|

# 9. Analytics Screen

### Route

```
analytics
```

### Purpose

Listening statistics and charts. The screen loads monthly plays, top records, rating distribution, and mood distribution from backend analytics endpoints.

### Navigation

|Action|Destination|
|---|---|
|Tap record in chart|`record_detail/{releaseId}`|
|Tap Top Records View All|`top_records`|
|Back|`home`|

---

# 10. Top Records Screen

### Route

```
top_records
```

### Purpose

Expanded top-records screen opened from Analytics.

### Backend Data

```
GET /api/v1/analytics/top-records
```

The screen displays up to 25 records.

### Navigation

|Action|Destination|
|---|---|
|Tap record|`record_detail/{releaseId}`|
|Back|previous screen|

---

# 11. Records Collection Screen

### Route

```
collection
```

### Purpose

Browser for active app collection membership with optional Discogs sync and add-entry shortcuts.

### Displays

- Header and action-menu toggle remain visible when the collection is empty
- Import/sync progress with centered status feedback
- Error state with orange error text and centered `Retry Load`
- Latest 25 active collection records by Discogs added date
- `Show More` pagination in 25-record pages
- First action menu item: `Collection settings`, with green settings icon
- `Load Discogs collection` action when Discogs credentials exist and the unfiltered collection is empty
- `Sync Items` action after collection records are loaded, with green sync icon
- Expandable `Collection folders` action when Discogs credentials exist and imported folders include non-default folders
- Green filter chips with result counters for artist, label, favorites, and Discogs folder filters
- Green add CTA above the search CTA. The plus expands left into camera and pencil options, and turns into an X while expanded.
- Scroll-to-top CTA appears above the add CTA when the list is scrolled.

### Navigation

|Action|Destination|
|---|---|
|Tap record|`record_detail/{releaseId}`|
|Tap Collection settings action|`settings`|
|Tap Load Discogs collection / Sync Items|stays on `collection` and follows background sync status|
|Tap Collection folders row|expands/collapses folder options|
|Tap folder option|stays on `collection` with `folder_id` filter and green folder chip|
|Clear folder chip|stays on `collection` and reloads unfiltered active records|
|Tap add camera option|`capture_record?flowMode=collection_add`|
|Tap add pencil option|`collection_manual_entry`|
|Tap search CTA|`collection_manual_search`|
|Tap Home tab|`home`|
|Tap Stats tab|`analytics`|
|Tap Insights tab|`ai_insights`|

---

# 12. Manual Submissions Screen

### Route

```text
collection_manual_entry
```

### Purpose

Draft hub for app-owned manual releases. This route replaces the old manual-entry placeholder.

### Displays

- Screen title: `Manual Submissions`
- Draft cards for up to 5 saved manual release drafts
- Draft card delete confirmation
- Add Release CTA
- Draft-limit dialog when the user already has 5 drafts

### Navigation

|Action|Destination|
|---|---|
|Tap Add Release|`collection_manual_form`|
|Tap draft card|`collection_manual_form?draftId={draftId}`|
|Save draft from form|returns to `collection_manual_entry` and refreshes draft cards|
|Save release from form|`record_detail/{releaseId}`|
|Cancel form|returns to `collection_manual_entry`|
|Tap Home tab|`home`|
|Tap Stats tab|`analytics`|
|Tap Insights tab|`ai_insights`|
|Tap Collection tab|`collection`|

### Form Route

```text
collection_manual_form?draftId={draftId}
```

`draftId` is optional. When absent, the form starts a new manual release. When present, the form loads and updates that draft before draft save or release save.

Saving a release posts to `POST /api/v1/manual-releases`, removes the source draft when applicable, refreshes Collection and Manual Submissions state, and navigates to Record Detail. From that Record Detail screen, back returns to Collection.

---

# 13. Settings Screen

### Route

```
settings
```

### Purpose

Screen for app configuration, including collection source-of-truth selection.

### Displays

- App version  
- Build number  
- Basic application information
- `Collection source of truth: App` or `Collection source of truth: Discogs`
- Toggle ON for App-owned collection membership; toggle OFF for Discogs source selection

### Notes

The collection source toggle is functional. `App` mode preserves local collection membership during Discogs sync. `Discogs` mode persists the user's preference for future mirror behavior.

This screen can still support future configuration features such as:

- preferences  
- account management  
- integrations  

### Navigation

|Action|Destination|
|---|---|
|Back|`home`|

---

# 14. AI Insights Screen

### Route

```
ai_insights
```

### Purpose

Single-thread chat shell for future AI-assisted listening insights.

### Displays

- Screen title: `Insights`
- Suggested prompts
- Message list
- Text input
- Send action

### Navigation

|Action|Destination|
|---|---|
|Tap Home tab|`home`|
|Tap Stats tab|`analytics`|
|Tap Collection tab|`collection`|

# Navigation Argument Definitions

|Argument|Type|Description|
|---|---|---|
|releaseId|String|Internal backend release identifier returned as `release_id`|
|imageUri|String|Local URI of captured photo|
|barcode|String|Optional UPC/EAN value passed into barcode processing or manual search|
|flowMode|String|Identify flow mode: `session` or `collection_add`|
|draftId|String?|Optional manual release draft id for `collection_manual_form`|

---

# Example Compose Navigation Setup

Example navigation configuration:

```kotlin
NavHost(
    navController = navController,
    startDestination = "home"
) {

    composable("home") {
        HomeScreen()
    }

    composable("recent_sessions") {
        RecentSessionsScreen()
    }

    composable("capture_record") {
        CaptureRecordScreen()
    }

    composable("processing?imageUri={imageUri}") {
        ProcessingScreen()
    }

    composable("match_confirmation") {
        MatchConfirmationScreen()
    }

    composable("manual_search") {
        ManualSearchScreen()
    }

    composable("collection_manual_entry") {
        ManualSubmissionsScreen()
    }

    composable("collection_manual_form?draftId={draftId}") { backStackEntry ->
        val draftId =
            backStackEntry.arguments?.getString("draftId")

        ManualReleaseFormScreen(draftId = draftId)
    }

    composable(
        "session_logging/{releaseId}"
    ) { backStackEntry ->

        val releaseId =
            backStackEntry.arguments?.getString("releaseId")

        SessionLoggingScreen(releaseId)
    }

    composable(
        "record_detail/{releaseId}"
    ) { backStackEntry ->

        val releaseId =
            backStackEntry.arguments?.getString("releaseId")

        RecordDetailScreen(releaseId)
    }

    composable("analytics") {
        AnalyticsScreen()
    }

    composable("ai_insights") {
        AiInsightsScreen()
    }

    composable("top_records") {
        TopRecordsScreen()
    }

    composable("settings") {
        SettingsScreen()
    }   
}
```

---

# Navigation State Considerations

Important UI state that should be preserved:

```
identified release candidates
captured image URI
search results
```

Recommended approach:

```
ViewModel per screen
```

Example:

```
CaptureViewModel
SessionViewModel
RecordViewModel
AnalyticsViewModel
```

---

# Error Handling Navigation

Cases:

### Image Processing Failure

```
processing → manual_search
```

### API Failure

```
show retry option
```

### Invalid Release Selection

```
return to match_confirmation
```

---

# Navigation Principles for MVP

Keep navigation simple:

```
single activity
compose navigation
stateless screens
state handled in ViewModels
```

Avoid for MVP:

```
nested navigation graphs
deep linking
multi-activity architecture
```

---

# Future Navigation Extensions (Post-MVP)

Potential additional screens:

```
Price tracking
Sell recommendations
```

These should be added as **separate navigation routes** later.

---

# Summary

The MVP navigation architecture is:

```
Single Activity
Jetpack Compose Navigation
Route-based navigation
releaseId as primary entity reference
```

This structure keeps the app **simple, testable, and scalable for future features**.
