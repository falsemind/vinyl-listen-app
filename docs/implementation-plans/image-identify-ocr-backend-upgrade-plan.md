# Code Implementation Plan: Image Identify OCR Backend Upgrade

## Goal
Improve vinyl label identification across varied fonts, colors, layouts, and text sizes by adding neural OCR backends behind the existing image-identification pipeline.

The upgraded pipeline should keep the current Tesseract path as the fast local baseline, then progressively fall back to stronger OCR only when confidence is low or Discogs validation fails.

## Current Problem
The current pipeline has improved catalog-number extraction, color-channel preprocessing, box-based Tesseract OCR, raw OCR query generation, and Discogs-result validation. It still fails on labels where:

* Font shape is unusual enough that Tesseract misreads text.
* Text is low-contrast, small, curved, distressed, or logo-like.
* Correct Discogs results never appear because OCR did not produce useful candidate queries.
* Parsed artist/title fields are noisy and need external validation.

More regex and image variants will keep producing diminishing returns. The next upgrade should add better text detection and recognition, not more one-off parsing rules.

## Target Architecture

```text
Uploaded image
  -> ImageProcessor variants
  -> BarcodeDetector
  -> OCR backend cascade
       1. TesseractBackend fast path
       2. EasyOcrBackend fallback
       3. PaddleOcrBackend fallback
  -> IdentifierParser
  -> SearchPlanBuilder
  -> DiscogsService search
  -> CandidateRanker with OCR evidence validation
  -> IdentifyResponse
```

## Backend Interface

Create a small interface so OCR engines are swappable:

| Component | Responsibility |
| :--- | :--- |
| `OcrBackend` | Accept a `PreparedImage`; return OCR lines with text, confidence, source backend, and optional bounding box. |
| `OcrResult` | Structured OCR output: `text`, `confidence`, `backend`, `variant`, `box`. |
| `OcrCascade` | Runs backends in order based on confidence thresholds and feature flags. |
| `OcrEvidenceBuilder` | Converts backend output into raw text, catalog candidates, context phrases, and debug evidence. |

The parser should continue to accept plain raw text, but the ranking/search layers should prefer structured OCR evidence when available.

## Phase 1: EasyOCR Fallback
*(Goal: Quickly test whether neural OCR improves bad-label candidate generation without committing to the heavier PaddleOCR dependency.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **1.1** | `OcrBackend` Interface | Define protocol/dataclasses for backend output. Keep Tesseract wrapped behind the same interface. | Existing OCR pipeline | Shared OCR backend contract. |
| **1.2** | `EasyOcrBackend` | Add optional EasyOCR backend using `easyocr.Reader(["en"], gpu=False)` by default. Load reader lazily and reuse it. | EasyOCR, PyTorch | Backend that returns boxes, text, confidence. |
| **1.3** | Feature Flag | Add config flag such as `IDENTIFY_EASYOCR_ENABLED=false` and `IDENTIFY_EASYOCR_MIN_CONFIDENCE`. | Settings config | Safe opt-in rollout. |
| **1.4** | Cascade Trigger | Run EasyOCR only when Tesseract produces no barcode, no high-confidence catalog, or low candidate confidence after Discogs ranking. | Existing ranker/search | Bounded fallback path. |
| **1.5** | Evidence Merge | Merge EasyOCR lines with Tesseract raw text. Deduplicate by normalized text and preserve confidence/source. | 1.1, 1.2 | Richer OCR evidence for parser and ranker. |
| **1.6** | Benchmark Harness | Add a local script/test helper for the sample-label folder to compare Tesseract vs EasyOCR candidate extraction and latency. | Test images | Repeatable quality and compute report. |

### Phase 1 Acceptance Criteria

* EasyOCR is optional and disabled by default.
* No model is loaded unless fallback is triggered.
* Existing focused identify tests still pass.
* Benchmark report includes per-image latency and extracted catalog candidates.
* At least a meaningful subset of previously bad labels produces better candidate queries.

### Phase 1 Compute Expectations

EasyOCR is easier to integrate but less predictable for performance planning. It loads PyTorch models into memory once, then reuses them. CPU mode is supported but slower than GPU. Expect:

* First request: slow due to model load.
* Subsequent CPU fallback: likely seconds per image depending machine and image size.
* Memory: higher than Tesseract; acceptable if backend is lazy-loaded and reused.

## Phase 2: PaddleOCR Production Fallback
*(Goal: Add a more robust and tunable OCR backend if EasyOCR improves results but is not strong or predictable enough.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **2.1** | `PaddleOcrBackend` | Add optional PaddleOCR backend using mobile English/general OCR models first. | PaddleOCR runtime | Backend that returns text boxes and confidence. |
| **2.2** | Model Mode Config | Support `mobile` vs `server`, CPU/GPU, and max-side settings. | Settings config | Tunable performance profile. |
| **2.3** | Fallback Policy | Run PaddleOCR only if Tesseract + EasyOCR fail to produce a validated Discogs candidate. | OcrCascade | Third-stage fallback. |
| **2.4** | Result Normalizer | Normalize PaddleOCR output into the same `OcrResult` shape. | 1.1 | Backend-independent downstream logic. |
| **2.5** | Benchmark Comparison | Compare Tesseract, EasyOCR, PaddleOCR mobile, and PaddleOCR server on the same bad-label set. | 1.6 | Data-driven backend choice. |

### Phase 2 Acceptance Criteria

* PaddleOCR is optional and disabled by default.
* Mobile model is tested before server model.
* Backend selection is controlled through config.
* Benchmark output clearly shows quality gain vs latency/memory cost.
* The pipeline can stop early when Discogs validation reaches a high-confidence threshold.

### Phase 2 Compute Expectations

PaddleOCR has clearer official performance data than EasyOCR. Use it as the production-grade fallback if benchmark results justify it.

Expected local CPU profile:

* Mobile model: roughly low-single-digit seconds per fallback image.
* Server model: slower and more memory-heavy, useful only if mobile misses too much.
* GPU: much faster, but requires more deployment complexity and VRAM.

## Phase 3: Search and Ranking Integration
*(Goal: Ensure stronger OCR actually improves identification, not just raw text output.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **3.1** | SearchPlanBuilder | Move raw-context query generation out of `IdentifyService` into a dedicated component. | Existing query planner | Testable query planner. |
| **3.2** | OCR Evidence Ranking | Prefer candidates supported by multiple OCR backends or high-confidence text boxes. | OcrResult confidence/source | Better search priority. |
| **3.3** | Discogs Validation Gate | Stop running expensive OCR once a candidate reaches high confidence, e.g. exact catno plus raw OCR artist/title overlap. | CandidateRanker | Cost control. |
| **3.4** | Debug Payload/Logs | Log backend source, extracted candidates, queries fired, and ranking evidence. | Existing logging | Faster failure diagnosis. |

## Rollout Plan

1. Ship backend interface and keep current Tesseract behavior unchanged.
2. Add EasyOCR behind an environment flag.
3. Run local benchmark on known bad labels.
4. Enable EasyOCR fallback in development only.
5. Add PaddleOCR behind a separate flag if EasyOCR improves quality but remains inconsistent.
6. Compare all backends with the same sample set before enabling any new backend by default.

## Risks and Mitigations

| Risk | Mitigation |
| :--- | :--- |
| Large dependency footprint | Keep EasyOCR/PaddleOCR optional extras. |
| Slow first request | Lazy-load backend and warm it during app startup only when enabled. |
| CPU spikes | Run neural OCR only after low-confidence Tesseract/Discogs result. |
| Model downloads in production | Pin model cache directory and pre-bake models in deployment image. |
| More OCR text creates more noise | Use confidence, backend agreement, and Discogs validation as ranking gates. |

## Success Metrics

* Increase top-1 correct match rate on the bad-label sample set.
* Keep normal-label fast path close to current latency.
* Bound neural OCR fallback latency to an acceptable target, initially under 5 seconds on CPU.
* Improve explainability: every returned candidate should expose matched evidence in logs or debug output.

## Recommended Next Step

Implement Phase 1 as a spike:

* Add `OcrBackend` and `EasyOcrBackend`.
* Keep EasyOCR disabled by default.
* Add a benchmark command for `/Users/alex/Pictures/test-images`.
* Compare extracted catalog candidates and Discogs query coverage before deciding whether to proceed to PaddleOCR.
