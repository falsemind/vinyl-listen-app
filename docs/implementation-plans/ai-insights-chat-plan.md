# Implementation Plan: AI Insights Chat

## Goal

Add an `AI Insights` bottom-navigation screen to the Android app where a user can chat with an assistant about listening habits, collection patterns, moods, styles, ratings, and record history.

The first version should validate the product and architecture shape without overcommitting to a deep agent platform. It should keep Android simple, put AI orchestration behind backend-owned APIs, and allow later experimentation with LangChain/LangGraph, persistent chat history, and richer tools.

## Product Decisions

- User model: single-user and local-first for now.
- Deployment assumption: backend may later run in a cloud environment for testing and experimentation, so AI provider configuration must not assume localhost-only runtime.
- Recommendation scope: recommend only releases already known to the app.
- Privacy: chat history is sensitive user data and needs clear/delete and export support from the first persistent-history phase.
- First success target: architectural proof that the agent can answer real analytics and listening-history questions.
- Initial model provider direction: use a ChatOpenAI-compatible adapter, with LM Studio as the likely first local model runtime.
- Android bottom navigation label: `Insights`.
- Initial chat scope: single chat thread only.
- Product vocabulary: use `style` rather than `genre` for collection categories exposed by current backend analytics.
- Spotify export direction: use local Spotify listening-history exports as an optional future insight source, starting with SQL analytics and deterministic matching rather than embeddings/RAG.

## Current Context

- Android navigation already has bottom-nav-oriented routes for `Home`, `Analytics`, and `Settings`.
- A product mockup exists at `docs/product/app-screens-mockups/AIInsightsScreen.tsx`.
- Backend analytics APIs already expose structured listening data:
  - monthly plays
  - top records
  - rating distribution
  - mood distribution
  - style distribution
- Spotify extended streaming-history exports can add multi-year listening signals that overlap with the local vinyl collection by artist, album, and track names.
- Backend services already follow a route -> service -> repository boundary.
- Existing docs expect new backend workflows to update API, schema, feature, repository-structure, navigation, and product screen documentation together.

## Product Requirements

### MVP

- Add `Insights` as a bottom nav destination.
- Show a chat-style screen with:
  - message list
  - text input
  - send action
  - loading/streaming state
  - error + retry state
  - empty state with a few suggested prompts
  - optional record recommendation cards when an answer references specific records
- Let users ask questions such as:
  - "What have I listened to most this month?"
  - "What moods do I play most often?"
  - "Recommend something from my collection for a quiet evening."
  - "What styles have I been neglecting?"
- Persist chat history at least per device/user profile once backend persistence is introduced.
- Keep assistant answers grounded in app data and avoid pretending to know unavailable data.

### Not MVP

- Multi-user auth-aware personalization unless auth exists.
- Cross-device chat sync unless backend sessions are persisted and user identity is available.
- Autonomous background agents.
- Write actions such as creating listening sessions from chat.
- Recommendations outside the user's known collection.
- Vector/RAG indexing of the whole collection unless simple SQL-backed tools are insufficient.
- Embedding or RAG pipelines for Spotify history in the first Spotify integration slice.
- Live Spotify API sync, playlist semantics, artist alias resolution, podcast/episode analysis, or recommendations for music outside the known app collection.
- Fine-tuning.

## Architecture Recommendation

Use a separate backend-facing AI boundary, not direct Android-to-LLM calls.

```text
Android AI Insights Screen
        |
        | POST /api/v1/ai/chat
        v
FastAPI AI Routes
        |
        v
AI Insights Service
        |
        +--> Chat Session Repository
        +--> Analytics / Sessions / Releases Repositories
        +--> Agent Runtime Adapter
                 |
                 +--> LangChain agent or LangGraph graph
                 +--> Model provider
```

This keeps provider keys off-device, gives the backend control over rate limits and data access, and lets the Android screen remain a normal API client feature.

Because the app is single-user/local-first, the first backend contract does not need account ownership fields. If the backend is deployed to the cloud for experiments, provider URLs, model names, and API keys should be environment-driven so the same service can point either at local LM Studio or a hosted OpenAI-compatible endpoint.

## AI Runtime Shape

Start with a small adapter interface and one experimental implementation.

```text
AiInsightsAgent
  answer(message, conversation_id, context) -> AiAssistantReply
```

The first real AI implementation should target a ChatOpenAI-compatible client so LM Studio can run local model weights during development. The adapter should keep `base_url`, `api_key`, `model`, timeout, and temperature in backend settings. That leaves room to point the same code at a hosted provider later.

Use a stub adapter first only if Android/API wiring needs to be proven before the model runtime is ready. Otherwise, the architectural proof should move quickly to a LangChain agent with read-only collection tools. Move to a LangGraph graph when the workflow needs explicit state transitions, durable execution, resumability, human approval, or more complex tool routing. Official LangChain docs position LangChain agents as the higher-level starting point and LangGraph as the lower-level stateful orchestration layer with persistence and durable execution.

### Suggested Agent Tools

- `get_recent_sessions(limit, since)`
- `get_top_records(limit, range)`
- `get_mood_distribution(range)`
- `get_style_distribution(range)`
- `get_rating_distribution(range)`
- `search_collection(query)`
- `get_release_detail(release_id)`

Future Spotify-backed tools should keep the same narrow, read-only shape:

- `get_spotify_vinyl_overlap_summary(range)`
- `get_spotify_listening_time_patterns(range)`
- `get_spotify_top_artists_by_period(range)`
- `get_spotify_collection_recommendation_signals(range)`

For MVP, these should be deterministic backend functions with narrow schemas. The agent should not receive raw unrestricted database access.

Recommendation tools must only return known releases from the local app database. If the user asks for outside recommendations, the assistant should say it can currently recommend from the user's collection and offer collection-based alternatives. Spotify data may influence ranking and explanation, but it must not expand the recommendation universe.

## Persistence Options

### Phase 1: Stateless Backend, Local UI State

- Android stores in-memory messages only.
- Backend receives current message plus recent client-sent transcript.
- Cheapest for screen prototyping.
- Not enough for real memory.

### Phase 2: Backend Chat Sessions

Add tables:

- `ai_chat_sessions`
  - `id`
  - `created_at`
  - `updated_at`
  - optional `title`
- `ai_chat_messages`
  - `id`
  - `session_id`
  - `role`
  - `content`
  - `created_at`
  - optional `metadata_json`

This is the recommended first persistent memory layer.

Because chat history is private, this phase must also include:

- clear/delete chat history
- export chat history
- product copy that makes clear the assistant uses listening and collection data

### Phase 3: Agent Memory / Summaries

Add conversation summaries or profile-level memory only after chat history proves useful. Keep this separate from raw message history so it can be regenerated or deleted.

## API Contract Draft

### `POST /api/v1/ai/chat`

Request:

```json
{
  "conversation_id": "optional-existing-session-id",
  "message": "What styles have I played most lately?",
  "client_context": {
    "timezone": "America/Los_Angeles"
  }
}
```

Response:

```json
{
  "conversation_id": "session-id",
  "message": {
    "role": "assistant",
    "content": "Your recent sessions lean heavily toward..."
  },
  "used_tools": [
    "get_style_distribution"
  ]
}
```

### Future Streaming

Use Server-Sent Events or chunked streaming only after the basic request/response flow works. Streaming improves feel but adds Android state and retry complexity.

## Android Implementation Shape

- Add `VinylRoutes.AI_INSIGHTS`.
- Add bottom nav item label `Insights`.
- Add `AiInsightsScreen.kt`.
- Add an API client method for chat.
- Use `docs/product/app-screens-mockups/AIInsightsScreen.tsx` as the initial UI reference.
- Model UI state as:
  - `Idle`
  - `Sending`
  - `ResponseReceived`
  - `Error`
- Use conservative Compose components matching the existing dark design system.
- Suggested prompts should be real buttons that submit text, not explanatory copy.
- Keep Phase 1 to one chat thread. Do not add a conversation list or history browser yet.
- Resolve mockup wording before implementation: use "style" consistently rather than "genre".

## Backend Implementation Shape

- Add `backend/app/api/routes/ai.py`.
- Add schemas under `backend/app/schemas/ai.py`.
- Add `backend/app/services/ai_insights_service.py`.
- Add `backend/app/ai/` for runtime adapter code.
- Add repositories/migrations only when persistent sessions are introduced.
- Register route under `/api/v1/ai`.
- Reuse analytics/session/release services rather than duplicating SQL.

## Complexity Estimate

| Slice | Complexity | Notes |
| --- | --- | --- |
| Static Android screen + bottom nav | Small | Mostly Compose/navigation work. |
| Non-streaming chat API shell | Small-Medium | Basic route/service/schema with stub response. |
| LLM-backed response | Medium | Provider config, secrets, tests, error handling. |
| Tool-grounded listening insights | Medium-Large | Requires careful tool schemas and answer grounding. |
| Persistent chat sessions | Medium | Migration, repositories, API contract, history loading. |
| Spotify listening-history import | Medium-Large | Import validation, dedupe, privacy filtering, indexes, and summary tables. |
| Spotify-to-vinyl matching tools | Medium-Large | Requires normalized names, deterministic confidence rules, and explainable collection-only recommendation signals. |
| Streaming responses | Medium-Large | Backend streaming plus Android incremental rendering. |
| LangGraph durable agent | Large | Useful later, likely too much for first experiment. |

## Phased Plan

### Phase 0: Architecture Spike

| Task | Done Criteria |
| --- | --- |
| Decide service boundary | Android talks only to backend AI API. |
| Pick initial runtime | ChatOpenAI-compatible adapter chosen, with stub available as fallback if LM Studio is not ready. |
| Define tool list | Initial read-only analytics tools documented. |
| Define data policy | No direct DB access from agent; backend tools only. |
| Define recommendation scope | Agent recommendations are limited to known releases. |

### Phase 1: Android Shell

| Task | Done Criteria |
| --- | --- |
| Add route and bottom nav item | `AI Insights` is reachable from bottom nav. |
| Add chat screen | Message list, input, send button, suggested prompts, loading/error states. |
| Add mock ViewModel/state holder | Screen can be demoed without backend. |
| Update docs | Navigation and screen specs mention AI Insights. |

### Phase 2: Backend Chat API Skeleton

| Task | Done Criteria |
| --- | --- |
| Add route/schemas/service | `POST /api/v1/ai/chat` returns deterministic stub response. |
| Wire Android client | Screen sends message and renders backend reply. |
| Add tests | Route/service tests cover success and validation errors. |
| Update docs | API spec and backend services docs include AI route. |

### Phase 3: LLM Adapter Experiment

| Task | Done Criteria |
| --- | --- |
| Add provider config | API key/model settings are environment-driven. |
| Add runtime adapter | Service can call one LLM implementation behind an interface. |
| Add safe fallback | Missing provider config returns a clear disabled response. |
| Add minimal observability | Logs include latency, provider, and tool names without message content by default. |
| Validate LM Studio path | Backend can point at a local LM Studio `/api/v1/chat` endpoint through settings. |

Implemented Phase 3 adapter shape:

- `backend/app/ai/chat_adapter.py` owns disabled, LM Studio native chat, and OpenAI-compatible chat completions adapter behavior.
- `AiInsightsService` depends on the adapter boundary and keeps provider failures as safe assistant replies.
- Backend settings use `AI_CHAT_ENABLED`, `AI_CHAT_BASE_URL`, `AI_CHAT_ENDPOINT_PATH`, `AI_CHAT_MODEL`, `AI_CHAT_API_KEY`, `AI_CHAT_TIMEOUT_SECONDS`, and `AI_CHAT_TEMPERATURE`.
- The adapter keeps the current non-streaming API contract and leaves grounded analytics tools for Phase 4.

### Phase 4: Grounded Insight Tools

| Task | Done Criteria |
| --- | --- |
| Implement read-only tools | Agent can call analytics/session/release queries through service methods. |
| Add answer rules | Assistant states when data is missing or too sparse. |
| Add tests | Tool selection and response grounding are covered with deterministic tests/mocks. |

Implemented Phase 4 shape:

- `backend/app/ai/insight_tools.py` runs deterministic read-only tools before the model call.
- Tool context covers listening summary, session notes, recent sessions, top records, style distribution, mood distribution, and rating distribution.
- Session notes are treated as high-priority context for recommendations and subjective insight questions because they contain user-entered listening impressions.
- `AiInsightsService` passes tool context to the adapter and returns persisted `used_tools` names.
- Tools stay behind backend services/repositories; the model never receives direct database access.

### Phase 5: Persistent Chat History

| Task | Done Criteria |
| --- | --- |
| Add chat tables | Migration creates sessions/messages. |
| Save messages | User and assistant messages are persisted. |
| Load history | Android can resume a conversation. |
| Add delete/reset path | User can clear AI chat history. |
| Add export path | User can export AI chat history. |

Implemented Phase 5 shape:

- `ai_chat_sessions` and `ai_chat_messages` persist one local conversation thread.
- `POST /api/v1/ai/chat` stores user and assistant messages and passes recent history to the runtime adapter.
- `GET /api/v1/ai/chat/history`, `GET /api/v1/ai/chat/export`, and `DELETE /api/v1/ai/chat/history` provide load, export, and clear paths.
- Android loads persisted history when opening the Insights screen.

### Phase 6: Spotify Listening Data Integration

Goal: enrich AI Insights with local Spotify listening-history signals while keeping chat answers grounded, private, and limited to known releases in the app collection.

Starter scope:

- Import Spotify `end_song` JSON export files from backend-local file paths. Android upload is out of scope for the first slice.
- Retain useful event fields: `ts`, `ms_played`, `conn_country`, `master_metadata_track_name`, `master_metadata_album_artist_name`, `master_metadata_album_album_name`, `reason_start`, `reason_end`, `shuffle`, `skipped`, `offline`, and `offline_timestamp`.
- Skip fields for the first slice: `username`, `ip_addr_decrypted`, `user_agent_decrypted`, `incognito_mode`, `platform`, `spotify_track_uri`, and podcast/episode fields.
- Derive query-friendly fields during import: local date, local hour, weekday, year-month, normalized artist/album/track names, and a meaningful-listen flag.
- Precompute summary tables for chat tools instead of scanning raw Spotify events during every assistant request.
- Match Spotify artists/albums/tracks to known local releases offline, using exact normalized matches first and explainable confidence rules.

| Task | Effort | Done Criteria |
| --- | --- | --- |
| Audit export files | 2-4h | Sample files are validated and required starter fields are confirmed. |
| Add schema and migration | 4-8h | Raw event table, normalized fields, indexes, and dedupe key are defined. |
| Build import service | 4-8h | Import filters skipped fields, batches inserts, dedupes events, and reports counts/errors. |
| Add summary rollups | 4-8h | Artist, album, track, hourly, monthly, skip, and meaningful-listen summaries are queryable. |
| Add collection matching | 4-8h | Spotify summaries can link to known releases with confidence and match explanation. |
| Add AI tools | 4-8h | Assistant can use Spotify summaries through read-only tools with deterministic tests. |
| Update docs/API notes | 2-4h | Import contract, privacy behavior, and tool limits are documented. |

Implemented Phase 6 schema/import shape:

- `spotify_listening_import_batches` tracks backend-local import status, source paths, counts, and error summaries.
- `spotify_listening_events` stores filtered song events, normalized artist/album/track names, date buckets, meaningful-listen flag, indexes, and a unique dedupe key.
- `SpotifyListeningImportService.import_files(...)` reads local JSON exports, drops out-of-scope/private fields, batches inserts, dedupes repeated imports, and reports imported/duplicate/skipped/error counts.
- No Android upload flow, rollup tables, collection matching, or AI tools are included in this slice.

Performance approach:

- Treat raw Spotify events as import/source data, not chat-time context.
- Add indexes on normalized artist, album, track, played timestamp/date buckets, and dedupe keys.
- For the first rollup slice, refresh summary tables synchronously at the end of import so AI Insights can use the new data immediately.
- Keep assistant tools small: return ranked summaries and known-release candidates, not thousands of raw plays.

Risks and mitigations:

- Large exports can make imports slow: use streaming parse or chunked batches, plus resumable import metadata if needed.
- Matching can be noisy: start with exact normalized matches, expose confidence/explanation, and defer fuzzy aliases.
- Private data can leak into prompts: drop personal identifiers at import and pass only summaries to the AI adapter.
- Spotify signals can overpower actual vinyl behavior: combine Spotify summaries with saved sessions, ratings, and high-priority session notes.

Deferred:

- Embeddings/RAG for Spotify history.

## Open Questions

- Which specific LM Studio model should be used for the first spike?
- What minimum answer quality should count as proof that the architecture works?
- Should persistent chat history be added before or after the first real LLM adapter?
- If the backend runs in the cloud, will the model still run locally through a tunnel/VPN, or should the cloud backend point at a hosted OpenAI-compatible provider?

## Recommended Next Step

Keep the current AI Insights proof focused on deterministic backend tools. For Spotify, start with a schema/import spike and summary-table queries before adding any agent behavior. The key proof is whether Spotify listening history can produce fast, explainable collection-overlap signals that improve answers without changing the Android chat contract.
