# Code Implementation Plan: Milestone 6 — Image Identification Pipeline (M6)

## M6 Goal
To create a complete, multi-stage pipeline that transforms an uploaded image into a ranked list of candidate Discogs releases, respecting the priority of local database matches over external searches.

## Dependencies Checklist
*   **M1/M2:** Stable FastAPI infrastructure and PostgreSQL models (`releases`).
*   **M3:** The robust `DiscogsService` module (authenticated, cached, rate-limited).
*   **M4:** The persistence logic is stable, including the ability to check for existing releases via internal ID.

## Implementation Phases & Tasks

### Phase 1: Input and Image Preparation (The Pre-Flight Check)
*(Goal: Handle file I/O and normalize the input data.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **1.1** | `Identify Router` (`POST /identify`) | Define the FastAPI endpoint, handling file validation (size, type) and temporary storage for the uploaded image. This module initiates the pipeline by passing the file path to the next service. | M4 Input Handling Logic | Basic API handler that accepts a file and passes its location to the `ImageProcessor`. |
| **1.2** | `Image Processor` | Implement the normalization routines: resizing, grayscale conversion, noise reduction, rotation correction. This ensures subsequent vision tasks operate on consistent data. | Vision Libraries (OpenCV/Pillow) | Function that takes a raw image path and returns a processed image object ready for analysis. |

### Phase 2: Feature Extraction (The Sensor Suite)
*(Goal: Extract all possible identifiers from the prepared image.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **2.1** | `Barcode Detector` | Implement vision algorithms (e.g., using `pyzbar`) to detect and extract barcode strings from the processed image. This is high priority. | 1.2, Vision Libraries | Function that returns a list of detected barcodes (or empty list). |
| **2.2** | `OCR Extractor` | Implement OCR processing (e.g., Tesseract/EasyOCR) on areas of interest identified by the processor. This is the primary fallback signal. | 1.2, Vision Libraries | Function that returns a comprehensive string of all recognized text from the image. |
| **2.3** | `Identifier Parser` | Implement advanced pattern matching (regex) to parse raw OCR output into structured identifiers: Catalog Number (`BC 01`), Artist Name, Title Fragments, etc. | 2.2 | Function that takes raw text and outputs a dictionary of high-confidence potential search keys. |

### Phase 3: Candidate Search and Validation (The Core Logic)
*(Goal: Execute the "Local Lookup First" policy before calling Discogs.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **3.1** | `Initial Search Strategy` | Create a function that gathers all extracted identifiers (2.1, 2.3) and determines the search priority sequence: Barcode $\to$ Catalog Number $\to$ Artist+Title Query $\to$ Free Text Query. | 2.1, 2.3 | Logic defining the order of Discogs API calls based on identifier certainty. |
| **3.2** | `Local Database Lookup` (Crucial) | Implement a function that checks the internal database (`releases`) using all available identifiers. If an exact match is found via `discogs_release_id`, it bypasses external searches and returns the pre-existing release metadata immediately. | M4 Persistence Logic, M2 Models | Function: `find_internal_match(identifiers) -> InternalReleaseModel`. (This handles the "Local Lookup First" rule). |
| **3.3** | `External Search Execution` | If 3.2 returns no match, execute the search strategy (3.1) by calling the stable, rate-limited `DiscogsService` (M3), utilizing caching and throttling mechanisms. | M3 DiscogsService, 3.1 | Function that receives raw results from Discogs for a given query type. |

### Phase 4: Ranking and Output (The Presentation Layer)
*(Goal: Refine the external search results into ranked candidates and present them.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **4.1** | `Candidate Ranking Engine` | Implement the weighted scoring model specified in the Pipeline Spec (e.g., Barcode match = +100). This engine takes raw search results and assigns a confidence score to each candidate. | M3 Data Mapping, API Spec Scoring Rules | Function that sorts candidates by calculated relevance score. |
| **4.2** | `Final Candidate Selection` | Apply the limit (recommended: 5) and format the final output structure, ensuring it strictly matches the required JSON schema for the Android client (`discogs_release_id`, artist, title, etc.). | 3.2, 4.1, API Spec Response | The final structured response object ready to be serialized to JSON. |
| **4.3** | `Orchestrator & Error Handling` | Implement the main pipeline orchestration function: Execute (3.2) $\to$ [IF Hit] $\to$ Return Internal Match $\to$ [IF Miss] $\to$ Execute External Search (3.3) $\to$ Rank & Select (4.1, 4.2) $\to$ Handle all processing errors gracefully. | All previous tasks | The complete `POST /identify` handler that drives the entire identification process. |
