# Android Live Barcode Identify Plan

## Goal

Add an on-device barcode scanner entry point to the existing identify flow so a user can point the camera at a record sleeve barcode and jump straight to release candidates.

The scanner should use CameraX for preview/frame delivery and the bundled ML Kit barcode scanning model for local detection. The detected barcode should feed the existing Discogs release search path instead of adding a new backend endpoint.

## Non-Goals

- Do not replace photo-based identify.
- Do not redesign manual search, match confirmation, or session logging.
- Do not add server-side barcode scanning work in this pass.
- Do not support batch scanning or inventory workflows.

## Product Flow

1. `CaptureRecordScreen` has a secondary action: `Scan Barcode`.
2. Tapping it keeps the user on the existing CameraX preview and enables live barcode analysis.
3. The existing capture permission pattern is reused.
4. The preview shows a centered green rounded scan guide and `Hold still...`.
5. Frames are analyzed locally by ML Kit.
6. First stable UPC/EAN result inside the guide is accepted after a short debounce.
7. The app shows a short `Barcode captured` success state and navigates to `barcode_processing?barcode={barcode}`:
   - search by barcode through `VinylApiClient.searchReleases(...)`
   - show `MatchConfirmationScreen` if candidates are found
   - offer `Try Again`, `Manual Search` with the barcode prefilled, or `Cancel` if no result, search failure, or timeout

## Android Dependencies

CameraX is already present:

- `androidx.camera:camera-camera2`
- `androidx.camera:camera-core`
- `androidx.camera:camera-lifecycle`
- `androidx.camera:camera-view`

Add bundled ML Kit barcode scanning:

```kotlin
// android-app/gradle/libs.versions.toml
mlkitBarcodeScanning = "17.3.0"
mlkit-barcode-scanning = { group = "com.google.mlkit", name = "barcode-scanning", version.ref = "mlkitBarcodeScanning" }

// android-app/app/build.gradle.kts
implementation(libs.mlkit.barcode.scanning)
```

Use the bundled artifact rather than the Play Services artifact so first-run scanning works without a dynamic model download.

## Implemented Files

- `navigation/VinylRoutes.kt`
  - adds `BARCODE_PROCESSING_PATTERN = "barcode_processing?barcode={barcode}"`
  - adds `manualSearchBarcode(barcode: String)` for recovery handoff

- `navigation/VinylNavHost.kt`
  - routes successful capture to barcode processing
  - maps barcode search results into match confirmation candidates
  - routes recovery actions to scan retry, manual search, or cancel

- `ui/screens/CaptureRecordScreen.kt`
  - adds `Scan Barcode` mode on the existing preview
  - binds ImageAnalysis only while barcode mode is active
  - shows guide overlay, torch toggle, haptic success, and captured confirmation
  - keeps existing photo capture behavior unchanged

- `ui/screens/ProcessingScreen.kt`
  - adds barcode processing with the existing green spinner/success/recovery language
  - applies an 8-10s timeout before showing recovery actions

- `ui/screens/ManualSearchScreen.kt`
  - accepts `initialBarcode: String = ""`
  - keep current validation rules

## Scanner Behavior

Restrict ML Kit formats to vinyl-relevant retail barcodes:

```kotlin
BarcodeScannerOptions.Builder()
    .setBarcodeFormats(
        Barcode.FORMAT_UPC_A,
        Barcode.FORMAT_UPC_E,
        Barcode.FORMAT_EAN_13,
        Barcode.FORMAT_EAN_8,
    )
    .build()
```

Analyzer rules:

- Use `ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST`.
- Close every `ImageProxy` in success and failure paths.
- Ignore empty `rawValue`.
- Normalize to digits only.
- Accept only 8, 12, or 13 digits for the first pass.
- Require the same value twice within a short window, or freeze after first high-confidence result if repeated reads feel sluggish in testing.
- Stop analysis after acceptance to avoid duplicate navigation.

## Screen State

Keep state local and small for the first slice:

```kotlin
private sealed interface BarcodeScanUiState {
    data object RequestingPermission : BarcodeScanUiState
    data object Scanning : BarcodeScanUiState
    data class Found(val barcode: String) : BarcodeScanUiState
    data class Searching(val barcode: String) : BarcodeScanUiState
    data class Error(val message: String, val barcode: String? = null) : BarcodeScanUiState
}
```

If this grows, move search orchestration into a small ViewModel. Camera setup can remain Android UI code because it is platform/framework-specific.

## Candidate Search Handoff

Use the existing API client:

```kotlin
apiClient.searchReleases(
    artist = null,
    title = null,
    catalog = null,
    barcode = barcode,
    year = null,
)
```

Map each `ReleaseSearchResult` to the same candidate surface already used by match confirmation. Manual search remains the recovery path when barcode search returns no results, fails, or times out.

## UX Details

- `Scan Barcode` toggles barcode mode inside `CaptureRecordScreen`.
- `Cancel Barcode Scan` returns to normal capture mode.
- Center guide should be stable and not resize during scanning.
- Status copy should be terse:
  - `Hold still...`
  - `Barcode captured`
  - `Searching matches...`
  - `No match found`
- Do not show raw technical ML Kit errors unless needed for debugging.
- If camera permission is denied, show the same style of recovery copy as `CaptureRecordScreen`.

## Rollout Slices

### Slice 1: Manual Prefill

- Add ML Kit dependency.
- Detect barcode locally from the existing `CaptureRecordScreen` camera path.
- Navigate to `ManualSearchScreen(initialBarcode = barcode)`.
- User manually submits the search.

Status: completed as a test slice and then superseded by automatic barcode search.

This proved camera, ML Kit, permission, and barcode normalization with minimal product coupling. The separate `BarcodeScanScreen` experiment was removed after device testing showed a black preview surface; barcode analysis now lives on the known-good capture preview.

### Slice 2: Automatic Barcode Search

- After stable detection, call `searchReleases` automatically.
- Show a processing-style searching state after the captured confirmation.
- Route successful results into existing match confirmation flow.
- Fall back to manual search with barcode prefilled.

Status: completed.

### Slice 3: Polish

- Add auto-zoom support for distant barcode labels:
  - Move scanner option construction close enough to the bound CameraX `Camera` to access `camera.cameraInfo.zoomState`.
  - Configure ML Kit with `setZoomSuggestionOptions(...)`.
  - In the zoom callback, clamp against the current CameraX zoom state, call `camera.cameraControl.setZoomRatio(zoomRatio)`, and return whether the request was accepted.
  - Reset zoom to `1f` when barcode mode is canceled, succeeds, or the camera unbinds.
  - Gate zoom changes so the UI does not pulse: ignore tiny ratio changes and avoid repeated changes while one is in flight.
- Keep `enableAllPotentialBarcodes()` disabled for now. Revisit only after more device testing shows a clear need for undecoded barcode bounding boxes, because it can add noise and extra acceptance logic.
- Add a torch toggle in barcode mode for dim rooms and dark sleeves.
- Filter detection to the visible guide area before accepting a barcode, so edge/background barcodes do not trigger.
- Keep the stable-read requirement but make it tunable after device testing: start around `700-1000ms`.
- Reuse the existing identify processing flow after barcode capture:
  - After `Barcode captured`, navigate into a processing-style state/screen with the same green spinner language as `ProcessingScreen`.
  - Support a barcode-search mode that calls `searchReleases(barcode = ...)` instead of starting an image identify job.
  - Keep recovery actions consistent with image identify: `Retry`, `Manual Search`, and top-left cancel/close.
  - On retry, return to live barcode scan mode or rerun the barcode API search if the barcode is already known.
  - On manual search, open `ManualSearchScreen(initialBarcode = barcode)`.
  - On cancel, return to capture/home using the same route behavior as the identify flow.
  - Treat API failure, no results, and an `8-10s` timeout as recoverable processing errors instead of inline capture-screen errors.
  - Preserve the success beat: green check `Barcode captured`, then processing spinner `Searching matches...`, then candidates.
- Add haptic feedback on successful barcode capture if it feels good on device.
- Add instrumentation around scan success/failure if analytics exists later.

Status: implemented except analytics instrumentation, which remains a future follow-up.

## Test Checklist

- Device with camera scans UPC-A and EAN-13 sleeves.
- Permission allow, deny, and deny-then-allow paths work.
- No duplicate navigation after one barcode is detected.
- Manual search receives the detected barcode unchanged.
- Invalid or partial barcodes are ignored.
- App remains installable on devices without a camera because camera hardware stays optional.
