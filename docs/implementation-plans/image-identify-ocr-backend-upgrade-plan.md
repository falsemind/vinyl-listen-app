# Code Implementation Plan: Image Identify OCR Pipeline Upgrade

## Goal

Replace the current EasyOCR-era identification plan with a VLM OCR service-first pipeline.

The upgraded pipeline should remove EasyOCR completely, use a direct MLX/VLM OCR service as the preferred OCR engine for image identification, and keep the PaddleOCR-VL wrapper as an optional adapter for comparison or fallback if the direct service path does not produce enough structure or quality. Tesseract should remain only as an explicit fallback or benchmark backend.

The main optimization target is end-to-end identification quality and latency, not raw OCR speed alone.

## Current Problem

The existing pipeline can extract useful text, but it spends too much time recovering from noisy OCR evidence.

Current backend capabilities include:

- Barcode detection before OCR.
- Tesseract OCR with fast and escalated configs.
- Optional EasyOCR fallback with confidence-bearing text lines.
- Identifier parsing for barcode, catalog number, artist, title, label, and year.
- Discogs search planning and candidate ranking.

Observed issues:

- EasyOCR is no longer a useful direction based on local tests.
- Tesseract often returns noisy lines that still look queryable.
- Noisy Tesseract output can trigger empty or misleading Discogs searches.
- OCR latency is less important than returning the right Discogs candidate in fewer calls.
- PaddleOCR-VL through the Python wrapper pulls heavy Paddle/PaddleX/PaddlePaddle dependencies into the backend even when model inference is served by MLX.
- Direct MLX/VLM serving can keep the backend lighter, but it needs explicit prompt design and response parsing.

## Target Architecture

```text
Mobile Upload
  -> Identify API
  -> Image preparation
       -> barcode detection
       -> bounded OCR variants
  -> OCR backend factory
       -> MlxVlmOcrBackend primary
       -> optional PaddleOcrVlBackend adapter for comparison/fallback
       -> optional Tesseract fallback only on OCR service failure/timeout
  -> Structured OCR evidence
       -> text lines
       -> confidence/source metadata
       -> layout/context hints when available
  -> Identifier parser
       -> barcode
       -> catalog numbers
       -> artist/title/label/year candidates
  -> Search planner
       -> fewer, higher-quality Discogs queries
  -> Candidate ranker
       -> positive evidence
       -> negative evidence
       -> traceable score reasons
  -> Identify response
```

Core principle: the direct VLM service should be the normal experiment path because it keeps OCR inference outside the backend image. PaddleOCR-VL can stay available as a heavier adapter path if direct MLX/VLM output is not accurate or structured enough. Tesseract should not be allowed to suppress VLM OCR by returning plausible junk.

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

Add or preserve enough metadata for implementation diagnostics:

- backend name and model name
- device or serving profile
- elapsed time
- timeout/fallback reason
- selected image variant names
- per-line selected variant/source hints where available
- structured identity hints such as catalog numbers, artist/title candidates, and best Discogs query suggestions

The parser can continue accepting plain raw text, but search planning and ranking should prefer structured evidence when available.

## Dependency Policy

The direct `mlx_vlm` path should not require PaddleOCR, PaddleX, or PaddlePaddle in the backend environment. It should depend only on normal backend dependencies plus the HTTP/client code needed to call the OCR service.

The optional `paddleocr_vl` path may keep heavier Paddle dependencies, but those dependencies must stay behind an explicit optional install/profile. This keeps Option 1 available for comparison without making it part of the default Docker image.

## Phase 1: Remove EasyOCR And Add Backend Selection

*(Goal: make the OCR backend explicit before adding the direct VLM service path.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **1.1** | EasyOCR Removal | Remove `EasyOcrBackend`, EasyOCR optional dependency, EasyOCR settings, and EasyOCR benchmark modes. | Existing OCR backend code | No EasyOCR import, config, test, or docs path remains. |
| **1.2** | Backend Selector | Add `IDENTIFY_OCR_BACKEND` with values like `mlx_vlm`, `paddleocr_vl`, `tesseract`, and `auto`. | Settings config | Runtime-selectable OCR backend. |
| **1.3** | Fallback Policy | Add explicit fallback settings; fallback only when the selected OCR service fails, times out, or is unavailable. | 1.2 | Tesseract cannot block VLM OCR by producing noisy text. |
| **1.4** | Tests | Update OCR backend unit tests around backend selection and fallback reasons. | 1.1-1.3 | Tests describe the new routing behavior. |
| **1.5** | Benchmark Harness | Rename/update the benchmark script around `mlx_vlm`, `paddleocr_vl`, `tesseract`, and `auto`. | Existing script | Repeatable quality and latency comparison. |

### Phase 1 Acceptance Criteria

- EasyOCR is gone from code, dependencies, tests, Docker, and docs.
- Backend selection is controlled by settings.
- Tesseract remains available only as an explicit backend or failure fallback.
- Unit tests cover VLM-primary routing even before the real service client is implemented.

## Phase 2: Direct MLX/VLM OCR Backend Integration

*(Goal: integrate a direct OCR/VLM service backend behind the existing OCR contract.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **2.1** | `MlxVlmOcrBackend` | Add a backend that sends selected image bytes to an MLX/VLM-compatible HTTP service. | Service URL/profile | Backend returning `OcrResult`. |
| **2.2** | VLM Prompt Contract | Define a strict OCR prompt that asks for visible label text, likely artist/title/catalog fields, and no invented metadata. | 2.1 | Stable service request format. |
| **2.3** | Serving Config | Add settings for service URL, model name, request timeout, max image dimension, prompt, and response mode. | Settings config | Local MLX and remote GPU setups use the same app code. |
| **2.4** | Local MLX Profile | Support the tested Apple Silicon flow using `mlx-vlm-server` at a configured URL such as `http://host.docker.internal:8111/` from Docker. | Local server | Dev profile for M-series Macs. |
| **2.5** | Remote/GPU Profile | Keep the app compatible with a hosted VLM service that exposes an OpenAI-compatible or documented HTTP API. | Deployment config | Server profile without Mac-specific assumptions. |
| **2.6** | Output Normalization | Convert VLM responses into normalized `OcrTextLine` values with source and stable raw text. | 2.1-2.3 | Parser receives clean, deduplicated text. |
| **2.7** | Optional PaddleOCR Adapter | Keep `PaddleOcrVlBackend` behind optional extras/config for comparison or fallback to the wrapper-based path. | Existing PaddleOCR work | Option 1 remains available without becoming the default. |
| **2.8** | Timeout Handling | Bound VLM service latency and return clear fallback/error metadata. | 2.3 | API does not hang on OCR service issues. |
| **2.9** | Bounded Variant Sweep | Send a small configured set of OCR variants to direct MLX/VLM and merge/dedupe the results with variant metadata. | 2.1-2.6 | Better recovery for labels where one crop/resolution misses catalog text. |
| **2.10** | Structured Identity Contract | Extend the prompt/normalizer to preserve `visible_lines`, `fields`, `catalog_numbers`, and `best_discogs_queries` when the VLM returns JSON. | 2.2, 2.6 | Direct MLX can produce search-ready evidence, not just OCR text. |

### Phase 2 Acceptance Criteria

- Direct MLX/VLM OCR can run through the identify pipeline through `OcrBackend`.
- Local MLX serving works via configuration, not hardcoded values.
- Remote/GPU serving can be configured without code changes.
- PaddleOCR-VL wrapper code remains optional and is not required for the direct MLX/VLM path.
- OCR failures produce observable fallback reasons.
- MLX/VLM debug artifacts show which variant images were sent and which variant produced each normalized line.
- Comparison fixtures show both Paddle-wrapper wins and direct-MLX wins, so fallback decisions stay data-driven.
- Tests use mocks/fakes and do not require model downloads.

## Phase 3: Evidence, Search Planning, And Ranking

*(Goal: use better OCR to make fewer, better Discogs calls.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **3.1** | Evidence Model | Preserve OCR source and quality hints through parsed identifiers. | Phase 2 | Search planner can prefer high-quality VLM OCR evidence. |
| **3.2** | Catalog Normalization | Normalize Discogs-style catalog numbers, separators, prefixes, and OCR confusions. | Existing parser | Better catalog search precision. |
| **3.3** | Search Plan Builder | Move search-step construction out of `IdentifyService` into a testable planner if not already done. | Existing `_build_search_plan` | Isolated query planning tests. |
| **3.4** | Query Budgeting | Limit low-quality loose text queries and stop Discogs search early when top candidates validate strong OCR/catalog identity evidence. | 3.1-3.3 | Fewer empty/incorrect Discogs calls. |
| **3.5** | Negative Evidence | Penalize candidates that contradict strong barcode, catalog, artist/title, label, or year evidence. | Candidate ranker | Safer reranking. |
| **3.6** | Score Trace | Return or log why the top candidate won. | Candidate ranker | Debuggable identification outcomes. |
| **3.7** | Search-Ready VLM Queries | Promote VLM `best_discogs_queries` and strong catalog/title fields into early search steps before loose raw text. | 2.10, 3.3 | One-shot Discogs queries for labels like `HARMONY & KID LIB DAT 095`. |
| **3.8** | Label-Noise Guards | Reject side headers, edition banners, credit/production-year lines, and OCR-confused track prefixes as identity/catalog evidence. | 3.2-3.4 | Avoid queries such as `Limited Edition BAILEY`, `Productions 2025`, and `THIS SIDE` as release title. |

### Phase 3 Acceptance Criteria

- VLM OCR evidence changes the search plan in measurable ways.
- Strong catalog/barcode evidence is searched before loose OCR text.
- Loose text searches are skipped or reduced when they add little value.
- Discogs search stops early when a candidate validates multiple strong OCR/catalog signals.
- Search planning tests cover direct-MLX structured query evidence and noisy VLM lines.
- Parser/search tests cover `harmonyLib` and `SCILIMITED012` noise patterns before benchmark fixtures are added.
- Ranking tests cover positive and negative evidence.

## Phase 4: Deployment, Benchmarking, And Observability

*(Goal: make the new OCR path practical to run locally and on servers.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **4.1** | Environment Docs | Document local Mac MLX setup, Docker host networking, remote GPU setup, and optional PaddleOCR wrapper setup separately. | Phase 2 | Clear setup paths for dev and production. |
| **4.2** | Health Check | Add an OCR backend readiness check or diagnostic log path. | Phase 2 | Fast failure when the configured OCR service or optional Paddle adapter is unavailable. |
| **4.3** | Benchmark Dataset | Keep a local bad-label image set with expected artist/title/catalog outcomes. | Existing samples | Quality benchmark, not just OCR text diff. |
| **4.4** | Benchmark Report | Compare `mlx_vlm`, optional `paddleocr_vl`, `tesseract`, and `auto` on OCR latency, Discogs calls, top-1/top-3 accuracy, and failures. | 4.3 | Data-driven rollout decision. |
| **4.5** | Runtime Packaging | Keep Paddle/PaddleOCR dependencies out of the default backend install unless the optional wrapper adapter is explicitly enabled. | Docker/pyproject | Smaller default backend image. |
| **4.6** | Golden Query Fixtures | Add expected best queries/candidates for known hard labels such as `harmonyLib` and `SCILIMITED012`. | 2.9-3.7 | Benchmarks catch regressions in the exact cases that motivated the tuning. |

### Phase 4 Acceptance Criteria

- Developers can run direct MLX/VLM OCR locally on Apple Silicon with documented settings.
- Developers can enable the PaddleOCR wrapper adapter separately if direct MLX/VLM needs comparison.
- A deployment can point the backend at a remote/GPU OCR or VLM service.
- Benchmarks measure full identification outcomes.
- Benchmarks include cases where the Paddle wrapper layout path wins and cases where direct MLX reads catalog text the wrapper misses.
- Logs show OCR backend, model, elapsed time, fallback reason, and Discogs query count.

## Phase 5: Candidate Visual Verification

*(Goal: use image similarity to verify top candidates later, not to replace OCR search.)*

Status: deferred for now. Do not include Phase 5 visual verification in the Phase 4 implementation pass.

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **5.1** | Candidate Image Fetch/Cache | Reuse Discogs cover image URLs for top candidates with bounded caching. | Discogs result data | Candidate images available for verification. |
| **5.2** | Perceptual Hash Check | Compare upload/crop against candidate cover art using a small optional image-hash utility. | Pillow or optional imagehash | Cheap visual reranking signal. |
| **5.3** | ORB/Homography Check | For cover/sleeve photos, use ORB feature matches and homography as a stronger verification signal. | Optional OpenCV | Robust visual confirmation for top candidates. |
| **5.4** | Embedding Benchmark | Evaluate CLIP-style embeddings only after simpler methods are measured. | Separate experiment | Data-driven decision before adding model weight. |

### Phase 5 Acceptance Criteria

- Visual verification only runs for top candidates.
- Network/cache behavior is bounded and observable.
- OCR/catalog/barcode evidence remains the primary search path.
- Visual signals can rerank but not override exact barcode/catalog contradictions.

## Rollout Plan

1. Remove EasyOCR and land backend selection first.
2. Add direct `mlx_vlm` behind a fakeable backend contract.
3. Wire local MLX settings for development.
4. Keep `paddleocr_vl` as an optional adapter for comparison or future fallback.
5. Improve direct MLX quality with bounded variant sweeps and a structured identity/query prompt.
6. Update parser/search/ranking to trust high-quality VLM OCR evidence, reject known label noise, and reduce loose queries.
7. Run benchmarks against bad-label samples, including `harmonyLib` and `SCILIMITED012`.
8. Make `mlx_vlm` the default only after benchmark results beat Tesseract and optional PaddleOCR on end-to-end identification quality.

## Risks And Mitigations

| Risk | Mitigation |
| :--- | :--- |
| Direct VLM response format is less structured than PaddleOCR output | Use a strict prompt, conservative parsing, and fixture-based response tests. |
| VLM service setup is environment-specific | Keep serving configuration outside code and support local/remote profiles. |
| VLM OCR latency is higher than Tesseract | Measure full identification latency including Discogs calls, not OCR time alone. |
| OCR service unavailable | Use bounded timeout, readiness diagnostics, and optional Tesseract fallback. |
| Heavy Paddle dependencies bloat backend image | Keep PaddleOCR wrapper dependencies optional and document the separate runtime profile. |
| PaddleOCR wrapper outperforms direct MLX/VLM | Keep `PaddleOcrVlBackend` available behind config and benchmark both paths. |
| Strong OCR evidence still maps to wrong Discogs candidate | Add negative evidence, score traces, and benchmark expected outcomes. |

## Success Metrics

- Higher top-1/top-3 identification rate on the bad-label sample set.
- Fewer empty or incorrect Discogs searches per upload.
- More correct catalog-number extraction after normalization.
- Lower false-positive rate for generic artist/title matches.
- Acceptable p95 identify latency with `mlx_vlm` enabled.
- Debug trace available for every failed or low-confidence identification.

## Recommended Next Step

Finish the Phase 3 quality pass before Phase 4/5:

- Add golden query fixtures for `harmonyLib` and `SCILIMITED012`.
- Keep direct `mlx_vlm` as the default lightweight path and keep `PaddleOcrVlBackend` optional for comparison.
- Convert remaining query/ranking debug needs into structured logs or score traces instead of temporary console output.
- Run the benchmark harness once the golden fixtures describe expected candidates and Discogs query budgets.
