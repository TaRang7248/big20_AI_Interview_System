# TASK-028 CP1 Plan: Operational Observability & Heavy Query Isolation

This document outlines the plan for **TASK-028 CP1**, focusing on **Track B: Operational Observability** and strategies for **Heavy Query Isolation (Type 3/4)**.

---\n\n## 1. Goal & Scope (CP1)\n\n### Goal
Establish a **Query-Only Observability Layer** to monitor system health and performance without impacting business logic or data integrity.
Ensure strictly consistent "Read-Only" behavior for heavy analytical queries.

### Scope (Track B: Operational Observability)
- **Layer**: `packages/imh_stats` (extension).
- **Metrics** (Informational Only):
  - **Latency**: Average response time per phase (Span).
  - **Failure Rates**: LLM/RAG/State Transition failures (Reason).
  - **Cache Stats**: Redis Hit/Miss rates (System health).
- **Contracts**:
  - **Source**: Logs (Aggregated) & PG Failure Events.
  - **Role**: Informational (Trends). **NEVER** used for Business Logic/Grading.

### Scope (Heavy Query Isolation)
- **Type 3 (Multi-dimensional)**:
  - **MView**: Allowed for statistical aggregation.
  - **Summary Table**: Optional. If used, must be a strictly separated Read Model.
- **Type 4 (Correlation/Anomaly)**:
  - **Execution**: API Real-time Execution **BANNED**.
  - **Storage**: No persistent storage in CP1. Default state **DISABLED**.
- **Isolation**: Heavy queries must not compete with OLTP (Session/Eval) resources.

### Out of Scope (Strict)
- **Business Stats (Track A)**: Already CP0. No changes permitted.
- **Command/Engine Logic**: No modification to `SessionEngine` or State Transitions.
- **Snapshot/Freeze**: No re-evaluation or modification.
- **Redis Authority**: Redis remains Cache-Only. No Write-Back.
- **New Write Paths**: No new persistent storage (e.g., TimeSeries DB).
- **Schema Changes**: No changes to CORE tables (`sessions`, `interviews`, `evaluations`). MViews are allowed.

---\n\n## 2. Data Source & Trust Level Contracts\n\n| Track | Metric Type | Data Source | Trust Level | Usage Constraint |
|:---:|:---:|:---|:---:|:---|
| **A** | Business Stats | **PostgreSQL Snapshot** | **Authoritative** (100%) | Decision Making (Pass/Fail) |
| **B** | Observability | **Logs / Failure Events** | **Informational** (Trend) | Monitoring / Debugging Only |

### Critical Clauses
1.  **Informational Only**: Track B metrics are for reference only. They must **never** be mixed with Track A data to derive business insights.
2.  **No Mixed aggregation**: `JOIN` between Log-derived data and PG Snapshot data is **PROHIBITED** in Business Logic.
3.  **State Transition Failures**: Must be derived ONLY from:
    - Existing `error` logs.
    - Existing PostgreSQL `status='FAILED'` records (if any).
    - **PROHIBITED**: Adding new counters/tables inside `SessionEngine` to track failures.

---\n\n## 3. Observability Meta Model (Reason / Span / Layer)\n\nAll observability metrics must be decomposable using this model (Slice & Dice).

### 3.1 Reason Codes (Why it happened)
- `LLM_TIMEOUT`: LLM provider did not respond in time.
- `RAG_EMPTY`: Retrieval returned no context.
- `PROVIDER_ERROR`: External API 5xx/4xx.
- `FACE_NOT_DETECTED`: Vision analysis failed to find face.
- `AUDIO_SILENCE`: Audio input level too low.
- `SYSTEM_ERROR`: Internal unhandled exception.

### 3.2 Spans (Where in time it happened)
- **Scope**: Limited to currently implemented pipelines. Unimplemented features (e.g., TTS) are **Reserved**.
- `STT_PROCESSING`: Speech-to-Text conversion phase.
- `RAG_RETRIEVAL`: Vector DB search phase.
- `LLM_GENERATION`: Text generation phase.
- `EVAL_SCORING`: Evaluation logic execution phase.
- `TOTAL_SESSION`: End-to-end session duration.
- `TTS_SYNTHESIS` (Reserved): Currently logic-only or excluded from CP1.

### 3.3 Layers (Where in stack it happened)
- `API`: HTTP Entrance/Exit.
- `SERVICE`: Business Logic orchestration.
- `PROVIDER`: External Service Adapter.
- `DB`: PostgreSQL Persistence.
- `CACHE`: Redis Caching.

**Standard Visualization Strategy**:
- Latency = `AVG(duration) GROUP BY Span, Layer`
- Failure Rate = `COUNT(Reason) / TOTAL_OPS GROUP BY Layer`

---\n\n## 4. Heavy Query Isolation Strategy\n\n### Type 3: Multi-dimensional Analysis
- **Strategy**: **Materialized View (MView)** or **Summary Table**.
- **Update Policy**: Batch Update (e.g., every 1 hour or overnight).
- **Real-time access**: **BANNED**. Must query the MView/Summary.
- **Write-Back**: **PROHIBITED**. Summary tables are Read Models, not Domain Models.
- **Summary Table Conditions (Optional)**:
  1) Must be a **Read Model** completely separated from the Domain Model.
  2) **No Write-Back** to source tables.
  3) Business Logic must **never** treat it as Authority.
  4) Adoption to be decided during implementation.

### Type 4: Correlation & Anomaly Detection
- **Strategy**: **Offline / Background Job Only**.
- **API Access**: **BANNED**. No API endpoint shall trigger a Type 4 query synchronously.
- **Output**:
  - **No Persistent Storage** in CP1.
  - Results may be logged (Informational) but not stored in DB.
- **Default State**: **DISABLED**. Features are hidden/inactive by default.
- **Future**: TimeSeries DB integration in later phases.

---\n\n## 5. Redis Strategy for Observability\n\n- **Role**: **Result Cache Only**.
- **Content**: Aggregated metrics (e.g., "Avg Latency last 1h").
- **TTL Constraint**:
  - Real-time monitoring: Short TTL (e.g., 10s - 1m).
  - Historical trends: Long TTL (e.g., 1h - 24h).
- **Metadata Requirement**:
  - Responses must include `as_of`, `is_cached`, and `ttl_remaining`.
  - Consumers must be aware that data might be stale (Eventual Consistency).

---

## 6. Verification Gates (CP1)

Approval conditions for CP1 Implementation:
- [ ] **Data Source Separation**: Code proves Track B derives from Logs/Events, not Snapshots.
- [ ] **Code Level Separation**: Track A and Track B use physically separated Repositories/Services.
- [ ] **No Mixed Responses**: API does not return mixed Track A/B data in a single response.
- [ ] **Engine Integrity**: No modifications to `SessionEngine` or `Command` classes found.
- [ ] **Type 4 Isolation**: Type 4 features are **DISABLED** and have no persistent storage.
- [ ] **Summary Table Compliance**: If used, meets Read-Model-Only and No-Write-Back conditions.
- [ ] **Span Scope**: Implemented Spans match the active pipeline (excluding Reserved).
- [ ] **Redis Usage**: Redis is used strictly as a cache (setex), not as a primary store.
- [ ] **Write Path**: No new persistent write paths (files/DB) created for metrics.
