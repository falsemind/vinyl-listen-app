# Identification Pipeline

The identification pipeline turns an uploaded vinyl image into ranked release candidates. It lives in `backend/app/pipelines/identification/` and is orchestrated by `IdentifyService`.

## High-Level Flow

```text
Upload bytes
  ↓
ImageProcessor.prepare
  ↓
IdentifierExtractor.extract
  ├── BarcodeDetector.detect
  ├── OcrCascade.extract
  ├── IdentifierParser.parse
  └── analyze_ocr_layout
  ↓
build_search_plan
  ↓
Discogs/local candidate lookup
  ↓
CandidateRanker.rank
  ↓
IdentifyResponse
```

## Data Model

Core dataclasses live in `models.py`.

| Model | Purpose |
| --- | --- |
| `ImageVariant` | Named PNG image bytes used for barcode or OCR passes. |
| `ImageQualityMetrics` | Width, height, blur, luminance, glare, contrast, and dark/bright pixel ratios. |
| `PreparedImage` | Normalized upload plus digest, size, dimensions, variants, and quality metrics. |
| `OcrTextLine` | OCR line text with confidence, source backend, optional box, and variant name. |
| `OcrResult` | OCR backend output: raw text, selected variants, model name, elapsed time, and lines. |
| `OcrRoleEvidence` | Layout-derived role hints such as artist/title/label-like text. |
| `IdentifierEvidence` | Parsed identifier plus source, confidence, optional role, and box. |
| `ExtractedIdentifiers` | Barcodes, catalog numbers, artist, title, year, label, text fragments, raw OCR text, and evidence. |
| `IdentifyCandidate` | Local or Discogs release candidate with ranking metadata. |

## Image Processing

`preprocess.py` contains `ImageProcessor`.

### What it does

- Opens and validates the uploaded image with Pillow.
- Normalizes image orientation and size.
- Computes quality metrics.
- Creates barcode-oriented and OCR-oriented variants.
- Optionally creates geometry-corrected variants with OpenCV.
- Optionally writes debug PNGs for local OCR inspection.

### Standard variants

The processor creates variants such as:

- `normalized`
- `grayscale`
- `adaptive_threshold`
- `adaptive_threshold_inverted`
- `threshold`
- `threshold_low`
- `inverted_threshold`
- `sharpened`
- `upscaled_grayscale`
- `upscaled_threshold`

It also builds cropped label/catalog-band variants and optional geometry variants when `identify_geometry_preprocess_enabled` is true.

### Debug images

When `identify_debug_preprocess_images_enabled` is enabled, generated variants are written to `identify_debug_preprocess_images_dir`. This is useful for OCR tuning but should be treated as local/generated output.

## Barcode Detection

`barcode_detector.py` contains `BarcodeDetector`.

It scans `PreparedImage` variants and decodes barcode payloads. Detected values are passed into the parser so the final identifier set can combine direct barcode evidence with OCR-derived evidence.

Barcode values later go through normalization and GTIN checksum validation/repair in `normalization.py` and `identifier_parser.py`.

## OCR Backends

`ocr_backends.py` defines the backend abstraction and cascade.

### OcrCascade

`OcrCascade` runs a primary backend and optional fallback backend.

- If the primary backend raises an OCR backend error, fallback runs.
- If the primary backend returns no text, fallback runs.
- If primary returns usable text, fallback is skipped.

### Backend selection

`build_default_ocr_cascade` reads `identify_ocr_backend`.

Supported values:

- `tesseract`
- `mlx_vlm`
- `paddleocr_vl`
- `auto`

Tesseract can be enabled as fallback with `identify_ocr_tesseract_fallback_enabled`.

### Tesseract backend

`TesseractOcrBackend` uses `OcrExtractor`, which is the local OCR wrapper. It returns text lines, selected variants, and elapsed time.

### MLX/VLM backend

`MlxVlmOcrBackend` sends selected image variants to an external VLM OCR service. It uses configured service URL, endpoint path, model name, API key, timeout, max image dimension, max tokens, prompt, selected variant names, and variant count.

This backend is unavailable unless `identify_mlx_vlm_service_url` is configured.

### PaddleOCR-VL backend

`PaddleOcrVlBackend` uses PaddleOCR-VL settings, device selection, optional recognition backend/server configuration, timeout, and selected image variants. It caches expensive pipeline setup by configuration.

## OCR Extraction And Layout

`ocr_extractor.py` performs OCR across selected variants and returns normalized `OcrResult` data.

`ocr_layout_analyzer.py` inspects OCR lines and assigns role-like evidence. This helps downstream search and ranking distinguish likely title, artist, label, and other useful text from generic legal or manufacturing text.

## Identifier Parsing

`identifier_parser.py` converts raw OCR text plus detected barcodes into `ExtractedIdentifiers`.

It extracts:

- Barcodes.
- Catalog numbers.
- Artist and title candidates.
- Release year.
- Label.
- Searchable text fragments.
- `IdentifierEvidence` for every extracted value.

### Important heuristics

The parser includes many vinyl-specific cleanup rules:

- Removes noisy legal, rights, company, URL, and contact lines.
- Detects labeled metadata lines.
- Handles adjacent catalog-number tokens.
- Repairs OCR-confused catalog numbers at token edges.
- Normalizes DJ/artist/title line patterns.
- Filters low-value year-like and short lines.
- Validates GTIN checksums before accepting or repairing barcode candidates.

The parser keeps raw text and evidence so later stages can still use lower-confidence clues without treating them as primary identifiers.

## Normalization

`normalization.py` centralizes identifier comparison helpers.

It provides:

- Catalog number normalization.
- Catalog match keys.
- Catalog number comparison with punctuation/spacing tolerance.
- Barcode normalization.
- OCR barcode repair.
- GTIN checksum validation.

This keeps parser, search planner, and ranker behavior consistent.

## IdentifierExtractor

`extractor.py` is the pipeline coordinator.

It runs:

1. `BarcodeDetector.detect(prepared_image)`.
2. OCR through the configured `OcrCascade`.
3. `IdentifierParser.parse(ocr_result.raw_text, barcodes=detected_barcodes)`.
4. `analyze_ocr_layout(ocr_result.lines)`.
5. Evidence enrichment by matching parsed values back to OCR source lines.

The final `ExtractedIdentifiers` includes both parsed values and source-aware evidence.

## Search Evidence

`search_evidence.py` scores whether a text value is worth using as a Discogs query.

It reduces noisy searches by penalizing:

- Label-like boilerplate.
- Very short or low-information values.
- Mixed-case OCR noise.
- Weak title-case phrases.

`SearchEvidenceScore.is_query_worthy` is used by search planning to avoid low-value Discogs calls.

## Search Planning

`search_planner.py` turns `ExtractedIdentifiers` into ordered `SearchStep` objects.

Search strategies include:

| Strategy | Inputs | Purpose |
| --- | --- | --- |
| `barcode` | Barcode | Highest-precision lookup. |
| `catalog_number` | Catalog number | Strong lookup when barcode is missing or unreadable. |
| `catalog_identity_context` | Catalog plus identity text | Catalog search with artist/title/label context. |
| `vlm_discogs_query` | VLM-generated query-like text | Uses stronger VLM text when available. |
| `ocr_role_context` | Layout role evidence | Combines OCR role hints into Discogs queries. |
| `artist_title` | Parsed artist and title | Structured Discogs search. |
| `identity_context` | Artist/title/label fragments | Broad identity search. |
| `tracklist_context` | Tracklist-like fragments | Helpful when cover OCR finds tracks but not release title. |
| `raw_context` | Cleaned raw OCR lines | Controlled fallback for useful raw text. |
| `free_text` | Remaining high-value fragments | Last-resort text search. |

The planner deduplicates normalized query keys and caps raw-context searches. It also strips track prefixes and credit-style text that often creates false positives.

## Candidate Ranking

`candidate_ranker.py` scores each `IdentifyCandidate` against extracted identifiers.

### Positive evidence

Scores increase for:

- Local lookup source.
- Barcode match.
- Catalog number match.
- Artist match.
- Title match.
- Artist/title pair match.
- Label match.
- Year match.
- General OCR text overlap.
- OCR role evidence, such as release title, layout label, artist, title, and label.
- Discogs-validated text.

### Negative evidence

Scores decrease when strong extracted evidence contradicts candidate fields:

- Barcode contradiction.
- Catalog number contradiction.
- Artist contradiction.
- Title contradiction.
- Label contradiction.
- Year contradiction.

### Output

The ranker sorts candidates by confidence and title. Each ranked candidate contains:

- `confidence`
- `matched_on`
- `score_trace`

This makes API results explainable and helps tests assert why a candidate won.

## End-To-End Service Behavior

`IdentifyService` combines pipeline output with candidate lookup.

1. Local database search runs first.
2. Local candidates are ranked and returned immediately when present.
3. If local search misses, Discogs search steps execute in planned order.
4. Results are deduplicated by Discogs release ID.
5. Search stops early when a confident external candidate already covers the extracted identity context.
6. Final candidates are ranked and limited before response serialization.

## Test Coverage

Pipeline tests live in `backend/tests/pipelines/`:

- `test_candidate_ranker.py`
- `test_identifier_extractor.py`
- `test_identifier_parser.py`
- `test_ocr_backends.py`
- `test_ocr_extractor.py`
- `test_ocr_layout_analyzer.py`
- `test_preprocess.py`
- `test_search_evidence.py`
- `test_search_planner.py`

Service-level integration around this pipeline is covered by `backend/tests/services/test_identify_service.py` and route behavior by `backend/tests/api/test_identify_api.py`.
