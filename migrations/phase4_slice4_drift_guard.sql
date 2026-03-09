-- =============================================================================
-- Phase 4 Slice 4: Drift Guard Migration
-- =============================================================================
-- Purpose: Create composite index for aggregate stats queries and enforce
--          DECISION_MADE uniqueness constraint on the audit timeline table.
--
-- CONTRACTS:
--   (1) Index (status, evaluation_policy, decided_at) prevents Full-table scan.
--   (2) Partial unique index on session_audit_events ensures at most 1
--       DECISION_MADE per session_id (idempotency at DB level).
--   (3) All DDL is idempotent (IF NOT EXISTS / ON CONFLICT DO NOTHING safe).
--
-- Run order: This migration MUST run after session_audit_events table exists.
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Composite Index for Aggregate Stats (Phase 4 Slice 1)
--    Covers: status='DECIDED' + evaluation_policy='EVALUATIVE' + decided_at range
--    Purpose: Eliminate Full-table scan on aggregate queries.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_interviews_stats_composite
    ON interviews (status, evaluation_policy, decided_at)
    WHERE status = 'DECIDED';

-- Explain verification: After applying, queries with WHERE status='DECIDED'
-- AND evaluation_policy='EVALUATIVE' should use Index Scan on this index.

-- ---------------------------------------------------------------------------
-- 2. DECISION_MADE Unique Constraint (Phase 4 Slice 3 / Slice 4)
--    Partial unique index: one DECISION_MADE event per session.
--    DECISION_OVERRIDDEN is unlimited (no constraint).
-- ---------------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS uq_decision_made_per_session
    ON session_audit_events (session_id)
    WHERE event_type = 'DECISION_MADE';

-- ---------------------------------------------------------------------------
-- 3. Performance Index on Audit Timeline
--    Covers lookups: WHERE session_id = $1 ORDER BY occurred_at ASC
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_audit_session_occurred
    ON session_audit_events (session_id, occurred_at DESC);

-- ---------------------------------------------------------------------------
-- 4. Override Idempotency Index (Slice 4)
--    Partial unique index on (session_id, trace_id) for DECISION_OVERRIDDEN
--    to prevent duplicate override events from the same trace_id.
-- ---------------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS uq_override_per_trace
    ON session_audit_events (session_id, trace_id)
    WHERE event_type = 'DECISION_OVERRIDDEN';

-- ---------------------------------------------------------------------------
-- 5. decided_at column: ensure it exists and has a NOT NULL guard post-DECIDED
--    (This is a soft guard; hard enforcement done at application level)
-- ---------------------------------------------------------------------------
-- Note: decided_at column is expected to already exist in the interviews table.
-- If not, uncomment and apply:
-- ALTER TABLE interviews ADD COLUMN IF NOT EXISTS decided_at TIMESTAMPTZ;

COMMIT;
