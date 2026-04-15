
# Code Implementation Plan: Milestone 4 — Release Import & Metadata API

## M4 Goal
To build the full lifecycle process allowing external release metadata (from Discogs) to be reliably fetched, normalized, and stored in the local database, creating the internal `release_id`.

## Dependencies Checklist
*   **M1/M2:** FastAPI skeleton is running; PostgreSQL connection established (`releases`, `sessions`, etc., models exist).
*   **M3:** The robust `DiscogsService` module is complete (stable API client, rate limiting, caching works).

## Implementation Phases & Tasks

### Phase 1: Data Structure and Persistence Logic (The Storage)
*(Goal: Ensure we can map Discogs fields to our internal database schema.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **1.1** | `Release Mapper Service` | Create a dedicated service that takes the raw JSON response from Discogs (M3 output) and transforms it into a standardized Python object/dictionary matching our internal database schema fields. This includes normalizing genres and styles lists. | M3 Output Schema, M2 DB Models | Function: `map_discogs_to_internal(raw_json) -> InternalReleaseData`. |
| **1.2** | `Persistence Service` | Implement the core logic to interact with SQLAlchemy. This service must handle two scenarios: **INSERT** (new record) and **UPDATE** (if a metadata refresh is required). | M2 DB Models, 1.1 | Function: `save_or_update_release(data) -> release_id`. |
| **1.3** | `Idempotency Check` | Enhance the persistence service to check for an existing record based on the `discogs_release_id` *before* attempting an insert, ensuring the import process is idempotent (running it twice doesn't create two records). | M2 DB Models | Logic that returns the existing `release_id` if a match by Discogs ID is found. |

### Phase 2: The Import Endpoint (`POST /releases/import`)
*(Goal: Build the business logic for creating and storing new releases.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **2.1** | `Import Endpoint Logic` | Implement the FastAPI handler for `POST /releases/import`. This is the orchestration layer. | M3, 1.3, 1.1 | The primary import function that manages the flow: Validate Input $\to$ Fetch Data (M3) $\to$ Check Internal State (1.3) $\to$ Map & Save (1.1, 1.2). |
| **2.2** | `Release Importer Service` | Centralize the entire import workflow into a single service layer function that handles all dependencies (Discogs fetch, Mapping, Persistence). This keeps the API handler clean. | M3, 1.2, 1.1 | A dedicated, reusable `import_release(discogs_id)` function. |
| **2.3** | `Error Handling` | Implement robust error handling for import failures: e.g., Discogs ID not found, network timeout during fetch, database constraint violations (e.g., unique index failure). Return the standard error format. | 2.1 | API handler that correctly catches and reports specific M4/M3 errors to the client. |

### Phase 3: Metadata Retrieval (`GET /releases/{release_id}`)
*(Goal: Allow the Android app to retrieve complete, local data using its preferred ID.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **3.1** | `Release Retrieval Service` | Implement a function that takes the internal `release_id` and queries the local database (`releases`). This should be a highly optimized, read-only operation. | M2 DB Models | Function: `get_internal_release(release_id) -> ReleaseModel`. |
| **3.2** | `Retrieval Endpoint Logic` | Implement the FastAPI handler for `GET /releases/{release_id}`. This should validate that the provided ID exists in the database before attempting retrieval. | 3.1 | Functional endpoint returning full, local release metadata as per API Spec. |

### Phase 4: Review and Polish
*(Goal: Ensure stability and readiness for M5.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **4.1** | `Integration Testing` | Test the entire flow end-to-end: Send an external ID $\to$ Check if it's in cache (M3) $\to$ Import via API (M4) $\to$ Verify record exists in DB $\to$ Retrieve using internal ID endpoint (M4). | All previous tasks | Passing E2E test suite covering import and retrieval. |
| **4.2** | `Documentation Update` | Final review of the M4 documentation, ensuring request/response examples are accurate for both endpoints. | 2.1, 3.2 | Updated README/API Spec reflecting the operational flow. |

---
### Summary of Logic Flow (M4 Focus)

The import process is a chain reaction:

**`Client POST /import` $\to$ `Validate Discogs ID` $\to$ `Call M3 DiscogsService` $\to$ [IF Success] $\to$ `Map Data` $\to$ [IF Not Exists] $\to$ `Save to DB (Create release_id)` $\to$ `Return Release ID`**
