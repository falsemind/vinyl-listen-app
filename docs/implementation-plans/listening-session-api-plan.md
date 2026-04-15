# Code Implementation Plan: Milestone 5 — Listening Session API

## M5 Goal
To implement all endpoints necessary to create, retrieve, and manage listening session logs, ensuring strict adherence to data validation rules.

## Dependencies Checklist
*   **M1/M2:** Database structure is complete (`releases`, `sessions` models are defined).
*   **M3/M4:** The local `releases` table is stable and populated via the import process (we must trust that the `release_id` refers to a valid, fully mapped record).

## Implementation Phases & Tasks

### Phase 1: Core Service Layer & Validation (The Logic)
*(Goal: Implement the core business logic for session creation and ensure data integrity before writing.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **1.1** | `Sessions Service Interface` | Define the public interface of the service layer (e.g., `create_session()`, `get_sessions_by_release(id, limit, offset)`). This separates persistence logic from API handling. | M2 DB Models | Clean service class ready to handle business operations. |
| **1.2** | `Session Input Validation` | Implement a validation function that checks all incoming POST data fields: Rating must be 1-5; `played_at` must be valid ISO8601 datetime format. | API Spec (Validation Rules) | Function that throws specific, standardized exceptions if input constraints are violated. |
| **1.3** | `Reference Validation Logic` | Implement a crucial validation check: Given a `release_id` and a specified `side` ("A", "B"), query the local `releases` metadata to confirm that this side exists for the given release. | M2 DB Models, 1.2 | Function that throws a specific error (e.g., `invalid_side`) if the side doesn't match the release data. |
| **1.4** | `Session Persistence Logic` | Implement the database transaction to insert the validated session record into the `sessions` table. This should handle generating and returning the new unique `session_id`. | M2 DB Models, 1.3 | Function: `save_new_session(validated_data) -> SessionID`. |

### Phase 2: API Endpoint Implementation (The Interface)
*(Goal: Build the public-facing routes that handle client interaction.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **2.1** | `POST /sessions` Endpoint | Implement the API handler. This route orchestrates: Input Validation (1.2) $\to$ Reference Validation (1.3) $\to$ Service Creation (1.4). Returns 201 Created upon success. | 1.1, 1.2, 1.3, 1.4 | Fully functional POST endpoint for logging new sessions. |
| **2.2** | `GET /sessions/{session_id}` Endpoint | Implement the handler to retrieve a single session by its internal ID, ensuring the record exists before querying and returning it. | M2 DB Models | API endpoint providing detailed information for one specific listening event. |
| **2.3** | `GET /releases/{release_id}/sessions` Endpoint | Implement the history endpoint. This must handle query parameters (`limit`, `offset`) correctly to provide proper database pagination. | 1.1, M2 DB Models | API endpoint that returns a paginated list of sessions for a given release. |

### Phase 3: Review and Polish (Stability)
*(Goal: Ensure the system is reliable in production scenarios.)*

| Task ID | Module/Component | Description | Dependencies | Deliverable |
| :--- | :--- | :--- | :--- | :--- |
| **3.1** | `Error Response Standardization` | Review all validation points (M5) and ensure that specific errors (e.g., `Rating too high`, `Side not found`) are returned using the mandated error response format (`{"error": {"code": ..., "message": ...}}`). | 1.2, 1.3, API Spec | Consistent and informative error handling across all M5 endpoints. |
| **3.2** | `Unit Testing` | Write unit tests focused heavily on edge cases: attempts to create sessions with invalid ratings (0 or 6), non-existent side inputs, and boundary conditions for pagination. | All previous tasks | Test suite proving the robustness of session creation and retrieval logic. |

---
### Summary of Logic Flow (M5 Focus)

The process is straightforward but rigorous:

**`Client POST /sessions` $\to$ `Validation Layer` $\to$ [IF Fails] $\to$ `Error Response` $\to$ [IF Passes] $\to$ `Release/Side Validation` $\to$ `Sessions Service` $\to$ `DB Persistence (INSERT)` $\to$ `Success Response`**
