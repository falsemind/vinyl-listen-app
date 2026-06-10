---
name: navigation-graph
description: This document explains Android Navigation Graph Specificationn.
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
 │     └── Processing
 │           ├── MatchConfirmation
 │           │      └── SessionLogging
 │           │             └── RecordDetail
 │           │                    └── Home
 │           │
 │           └── ManualSearch
 │                   └── SessionLogging
 │                          └── RecordDetail
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
```

Home, Analytics, Insights, and Collection are active bottom-navigation routes. Settings is reachable from the Home header icon and currently shows lightweight app information. Analytics loads the implemented dashboard endpoints, Insights shows the single-thread AI chat shell, and Collection loads the Discogs-backed records collection.

---

# Navigation Routes

|Screen|Route|
|---|---|
|Home|`home`|
|Recent Sessions|`recent_sessions`|
|Capture Record|`capture_record`|
|Processing|`processing?imageUri={imageUri}`|
|Match Confirmation|`match_confirmation`|
|Manual Search|`manual_search`|
|Collection Manual Search|`collection_manual_search`|
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
|Import a Discogs release before logging|`POST /api/v1/releases/import`|
|Load record detail metadata|`GET /api/v1/releases/{release_id}`|
|Load record listening history|`GET /api/v1/releases/{release_id}/sessions`|
|Start Discogs collection sync|`POST /api/v1/collection/sync`|
|Resume active Discogs collection sync|`GET /api/v1/collection/sync/active`|
|Poll Discogs collection sync|`GET /api/v1/collection/sync/{job_id}`|
|Load Records Collection list|`GET /api/v1/collection/releases?limit=25&offset={offset}`|
|Manual collection search|`GET /api/v1/collection/search`|
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

If only `discogs_release_id` is available, the app must import the release first:

```
POST /api/v1/releases/import
then
release_id returned
then
session_logging/{releaseId}
```

Manual Search uses `GET /api/v1/releases/search` to list Discogs candidates. Search results do not have an internal `release_id`, so the app imports the selected `discogs_release_id` with `POST /api/v1/releases/import` before navigating to `session_logging/{releaseId}`.

Collection Manual Search uses the same screen shell but calls `GET /api/v1/collection/search`. Results include internal `release_id`, so selecting one navigates directly to `record_detail/{releaseId}` without importing from Discogs.

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
image_uri
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
|Back|`home`|

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

Discogs-backed browser for current collection membership.

### Displays

- Empty state with centered `Load Discogs Collection` action
- Import/sync progress with centered status feedback
- Error state with orange error text and centered `Retry Load`
- Latest 25 active collection records by Discogs added date
- `Show More` pagination in 25-record pages
- `Sync Items` action after collection records are loaded

### Navigation

|Action|Destination|
|---|---|
|Tap record|`record_detail/{releaseId}`|
|Tap search CTA|`collection_manual_search`|
|Tap Home tab|`home`|
|Tap Stats tab|`analytics`|
|Tap Insights tab|`ai_insights`|

---

# 12. Settings Screen

### Route

```
settings
```

### Purpose

Screen for app configuration and basic application information.

### Displays

- App version  
- Build number  
- Basic application information

### Notes

No functional settings are included in the MVP yet.

This screen exists to support future configuration features such as:

- preferences  
- account management  
- integrations  

### Navigation

|Action|Destination|
|---|---|
|Back|`home`|

---

# 13. AI Insights Screen

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
|image_uri|String|Local URI of captured photo|

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
