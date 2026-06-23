# Android ML Kit Text Identify Experiment Plan

## Goal

Define a later Android-first experiment that uses on-device ML Kit text recognition to extract cheap, high-signal release identifiers before falling back to the backend OCR identify pipeline.

The experiment should stay narrow: catalog numbers first, then selected text snippets such as artist, title, barcode, and label text. Full album-cover understanding remains a backend-oriented problem.

## Product Hypothesis

On-device OCR can reduce backend processing cost and make simple identify flows feel faster when the user can point the camera at a catalog number, barcode-adjacent text, spine, label, or back-cover identifier.

The backend pipeline remains the advanced path for difficult images, noisy covers, ranking, junk filtering, and evidence-heavy Discogs matching.

## Non-Goals

- Do not replace the backend PaddleOCR/VLM identify pipeline.
- Do not build a full on-device release matcher.
- Do not attempt broad junk filtering for credits, contacts, copyright blocks, tracklists, or label copy.
- Do not add offline Discogs matching.
- Do not change multi-user, collection, or token ownership rules.

## Current App Fit

- Android already has CameraX capture surfaces and ML Kit barcode precedent.
- Manual and barcode flows can already hand off into search/import behavior.
- Backend identify code already owns OCR evidence, identifier parsing, search planning, and candidate ranking.
- This experiment should reuse those boundaries instead of duplicating the backend pipeline on device.

## Candidate Approaches

### Approach A: Android Extracts Text And Prefills Manual Search

Android runs ML Kit text recognition, extracts likely catalog numbers or barcodes, and routes the best candidate into the existing manual search flow.

This is the smallest useful slice. It avoids backend changes and gives quick feedback on whether ML Kit text is useful for vinyl-specific identifiers.

Tradeoff: it does not reuse backend parser/ranking logic except through the existing search endpoint.

### Approach B: Android Extracts Text, Backend Parses And Searches

Android sends OCR text lines and optional metadata to a new text-only identify endpoint. Backend treats the input as OCR evidence without receiving an image.

This reuses existing parser, search planning, and ranking work while avoiding backend image/OCR cost.

Tradeoff: it needs a new API contract and backend tests, but keeps intelligence centralized.

### Approach C: Android Adds A Lightweight Local Parser Layer

Android extracts text and builds local candidates for catalog number, barcode, and possibly simple artist/title line pairs.

This can make the UI faster and useful before backend round trips.

Tradeoff: parsing rules can grow quickly. Keep this layer intentionally shallow and transparent.

## Recommended Path

Start with Approach A, then evolve into Approach B if the extracted text is good enough.

The first prototype should live inside the existing capture screen. For now, add one more action in the same row as the barcode scanner instead of redesigning the whole capture UI.

Later, the capture screen can move toward a more regular camera UX:

- one primary button to take a photo
- secondary mode buttons for barcode, catalog number, ML Kit text, and advanced backend identify
- advanced backend identify remains the full image/OCR pipeline path

Approach C should be limited to simple candidate extraction only:

- barcode-shaped digits
- catalog-number-shaped tokens
- short line pairs that may be artist/title hints

Anything that requires confidence scoring, junk filtering, release matching, or Discogs ranking should stay backend-owned.

## Experiment Slices

### Slice 1: Text Recognition Spike

Add ML Kit text recognition to the existing capture screen as an additional prototype action near the barcode scanner.

The first prototype should process a still frame/photo instead of scanning continuously. This keeps the behavior predictable, avoids candidate flicker, and better matches the user's mental model: aim, capture, inspect extracted text.

Output:

- raw recognized lines
- bounding boxes if easily available
- candidate catalog-number tokens
- candidate barcode tokens

No search or import behavior is required in this slice.

### Slice 2: Catalog Number Prototype

Show catalog-number candidates in the capture/manual flow and allow the user to pick one.

Route the selected value into a single manual-search field.

Acceptance criteria:

- user can scan a clear label/spine/back-cover catalog number
- candidate list is visible and editable
- no backend OCR job is created
- fallback to normal manual search remains obvious

### Slice 3: Text-Only Backend Identify Contract

Add a separate backend endpoint that accepts OCR text lines without an image upload.

Do not add this as a mode on the existing identify job API. Keeping it separate makes the feature boundary clearer and avoids mixing image upload jobs with text-only parsing/search.

Android sends:

- recognized lines
- selected/highlighted candidate if the user chose one
- optional barcode/catalog-number hints
- source type such as `ANDROID_MLKIT_TEXT`

Backend returns normal identify candidates.

Use a job-like progress model for consistency with the current identify pipeline, but only expose states that make sense for text-only input. For example, skip image-processing states and keep states around receiving text, parsing identifiers, searching candidates, ranking, completed, failed, and canceled.

### Slice 4: UX Polish And Measurement

Compare:

- ML Kit catalog candidate success rate
- manual correction rate
- backend OCR avoided
- time to first candidate
- cases where backend OCR still wins

## Implementation Phases

### Android Phase 1: Prototype Entry Point And ML Kit Wiring

Goal: add a narrow text-recognition prototype inside the existing capture screen.

Tasks:

| Task | Effort | Depends On | Done Criteria |
|------|--------|------------|---------------|
| Add ML Kit text recognition dependency | 1-2h | Existing Android build | App builds with text recognition dependency and no barcode regression |
| Add prototype capture action near barcode scanner | 2-4h | Existing capture screen | User can trigger catalog/text OCR from the existing capture screen |
| Process a still frame/photo through ML Kit | 4-8h | Dependency wiring | Captured image produces recognized text lines on device |
| Add local debug logging/result surface | 2-4h | Text recognition output | Raw lines, image size, processing time, and candidate count are visible for testing |

Android verification:

- `:app:compileDebugKotlin`
- `:app:ktlintCheck`
- Manual device test with clear label, spine, barcode-adjacent text, and noisy back cover

### Android Phase 2: Catalog Candidate Extraction

Goal: turn recognized text into editable catalog-number suggestions without backend OCR.

Tasks:

| Task | Effort | Depends On | Done Criteria |
|------|--------|------------|---------------|
| Add catalog token extraction heuristics | 4-8h | Phase 1 output | Tokens are ranked by accepted first-pass quality signals |
| Show editable catalog-number suggestion | 4-8h | Candidate extraction | User can inspect, edit, clear, or accept the suggested catalog number |
| Route accepted catalog number to manual search | 2-4h | Editable suggestion | Existing manual search opens with the catalog field populated |
| Add unit tests for candidate extraction | 4-8h | Heuristic implementation | Tests cover catalog-like, barcode-like, year-only, duplicate, and noisy tokens |

Android verification:

- Candidate extraction unit tests
- `:app:compileDebugKotlin`
- `:app:ktlintCheck`
- Manual fallback test when no useful catalog number is found

### Android Phase 3: OCR Quality Mode

Goal: make the high-res versus low-res tradeoff measurable first, then user-visible later.

Tasks:

| Task | Effort | Depends On | Done Criteria |
|------|--------|------------|---------------|
| Implement internal quality modes | 4-8h | Phase 1 still-frame path | Balanced, high-accuracy, and fast input sizing can be selected internally |
| Record timing and extraction metrics per mode | 2-4h | Quality modes | Logs show mode, source size, processing time, line count, and candidate count |
| Add settings toggle when modes are proven useful | 4-8h | Metric comparison | User can choose balanced, high-accuracy, or fast mode from pipeline/settings |

Android verification:

- Compare the same test photos across modes
- Confirm high-accuracy improves small text when available
- Confirm fast mode reduces latency on weaker devices

### Backend Phase 1: Text-Only Identify Contract

Goal: introduce a separate text-only endpoint without changing the image identify API.

Tasks:

| Task | Effort | Depends On | Done Criteria |
|------|--------|------------|---------------|
| Define request and response schema | 2-4h | Android Phase 1 output shape | Contract accepts OCR lines, optional selected hints, and source metadata |
| Add separate text-only identify route | 4-8h | Schema | Endpoint accepts text payloads without image upload |
| Add text-only progress states | 4-8h | Route | Job states cover text received, parsing, searching, ranking, completed, failed, and canceled |
| Document endpoint in API docs | 2-4h | Route behavior | API docs explain request fields, response shape, and omitted image states |

Backend verification:

- Focused API tests for valid, empty, noisy, and malformed text payloads
- Existing image identify tests still pass

### Backend Phase 2: Parser And Search Reuse

Goal: reuse backend identifier parsing, search planning, and ranking for Android ML Kit text.

Tasks:

| Task | Effort | Depends On | Done Criteria |
|------|--------|------------|---------------|
| Map Android OCR lines into identify evidence | 4-8h | Text-only route | Backend can parse catalog, barcode, artist, and title signals from submitted lines |
| Reuse existing search planning | 4-8h | Evidence mapping | Text-only requests produce Discogs search candidates through existing planning logic |
| Reuse existing ranking output | 4-8h | Search planning | Response shape matches normal candidate expectations where applicable |
| Add backend tests for text-only cases | 4-8h | Parser/search integration | Tests cover catalog number, barcode, artist/title hints, and junk-heavy text |

Backend verification:

- Focused text-only identify service tests
- Route tests for progress and response shape
- Regression test that image OCR still owns full-image pipeline behavior

### Backend Phase 3: Android Integration And Rollout

Goal: connect Android text-only identify to backend search once local catalog-number value is proven.

Tasks:

| Task | Effort | Depends On | Done Criteria |
|------|--------|------------|---------------|
| Add Android client method for text-only identify | 2-4h | Backend Phase 1 | Android can submit raw OCR lines to the separate endpoint |
| Add text identify progress UI | 4-8h | Text-only progress states | UI shows only text-relevant progress states |
| Add candidate handoff to match confirmation/import | 4-8h | Backend candidates | User can review backend candidates from ML Kit text input |
| Add observability counters | 2-4h | End-to-end flow | Logs/metrics separate ML Kit text identify from image identify |

Rollout criteria:

- Catalog-number local prototype shows enough value to justify backend integration
- Text-only endpoint avoids backend image processing cost
- Users can always fall back to manual search or advanced backend image identify

## Android Requirements

- ML Kit text recognition dependency.
- CameraX analyzer path that does not conflict with barcode mode.
- State for OCR mode, candidate list, selected candidate, and fallback actions.
- Clear cancellation/route behavior so scanning does not race with photo upload or barcode processing.
- Tests around route handoff and candidate selection.

## Backend Requirements

Only needed for Approach B.

- Text-only identify request model.
- Source marker for Android ML Kit OCR evidence.
- Reuse existing identifier parsing, search planning, and candidate ranking.
- Avoid treating Android OCR as more authoritative than backend OCR.
- Tests for catalog number, barcode, artist/title, and noisy text payloads.

## Resolved Decisions

- Text fragments that go through the backend parser/search path should be sent as-is, similar to the current OCR pipeline approach.
- Text-only identify should use a separate endpoint.
- Text-only identify should return a job-like progress model, but with only text-relevant states.
- Catalog-number prototype output should remain editable and should not hide fallback/manual correction.
- Still-frame/photo input is the preferred prototype interaction.
- OCR quality can later become a user-visible setting with balanced, high-accuracy, and fast modes.
- Catalog-number suggestion quality should start with simple local heuristics rather than a raw percentage or backend ranking score.

## Still-Frame Input Tradeoff

Using the normal captured image is simpler and can preserve more detail, which may help with small catalog numbers, spine text, thin fonts, and worn labels. The downside is that full-resolution photos cost more CPU, memory, and latency, especially on cheaper devices.

Using a lower-resolution analyzer frame is faster and cheaper. It can be good enough for large label text or clear catalog numbers, but it may lose the small typography that matters most for vinyl identifiers.

Recommended prototype tradeoff:

- Use the still-frame/photo interaction.
- Downscale before ML Kit rather than feeding the largest captured image directly.
- Keep enough resolution for small text, then measure on real devices/photos.
- Store/log the source image size, OCR processing time, extracted line count, and whether a catalog-number candidate was found.

If accuracy drops on catalog numbers, prefer a higher-resolution still frame for catalog mode. If latency is poor on cheaper devices, add a bounded downscale target instead of switching to continuous scanning.

Later, expose this as an OCR quality mode in pipeline/settings:

- `Balanced`: default mode; bounded downscale for reasonable speed and accuracy.
- `High accuracy`: use a higher-resolution still frame for difficult small text, slower on cheaper devices.
- `Fast`: use a lower-resolution frame for quicker extraction when the user prefers responsiveness.

This should be a user-visible tradeoff, not an invisible optimization. The UI copy should make the behavior clear: higher accuracy may be slower, fast mode may miss small catalog numbers.

## Catalog Candidate Quality Threshold

The confidence question is mainly about Slice 2, not Slice 3. It asks when Android should present a detected catalog number as a suggested candidate.

This should not be a raw percentage at first. ML Kit text recognition confidence may not map cleanly to release-identification quality, and backend ranking scores answer a different question: how good a matched release candidate is, not whether one OCR token is a good catalog-number candidate.

Start with a transparent local quality score made from the accepted first-pass signals:

- token matches known catalog-number shapes
- token length is plausible
- token has a useful mix of letters and numbers
- token avoids obvious barcode-only or year-only patterns
- token appears more than once, or appears near label/catalog keywords
- OCR confidence is high if ML Kit exposes it for the recognized text

Use the score only to order suggestions. Do not auto-submit in the first prototype. Always show the editable candidate and fallback manual correction.

## Risks

- ML Kit text may be good on clean labels but weak on stylized covers.
- Catalog-number patterns vary by label and region.
- A local parser can become a second backend pipeline if scope is not controlled.
- Continuous scanning can create UI noise if candidates flicker.

## Recommended First Step

Build Slice 1 as a hidden/debug text-recognition mode on the existing capture path, then test it against a small set of real release photos:

- clear catalog number on label
- catalog number on spine
- barcode plus nearby text
- front cover with artist/title
- difficult noisy back cover

Use the results to decide whether Slice 2 is worth implementing before adding any backend contract.
