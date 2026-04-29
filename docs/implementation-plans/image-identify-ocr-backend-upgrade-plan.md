# Code Implementation Plan: Image Identify OCR Pipeline Upgrade

## Goal

Improve vinyl image identification across varied labels, sleeves, colors, fonts, lighting, and photo angles.

The upgraded pipeline should keep Tesseract as the fast baseline, use EasyOCR only when it adds useful evidence, and improve the existing parser/search/ranking flow with better preprocessing, structured OCR evidence, and domain-specific error correction.

## Current Problem

The current pipeline already does more than plain OCR:

- Pillow-based normalization, resizing, denoising, contrast, sharpening, threshold, adaptive threshold, upscaled, crop, and color-channel variants.
- Barcode detection through `pyzbar`.
- Tesseract OCR with fast and escalated configs.
- Optional EasyOCR fallback with confidence-bearing text lines.
- OCR layout role extraction, identifier parsing, Discogs search planning, and candidate ranking.

The remaining accuracy issues are most likely caused by:

- crooked, rotated, tightly cropped, reflective, or perspective-distorted photos
- OCR confusion in catalog numbers and barcodes
- weak propagation of OCR confidence/source/box evidence into ranking
- false positives from generic artist/title or noisy raw text
- missing candidate validation against Discogs metadata

## Target Architecture

```text
Upload
  -> ImageProcessor
       - current Pillow variants
       - optional geometry/quality variants
  -> BarcodeDetector
  -> OcrCascade
       1. Tesseract baseline
       2. EasyOcrBackend fallback when evidence is weak
  -> IdentifierExtractor
       - parser output
       - structured OCR evidence
       - layout role evidence
  -> SearchPlanBuilder
  -> Discogs/local candidate search
  -> CandidateRanker
       - positive evidence
       - negative evidence
       - OCR confidence/source agreement
       - Discogs-aware corrections
  -> optional visual verification for top candidates
  -> IdentifyResponse
```

## Backend Interface

Keep the existing backend shape:

```python
class OcrBackend(Protocol):
    def extract(self, prepared_image: PreparedImage) -> OcrResult: ...
```

`OcrResult` should continue to carry:

- `source`
- `raw_text`
- `lines: tuple[OcrTextLine, ...]`

The parser can keep accepting plain raw text, but downstream ranking should prefer structured evidence when available.

## Phase 1: EasyOCR Fallback

*(Goal: keep neural OCR as a bounded fallback, not the default path.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **1.1** | `OcrBackend` Interface | Keep Tesseract and EasyOCR behind the same typed backend contract. | Existing OCR pipeline | Shared OCR backend contract. |
| **1.2** | `EasyOcrBackend` | Keep EasyOCR optional, lazy-loaded, and reusable. Default to CPU unless explicitly configured. | EasyOCR optional extra | Backend returning text, boxes, and confidence. |
| **1.3** | Feature Flags | Keep `IDENTIFY_EASYOCR_ENABLED`, GPU, confidence, and max-dimension settings. | Settings config | Safe opt-in rollout. |
| **1.4** | Cascade Trigger | Run EasyOCR only when Tesseract output is weak, noisy, suspicious, or lacks catalog/barcode evidence. | Existing `OcrCascade` | Bounded fallback path. |
| **1.5** | Evidence Merge | Deduplicate merged OCR lines by normalized text while preserving source/confidence/box. | 1.1, 1.2 | Richer downstream OCR evidence. |
| **1.6** | Benchmark Harness | Keep and extend the local OCR benchmark script for bad-label samples. | Test images | Repeatable quality/latency report. |

### Phase 1 Acceptance Criteria

- EasyOCR is optional and disabled by default.
- Tesseract remains the fast default path.
- Fallback behavior is covered by unit tests.
- Merged OCR output keeps source and confidence metadata.
- Benchmarks compare extracted identifiers, not only raw text length.

### Phase 1 Compute Expectations

EasyOCR loads PyTorch models into memory once, then reuses them. CPU mode is supported but slower than GPU. Keep max-image-dimension controls in place and avoid running EasyOCR when barcode or exact catalog evidence already gives a strong match.

## Phase 2: Evidence, Validation, And Error Correction

*(Goal: improve identification quality without adding another heavy OCR backend.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **2.1** | `ExtractedIdentifiers` Evidence | Attach source, confidence, role, variant/backend, and box metadata to extracted catalog/title/label/barcode evidence. | `OcrResult`, `OcrTextLine`, parser | Ranker can distinguish strong OCR from noisy text. |
| **2.2** | Discogs Catalog Normalizer | Add Discogs-style normalization: uppercase, strip punctuation, split letter/number groups, and compare shadow-like forms. | `identifier_parser.py`, `candidate_ranker.py` | Better catalog search/ranking across spacing and punctuation variants. |
| **2.3** | Barcode Checksum Correction | Validate UPC/EAN check digits and only repair OCR-like digit mistakes when checksum passes. | `barcode_detector.py`, parser | Higher precision barcode evidence. |
| **2.4** | Candidate-Conditioned Correction | After initial candidates return, compare OCR tokens with candidate artist/title/label/catalog/barcode metadata using weighted OCR-confusion distance. | Discogs candidates, ranker | Recovery from errors like `OO2LP` vs `002LP`. |
| **2.5** | Negative Evidence | Penalize candidates that contradict high-confidence barcode, catalog, year, or label evidence. | `CandidateRanker` | Fewer generic false positives. |
| **2.6** | Search Plan Builder | Move search-step construction out of `IdentifyService` into a testable planner. | Existing `_build_search_plan` | Isolated query planning tests. |
| **2.7** | Debug Trace | Log preprocessing variants, OCR sources, identifiers, search steps, score components, and final confidence band. | Existing logging | Faster failure diagnosis. |

### Phase 2 Acceptance Criteria

- No new heavyweight runtime dependency is required.
- Existing API response shape remains stable.
- Candidate ranking tests cover positive and negative evidence.
- Barcode checksum behavior is unit-tested with valid, invalid, and repairable examples.
- Catalog normalization handles punctuation, spacing, case, and OCR digit/letter confusions.
- Debug output can explain why the top candidate won.

## Phase 3: Geometry And Preprocessing Improvements

*(Goal: improve OCR input quality before adding more OCR compute.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **3.1** | Image Quality Metrics | Compute blur, exposure, glare/saturation, and minimum-size signals for diagnostics. | Pillow, optional OpenCV | Quality metadata for logs and future client hints. |
| **3.2** | Deskew Variants | Add text deskew/rotation variants for OCR when skew is detected. | Optional OpenCV | Better Tesseract/EasyOCR line segmentation. |
| **3.3** | Perspective Correction | Add quadrilateral crop/warp variants for sleeve and cover photos. | Optional OpenCV | Cleaner cover/sleeve OCR input. |
| **3.4** | Label Crop Detection | Add circular/elliptical label crop variants for record-label photos. | Optional OpenCV | Less background noise in center-label OCR. |
| **3.5** | Threshold Selection | Add Otsu and small morphology variants, then cheaply select the best few OCR inputs. | Optional OpenCV or Pillow | Better text contrast without exploding OCR passes. |

### Phase 3 Acceptance Criteria

- OpenCV remains optional and feature-flagged.
- Existing Pillow-only preprocessing still works.
- Debug images include geometry variants when enabled.
- OCR pass count stays bounded.
- Tests cover variant generation and fallback behavior when OpenCV is unavailable.

## Phase 4: Candidate Visual Verification

*(Goal: use image similarity to verify top candidates, not to replace OCR search.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **4.1** | Candidate Image Fetch/Cache | Reuse Discogs cover image URLs for top candidates with bounded caching. | Discogs result data | Candidate images available for verification. |
| **4.2** | Perceptual Hash Check | Compare upload/crop against candidate cover art using a small optional image-hash utility. | Pillow or optional imagehash | Cheap visual reranking signal. |
| **4.3** | ORB/Homography Check | For cover/sleeve photos, use ORB feature matches and homography as a stronger verification signal. | Optional OpenCV | Robust visual confirmation for top candidates. |
| **4.4** | Benchmark CLIP Separately | Evaluate CLIP-style embeddings only after simpler methods are measured. | Separate experiment | Data-driven decision before adding model weight. |

### Phase 4 Acceptance Criteria

- Visual verification only runs for top candidates.
- Network/cache behavior is bounded and observable.
- OCR/catalog/barcode evidence remains the primary search path.
- Visual signals can rerank but not override exact barcode/catalog contradictions.

## Rollout Plan

1. Keep current Tesseract path as the baseline.
2. Keep EasyOCR disabled by default outside development.
3. Implement Phase 2 evidence/error-correction work first.
4. Benchmark before/after on a fixed bad-label image set.
5. Add optional OpenCV preprocessing behind a feature flag.
6. Add visual verification only after candidate ranking is explainable.
7. Enable production features gradually through environment flags.

## Risks And Mitigations

| Risk | Mitigation |
| :--- | :--- |
| Larger dependency footprint | Keep EasyOCR and OpenCV/image-hash features optional. |
| Slow requests | Gate expensive OCR and visual verification behind evidence thresholds. |
| More OCR text creates more noise | Prefer confidence, backend agreement, role evidence, and negative evidence gates. |
| False correction | Only apply barcode repair with checksum validation; only apply catalog correction when candidate evidence supports it. |
| Hard-to-debug ranking | Add structured score traces and confidence bands. |
| OpenCV unavailable in deployment | Keep Pillow-only preprocessing as the default fallback. |

## Success Metrics

- Higher top-1/top-3 identification rate on the sample bad-label set.
- Lower false-positive rate for generic artist/title matches.
- More correct catalog-number extraction after normalization/correction.
- More exact barcode matches with checksum validation.
- Lower average OCR fallback cost for already-confident cases.
- Debug trace available for every failed or low-confidence identification.

## Recommended Next Step

Implement Phase 2 first:

- Add Discogs-style catalog normalization.
- Add UPC/EAN checksum validation and safe repair.
- Preserve structured OCR evidence into parsed identifiers.
- Add negative evidence and score tracing in `CandidateRanker`.
- Extend the benchmark script to compare candidate outcomes before and after these changes.
