"""
Phase 4 Slice 3: Admin Audit Timeline (Append-Only PG Source)
=============================================================

CONTRACTS (LOCKED):
- Source: PostgreSQL append-only table `session_audit_events`.
- Immutability: Rows are INSERT-only. UPDATE/DELETE are structurally impossible by policy.
- Event Enum: Values below are the canonical set. Extend by adding; never rename/remove.
- DECISION_MADE uniqueness: DB Unique Constraint on (session_id) for DECISION_MADE events.
- trace_id links Audit events to Stats aggregation records.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg  # type: ignore

logger = logging.getLogger("imh.stats.audit_timeline")


# ---------------------------------------------------------------------------
# Event Type Enum (Locked set – extend only, never rename)
# ---------------------------------------------------------------------------
class AuditEventType:
    SESSION_CREATED       = "SESSION_CREATED"
    CAMERA_CHECKED        = "CAMERA_CHECKED"
    WEBRTC_CONNECTED      = "WEBRTC_CONNECTED"
    TURN_SUBMITTED        = "TURN_SUBMITTED"
    EVALUATION_STARTED    = "EVALUATION_STARTED"
    EVALUATION_COMPLETED  = "EVALUATION_COMPLETED"
    SESSION_ABORTED       = "SESSION_ABORTED"
    DECISION_MADE         = "DECISION_MADE"
    DECISION_OVERRIDDEN   = "DECISION_OVERRIDDEN"

    _ALL = frozenset([
        SESSION_CREATED, CAMERA_CHECKED, WEBRTC_CONNECTED, TURN_SUBMITTED,
        EVALUATION_STARTED, EVALUATION_COMPLETED, SESSION_ABORTED,
        DECISION_MADE, DECISION_OVERRIDDEN,
    ])

    @classmethod
    def is_valid(cls, event_type: str) -> bool:
        return event_type in cls._ALL


# Table DDL (idempotent – run once on startup or migration)
CREATE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS session_audit_events (
    id              BIGSERIAL PRIMARY KEY,
    session_id      TEXT        NOT NULL,
    event_type      TEXT        NOT NULL,
    trace_id        TEXT        NOT NULL,
    actor_id        TEXT,
    payload         JSONB,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

# Unique constraint: one DECISION_MADE per session
DECISION_UNIQUE_DDL = """
CREATE UNIQUE INDEX IF NOT EXISTS uq_decision_made_per_session
    ON session_audit_events (session_id)
    WHERE event_type = 'DECISION_MADE';
"""

# Index for fast timeline lookups
TIMELINE_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS idx_audit_session_occurred
    ON session_audit_events (session_id, occurred_at DESC);
"""


class AuditTimelineRepository:
    """
    Append-Only Audit Timeline Repository.

    All writes use INSERT. No UPDATE or DELETE paths exist.
    DECISION_MADE uniqueness is enforced by a partial unique index.
    """

    def __init__(self, conn_config: dict):
        self.conn_config = conn_config

    async def _get_connection(self):
        return await asyncpg.connect(**self.conn_config)

    async def ensure_schema(self):
        """Create tables and indexes (idempotent)."""
        conn = await self._get_connection()
        try:
            await conn.execute(CREATE_TABLE_DDL)
            await conn.execute(DECISION_UNIQUE_DDL)
            await conn.execute(TIMELINE_INDEX_DDL)
            logger.info("[P4 Audit] Schema ensured (session_audit_events).")
        finally:
            await conn.close()

    async def append_event(
        self,
        *,
        session_id: str,
        event_type: str,
        trace_id: str,
        actor_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        occurred_at: Optional[datetime] = None,
    ) -> bool:
        """
        Append a new audit event. Returns True on success.

        For DECISION_MADE: if a duplicate already exists, returns False (idempotent).
        For DECISION_OVERRIDDEN: always appended (no uniqueness constraint).
        """
        if not AuditEventType.is_valid(event_type):
            logger.error("[P4 Audit] Unknown event_type=%s", event_type)
            return False

        conn = await self._get_connection()
        try:
            at = occurred_at or datetime.utcnow()
            await conn.execute(
                """
                INSERT INTO session_audit_events
                    (session_id, event_type, trace_id, actor_id, payload, occurred_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT DO NOTHING
                """,
                session_id,
                event_type,
                trace_id,
                actor_id,
                json.dumps(payload) if payload else None,
                at,
            )
            logger.info(
                "[P4 Audit] event=%s session=%s trace=%s",
                event_type, session_id, trace_id,
            )
            return True
        except asyncpg.UniqueViolationError:
            logger.warning(
                "[P4 Audit] Duplicate DECISION_MADE blocked for session=%s", session_id
            )
            return False
        except Exception as exc:
            logger.error("[P4 Audit] append_event failed: %s", exc)
            return False
        finally:
            await conn.close()

    async def get_timeline(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Return the full audit timeline for a session, ordered chronologically.
        trace_id links each event to the stats aggregation record.
        """
        conn = await self._get_connection()
        try:
            rows = await conn.fetch(
                """
                SELECT id, session_id, event_type, trace_id, actor_id, payload, occurred_at
                FROM session_audit_events
                WHERE session_id = $1
                ORDER BY occurred_at ASC
                LIMIT $2
                """,
                session_id,
                limit,
            )
            return [
                {
                    "id": r["id"],
                    "session_id": r["session_id"],
                    "event_type": r["event_type"],
                    "trace_id": r["trace_id"],
                    "actor_id": r["actor_id"],
                    "payload": json.loads(r["payload"]) if r["payload"] else None,
                    "occurred_at": r["occurred_at"].isoformat() if r["occurred_at"] else None,
                }
                for r in rows
            ]
        finally:
            await conn.close()

    async def get_decision_event(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Returns the single DECISION_MADE event for a session, or None.
        Used for cross-consistency checks against stats aggregation.
        """
        conn = await self._get_connection()
        try:
            row = await conn.fetchrow(
                """
                SELECT trace_id, occurred_at, payload
                FROM session_audit_events
                WHERE session_id = $1 AND event_type = 'DECISION_MADE'
                LIMIT 1
                """,
                session_id,
            )
            if not row:
                return None
            return {
                "trace_id": row["trace_id"],
                "occurred_at": row["occurred_at"].isoformat() if row["occurred_at"] else None,
                "payload": json.loads(row["payload"]) if row["payload"] else None,
            }
        finally:
            await conn.close()

    async def count_decisions(
        self, job_id: str, decision: str, month_bucket: Optional[str] = None
    ) -> int:
        """
        Cross-consistency check: count DECISION_MADE events by decision type.
        Used to validate against stats aggregation (pass_count/fail_count must match).
        """
        conn = await self._get_connection()
        try:
            args: List[Any] = [decision]
            where_clauses = [
                "sae.event_type = 'DECISION_MADE'",
                f"sae.payload->>'decision' = $1",
                "i.job_id = $2",
                "i.evaluation_policy = 'EVALUATIVE'",
                "i.status = 'DECIDED'",
            ]
            args.append(job_id)

            if month_bucket:
                args.append(month_bucket)
                where_clauses.append(
                    f"TO_CHAR(sae.occurred_at AT TIME ZONE 'UTC', 'YYYY-MM') = ${len(args)}"
                )

            where = " AND ".join(where_clauses)
            row = await conn.fetchrow(
                f"""
                SELECT COUNT(*) AS cnt
                FROM session_audit_events sae
                JOIN interviews i ON i.id::TEXT = sae.session_id
                WHERE {where}
                """,
                *args,
            )
            return int(row["cnt"] or 0)
        finally:
            await conn.close()
