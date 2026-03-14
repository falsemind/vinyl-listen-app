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
 │
 └── Settings
```

---

# Navigation Routes

|Screen|Route|
|---|---|
|Home|`home`|
|Capture Record|`capture_record`|
|Processing|`processing`|
|Match Confirmation|`match_confirmation`|
|Manual Search|`manual_search`|
|Session Logging|`session_logging/{releaseId}`|
|Record Detail|`record_detail/{releaseId}`|
|Analytics|`analytics`|
|Settings|`settings`|
---

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
|Tap record|`record_detail/{releaseId}`|
|Open analytics|`analytics`|
|Open settings|`settings`|
---

# 2. Capture Record Screen

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

# 3. Processing Screen

### Route

```
processing
```

### Purpose

Displays processing progress while the backend identifies the record.

### Possible Results

|Result|Destination|
|---|---|
|Matches found|`match_confirmation`|
|No matches|`manual_search`|

---

# 4. Match Confirmation Screen

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

# 5. Manual Search Screen

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
```

### Actions

|Action|Destination|
|---|---|
|Select release|`session_logging/{releaseId}`|

---

# 6. Session Logging Screen

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

### Actions

|Action|Destination|
|---|---|
|Save session|`record_detail/{releaseId}`|
|Cancel|`home`|

---

# 7. Record Detail Screen

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

---

# 8. Analytics Screen

### Route

```
analytics
```

### Purpose

Display listening statistics and charts.

### Navigation

|Action|Destination|
|---|---|
|Tap record in chart|`record_detail/{releaseId}`|
|Back|`home`|

---

# 9. Settings Screen

### Route

```
settings
```

### Purpose

Placeholder screen included in MVP for basic application information.

### Displays

- App version  
- Build number  
- Basic application information

### Notes

No functional settings are included in the MVP.

This screen exists to support future configuration features such as:

- preferences  
- account management  
- integrations  
- collection sync settings

### Navigation

Action | Destination
------ | ------
Back | home

# Navigation Argument Definitions

|Argument|Type|Description|
|---|---|---|
|releaseId|String|Discogs release identifier|
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

    composable("capture_record") {
        CaptureRecordScreen()
    }

    composable("processing") {
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
AI assistant
Collection browser
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