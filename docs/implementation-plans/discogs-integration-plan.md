# Code Implementation Plan: Milestone 3 — Discogs Integration

## M3 Goal
To create a stable, resilient, and efficient service layer responsible for all communication with the Discogs API. This service must respect rate limiting and minimize external calls via caching.

## Key Deliverables
1.  **`DiscogsService` Module:** A clean Python class/module managing all external interaction.
2.  **Authenticated Requests:** Securely handle the Personal Access Token.
3.  **Caching Layer (`discogs_release_cache`):** Logic to read and write metadata before hitting Discogs.
4.  **Rate Limiter/Throttler:** Mechanism to prevent exceeding the 60 requests/minute quota.
5.  **Core Functions:** Implement search (barcode, catno) and single-metadata fetch endpoints.

## Implementation Phases & Tasks

### Phase 1: Foundation and Security (The Setup)
*(Goal: Establish secure connectivity and core module structure.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **1.1** | `Config & Token Manager` | Securely load the Discogs Personal Access Token from environment variables. Implement a wrapper for token management and basic API configuration (base URL, User-Agent). | None | Configuration class/service that provides the authenticated header structure. |
| **1.2** | `DiscogsClient Core` | Create the base HTTP client module (e.g., using Python's `requests`). Implement generic methods for handling requests and standardized JSON error parsing. | 1.1 | A basic, non-throttled class that can successfully send an authenticated request to Discogs and return the raw response. |
| **1.3** | `Service Interface Definition` | Define the public interface of the `DiscogsService` (e.g., `search_by_barcode()`, `fetch_metadata(id)`). This isolates business logic from HTTP details. | 1.2 | A clean class structure defining all future Discogs-related methods. |

### Phase 2: Resilience and Efficiency (The Guardrails)
*(Goal: Implement the operational constraints—rate limits and caching.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **2.1** | `Rate Limiter Implementation` | Implement a rate limiting algorithm (e.g., Token Bucket or simple time-based queue) within the `DiscogsClient Core`. This logic must pause/retry requests if the limit is approached/exceeded. | 1.2 | A decorator or wrapper function that ensures calls to the client respect the $\approx$60 RPM quota. |
| **2.2** | `Cache Table Schema` | Create and migrate the `discogs_release_cache` table in PostgreSQL (ID, raw JSON payload, cache expiration timestamp). | M2 (Existing DB setup) | Database migration file for the caching table. |
| **2.3** | `Caching Service Logic` | Implement a service method that wraps external calls: **Check Cache $\to$ If Hit, Return Cached Data $\to$ If Miss, Execute External Call $\to$ Store Result in Cache.** | 1.2, 2.2 | Function that provides cached or fresh Discogs data, ensuring the API is protected from redundant calls. |

### Phase 3: Core Functionality (The Search & Fetch)
*(Goal: Implement the required search and retrieval methods.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **3.1** | `Search by Barcode` | Implement the specific method to call Discogs using a barcode query (`/database/search?barcode=...`). This function must utilize the caching layer (2.3). | 1.3, 2.3 | Function that returns raw search results for a given barcode. |
| **3.2** | `Search by Catalog/Artist/Title` | Implement generic search methods allowing query parameters like catalog number or artist name. | 1.3, 2.3 | Flexible function capable of executing various structured searches against Discogs. |
| **3.3** | `Metadata Fetcher (Single ID)` | Implement the method to fetch complete metadata for a specific known release ID (`/database/release/{id}`). This is essential for later M4 imports. | 1.3, 2.3 | Function that returns the full JSON payload of a single Discogs release. |

### Phase 4: Integration and Testing (The Polish)
*(Goal: Connect M3 logic to M2 data structures and ensure stability.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **4.1** | `Internal Data Mapping` | Create a utility layer that maps the complex, nested Discogs JSON structure into your simpler internal data model (e.g., extracting fields like `title`, `artist`, `catalog_number`). | 3.3 | Functions to normalize and flatten raw Discogs responses. |
| **4.2** | **End-to-End Test Suite** | Write comprehensive tests: a) Basic client connection test; b) Cache miss $\to$ API call $\to$ Cache write test; c) Rate limiting behavior test (simulating quota exhaustion). | All previous tasks | Comprehensive unit and integration tests for the `DiscogsService`. |

---
### Summary of Flow (M3 Focus)

The flow is strictly focused on isolation, protection, and fetching:

**`Request` $\to$ [Rate Limiter] $\to$ `Caching Service` $\to$ [IF MISS] $\to$ `Discogs Client Core` $\to$ Discogs API $\to$ `Mapper` $\to$ Return Data.**
