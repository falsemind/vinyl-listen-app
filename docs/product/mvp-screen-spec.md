---
name: mvp-screen-spec
description: This document explains UI client's MVP Screen Specification.
---

# Vinyl Listening App — MVP Screen Specification

## Purpose

This document defines the core screens and user flow for the MVP of the Vinyl Listening App. It is intended to support **Figma wireframing and UX exploration**.

Scope includes:

- record identification
    
- listening session logging
    
- basic analytics
    

Selling recommendations are **not included in MVP**. AI Insights and collection management now exist as app features beyond the original MVP baseline.

---

# Screen 1 — Home

## Purpose

Provide a quick overview of listening activity and allow the user to quickly log a new session.

## Main Sections

### Header

App title or logo.

### Quick Action

Button:

```
Log Listening Session
```

### Bottom Navigation

Primary tabs:

```
Home
Stats
Insights
Settings
```

Each item uses an icon above the label.

### Recent Sessions

List showing up to 3 listening sessions.

Each item shows:

```
Artist
Title
Side played
Rating
Timestamp
```

`View All` opens the Recent Sessions screen with up to 25 sessions.

When a timed session is active, a green timer chip appears below the Home header. The chip shows elapsed time, an auto-add toggle, and a stop action. The chip also appears below headers on other app screens, except the identify camera, processing, and candidate confirmation flow.

### Stats Snapshot

Small overview metrics:

```
Total sessions
Records played this month
```

### Top Records

Compact highlight list:

```
Most played record
Least played record
```

## Actions

```
Tap Log Listening Session → Capture Record Screen
Tap Session → Record Detail Screen
Tap Record → Record Detail Screen
Tap Recent Sessions View All → Recent Sessions Screen
Tap Stats tab → Analytics Screen
Tap Insights tab → AI Insights Screen
Tap Settings tab → Settings Screen
```

---

# Screen 2 — Capture Record

## Purpose

Capture a photo or scan a sleeve barcode to identify the record.

## Main Components

### Camera View

Camera preview using device camera.

### Capture Button

```
Take Photo
```

### Barcode Scan Mode

```
Scan Barcode
```

When barcode mode is active, the camera preview stays on the Capture Record screen and shows a green rounded guide with `Hold still...` below it. The app accepts a stable UPC/EAN read automatically, shows a short green check state with `Barcode captured`, then opens the processing flow.

### Alternative Actions

```
Upload Photo
Scan Barcode
Manual Search
```

### Help Hint

Small hint text:

```
Capture the record label, runout etching, or barcode.
```

## Actions

```
Take Photo → Processing Screen
Upload Photo → Processing Screen
Scan Barcode → Barcode Processing Screen
Manual Search → Manual Search Screen
```

---

# Screen 3 — Processing

## Purpose

Show system progress while identifying the record or searching barcode matches.

## UI Elements

### Loading Indicator

### Status Messages

Example messages:

```
Uploading image
Extracting text
Searching candidates
```

Status rows are lightweight text rows with a status marker:

```
Grey circle → pending
Green checkmark → complete
Orange ! → issue
```

Photo identify statuses are backed by the server identify job flow. The client starts `POST /api/v1/identify/jobs` and polls `GET /api/v1/identify/jobs/{job_id}` until the backend returns a terminal state.

Visible phases map to backend statuses:

| UI phase | Backend statuses |
| --- | --- |
| Uploading image | `queued`, `upload_received` |
| Extracting text | `preprocessing_image`, `extracting_text`, `parsing_identifiers` |
| Searching candidates | `searching_local`, `searching_discogs`, `ranking_candidates` |
| Identify canceled | `canceled` |

If the job fails, the backend returns `failed_step` so the client can mark upload, extraction, or search as the failed phase.

Barcode processing reuses the same green spinner/success language but calls `GET /api/v1/releases/search?barcode={barcode}` directly. If no barcode candidates are found within roughly 8-10 seconds, the recovery state offers `Try Again`, `Manual Search`, and `Cancel`.

### Cancel Behavior

Processing has a top-left cancel button while the identify job is active. This is the only intentional exit path during active processing.

The screen blocks normal phone back navigation, including the system back button and back gesture, until the user taps cancel or the job reaches a terminal state. On cancel, Android sends a best-effort `POST /api/v1/identify/jobs/{job_id}/cancel`, stops local polling pressure, and leaves Processing once cancellation has started locally or a terminal backend status is returned.

## Navigation

```
If matches found → Match Confirmation Screen
If no results → Manual Search Screen
Cancel active identify → Home
```

For barcode processing, `Manual Search` opens with the detected barcode prefilled.

---

# Screen 4 — Match Confirmation

## Purpose

Allow the user to confirm the correct Discogs release.

## Layout

Scrollable list of candidate releases.

Each candidate shows:

```
Artist
Title
Year
Label
Catalog number
Thumbnail image
```

## Actions per Candidate

```
Confirm Release
View Details (optional)
```

## Bottom Actions

```
Show More Matches
Manual Search
```

## Navigation

```
MatchConfirmation
     ↓
User selects candidate
     ↓
Session mode: import selected Discogs candidate if needed, then Session Logging
Collection-add mode: import selected Discogs candidate if needed, activate collection membership
     ↓
backend returns internal release_id
     ↓
session_logging/{releaseId} or record_detail/{releaseId}
```

---

# Screen 5 — Manual Search

## Purpose

Allow the user to find a record manually if identification fails.

## Search Fields

Search input:

```
Artist
Title
Catalog number
Barcode
Year
```

## Results List

Each result shows:

```
Artist
Title
Format
Year
Label
Thumbnail
```

The first page shows up to 10 results. If more results are likely available, a `Show more` action loads the next page.

## Actions

```
Select Release → Import Release → Session Logging Screen
```

---

# Screen 6 — Session Logging

## Purpose

Record a listening session for the selected release.

If a timed session is active and auto-add is enabled, saving attaches the logged side-level session to the active timed session. Track selection remains optional.

## Record Info (Top Section)

Display:

```
Artist
Title
Year
Label
Thumbnail
```

## Input Fields

### Side Played

Dropdown or selector:

```
Disc 1 - Side A
Disc 1 - Side B
Disc 2 - Side A
Disc 2 - Side B
```

Values are based on release data. Multi-disc releases can repeat the same side names, so the selector stores a unique option value and displays a user-facing label.

### Rating

Scale:

```
1 — 5
```

Example UI:  
Star or slider input.

### Mood

Predefined moods:

```
Energetic
Calm
Melancholic
Nostalgic
Focused
Background
```

Additional option:

```
Add Custom Mood
```

Custom mood behavior:

- Tap **+ Custom** to open a full-width input popup.
- Input accepts only letters, numbers, and spaces.
- Custom mood names must be 3-20 characters.
- Custom mood names cannot duplicate predefined or saved custom moods.
- Valid input changes dismiss **X** to a green save checkmark.
- Saved custom moods are persisted through the backend and appear in future sessions.
- Long-press a saved custom mood to confirm deletion from saved mood options.
- Logged sessions keep their selected mood for analytics history even if the custom option is deleted later.
- Re-created moods reuse historical casing, so analytics does not split the same mood by case.

### Optional Track Selection

If cached Discogs tracklist data exists, the screen shows a track selector below side selection. Track selection is optional. The user can log only the side, selected tracks, or all tracks on the side.

### Notes

Optional text field.

Purpose:  
Personal listening notes for future analysis.

## Actions

```
Save Session
Cancel
```

## Navigation

```
Save Session → Record Detail Screen
Cancel → Home
```

---

# Screen 7 — Record Detail

## Purpose

Show detailed information and listening history for a record.

## Sections

### Record Info

```
Artist
Title
Year
Label
Catalog number
Discogs link
```

### Listening Stats

```
Total plays
Average rating
Last played
```

### Mood Summary

Small visualization:

```
Mood frequency
```

### Listening History

List of sessions:

```
Date
Side played
Rating
Mood
Notes indicator
```

## Actions

```
Add Session
View Notes
```

Navigation:

```
Add Session → Session Logging Screen
```

---

# Screen 8 — Analytics

## Purpose

Provide visual insights into listening habits.

Charts use Compose-compatible components backed by the analytics API. The Android screen keeps local prototype data as a fallback when the backend is unavailable.

## Charts

### Plays Over Time

Bar chart showing:

```
Sessions per month
```

The screen shows a rolling 12-month series, including empty months. The latest 6 months are visible by default, and the previous 6 months are reachable by horizontal scrolling.

Backend source:

```
GET /analytics/plays/monthly
GET /analytics/sessions?month=YYYY-MM
```

### Top Records

List:

```
Most played records
```

The Analytics screen shows up to 5 records inline. `View All` opens the Top Records screen with 10 records by default and a `Show More` action for additional pages.

Backend source:

```
GET /analytics/top-records
```

### Rating Distribution

Histogram or bar chart:

```
Rating frequency
```

Rating counts remain visible against the orange bar. Counts use orange when the bar does not cover the digits and dark text only when the orange bar is wide enough behind the count.

Backend source:

```
GET /analytics/rating-distribution
GET /analytics/records/by-rating?rating=5
```

### Mood Distribution

Pie or bar chart:

```
Mood counts
```

Backend source:

```
GET /analytics/mood-distribution
GET /analytics/records/by-mood?mood=Focused
```

### Style Distribution

Progress rows:

```
Specific Discogs style counts
```

Style analytics shows specific styles such as `Dub Techno`, `House`, and `Deep House`, not broad genres. Tapping a style opens a View All-style drilldown with record cards and 10-item pagination.

Backend source:

```
GET /analytics/style-distribution
GET /analytics/records/by-style?style=Dub%20Techno
```

## Actions

```
Tap month with sessions → Month Sessions Screen
Tap rating row → Rating Records Screen
Tap mood row → Mood Records Screen
Tap style row → Style Records Screen
Tap record in chart or drilldown → Record Detail Screen
Tap Top Records View All → Top Records Screen
```

---

# Screen 8A — Records Collection

## Purpose

Show the active local collection and provide collection-specific actions.

## Content

The screen header shows `Records Collection` and the action-menu toggle even
when the collection is empty. Records are loaded from:

```http
GET /collection/releases
```

Collection filters use green chips with a result counter. Supported filters:

```text
Artist
Label
Personal favorites
Discogs collection folder
```

Discogs folder filters are available only after the backend has imported folder
metadata and `GET /collection/folders` returns `discogs_configured=true` and
`has_extra_folders=true`. Selecting a folder filters the app collection only; it
does not change source of truth or sync scope.

## Actions

```text
Collection settings → Settings
Load Discogs collection / Sync Items → manual collection sync
Collection folders → expand folder rows; tap row to filter Collection
View all folders → open full Discogs folder list when more than 10 folders exist
Personal favorites → filter Collection to favorite records
+ floating CTA → identify flow or manual entry placeholder
Search floating CTA → Collection manual search
Tap record → Record Detail Screen
```

Action-menu rows use green icons: settings gear for `Collection settings`,
sync arrows for `Load Discogs collection` / `Sync Items`, and folder icons for
folder rows. The `View all folders` row uses a three-dot icon.

The add camera option starts the existing identify camera flow in collection-add
mode. Confirming a candidate saves the full release metadata into the backend,
activates collection membership, opens Record Detail, and refreshes Collection
when the user returns. This path works without a saved backend Discogs token by
fetching the selected full Discogs release from the device before import.

---

# Screen 9 — Recent Sessions

## Purpose

Show the expanded recent listening history from Home.

## Content

List up to 25 recent sessions.

Timed sessions render as a green bordered group when multiple logged records share a `session_group_id`.

The group shows metadata chips:

```
Session Time
Total Records
Avg Rating
Top Mood
```

Records inside the group keep the regular recent-session card content with a green border. Standalone sessions still render as normal cards.

Each item shows:

```
Title
Artist
Relative timestamp
```

## Actions

```
Tap Session → Record Detail Screen
Back → Home
```

---

# Screen 10 — Top Records

## Purpose

Show the expanded top records list from Analytics.

## Content

List up to 25 top records.

Each item shows:

```
Title
Artist
Play count
```

## Actions

```
Tap Record → Record Detail Screen
Back → Analytics
```

---

# Screen 11 — Settings

## Purpose

Show app information and collection configuration.

The Discogs integration card is collapsed by default. When expanded, it supports:

- Uploading a Discogs personal access token.
- Briefly revealing the newest typed token character before masking it.
- Clearing token input with an inline `X`.
- Canceling token entry, which clears input and dismisses keyboard focus.
- Showing saved-token state as grey copy plus the Discogs username in a green chip.
- Managing a saved token with a pencil icon that changes to `X` while actions are open.
- Updating or deleting a saved token. Delete requires confirmation.

Current content includes collection source-of-truth selection:

- `Collection source of truth: App` when local app membership is authoritative.
- `Collection source of truth: Discogs` when the user selects Discogs as the future mirror source.
- Toggle ON means App; toggle OFF means Discogs.
- Deleting the Discogs token disables token-backed Discogs features and resets source of truth to App.

---

# Screen 12 — AI Insights

## Purpose

Provide the initial single-thread chat shell for future AI-assisted listening insights.

## Content

- Suggested prompts
- Chat message list
- Text input
- Send action

## Constraints

- Use app design-system styling rather than mockup-specific visual details.
- Use `style` wording for collection categories.
- Keep the first implementation to one chat thread.

---

# MVP Navigation Flow

```
Home
 ↓
Capture Record
 ↓
Processing
 ↓
Match Confirmation
 ↓
Session Logging
 ↓
Record Detail
 ↓
Home
```

Alternative paths:

```
Capture Record → Manual Search → Session Logging
Record Detail → Add Session
Home → Session → Record Detail
Home → Recent Sessions → Record Detail
Home → Analytics → Top Records → Record Detail
Home → Insights
Home → Settings
```

---

# Notes for Figma Exploration

Design considerations to explore:

- quick logging with minimal taps
    
- large camera capture interaction
    
- clean session logging interface
    
- lightweight analytics visuals
    
- clear record identification confirmation

# High Level Color Design Considerations

## Quick Reference: iOS vs Android Standard Colors

| Color Type | iOS (HIG) | Android (Material 3) |
| :--- | :--- | :--- |
| **System Blue**| `#007AFF`| `#2196F3` |
| **System Green**| `#34C759` | `#4CAF50` |
| **System Red** | `#FF3B30` | `#F44336` |
| **Dark Mode BG**| `#000000` | `#121212` |

## Dark Mode 2.0: Optimization for AMOLED Screens

### True Black vs. Rich Gray

Pure black (#000000) behaves differently on AMOLED displays.

| Pure Black | Rich Charcoal |
| :--- | :--- |
| Black pixels consume no power on OLED screens| Reduces eye strain while maintaining efficiency |

Modern apps prefer charcoal tones like `#1E1E1E` or `#333333` to balance comfort and battery savings.

### Avoiding Visual Smearing
High-contrast transitions on pure black backgrounds can cause motion blur during scrolling.

Using controlled grays and softened highlights maintains smooth visual performance.

### Functional & Semantic Color Mapping

#### Success — Confirmation

Why Mint Green `#98FF98` over pure green color:
- Feels modern and lightweight
- Reduces neon glare in dark mode
- Communicates without aggression

#### Error — Intervention

Compared to pure red, Coral Red(orange undertone):

- Still captures attention immediately
- Feels more constructive, less punitive
- Reduces emotional friction

#### Warning — Attention

High-luminance Amber color:

- Pair with black text on light backgrounds
- Ensure WCAG contrast compliance
- Alert without inducing panic

#### Interactive — Action

Consistent brand color builds muscle memory:

- Users learn "this color = clickable"
- Reduces cognitive load
- Increases interaction speed

### The 60-30-10 Rule for Mobile Palettes

A professional mobile palette follows a proven structure that maintains clarity while allowing emphasis.

| 60% | 30% | 10% |
| :--- | :--- | :--- |
| **Primary Neutrals (60%)** Backgrounds, surfaces, structure | **Secondary Color (30%)** Supporting UI, headers, cards | **Accent Color (10%)** CTAs, highlights, focal points |

The MVP prioritizes **speed of logging a listening session** over deep record management features.
