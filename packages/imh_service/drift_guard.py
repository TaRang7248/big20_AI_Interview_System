"""
Phase 4 Slice 4: Drift Guard — Late Mutation Guard + Decision Override
======================================================================

CONTRACTS (LOCKED):
  - Late Mutation Guard: Any attempt to modify a DECIDED session returns 409.
    Error: HTTP 409 + X-Error-Code: E_LATE_MUTATION_FORBIDDEN + X-Trace-Id
  - Blocked Fields: decision, evaluation_policy, decided_at, status (after DECIDED)
  - Decision Override: Appends DECISION_OVERRIDDEN audit event (Append-Only).
    Override never modifies existing DECISION_MADE event.
  - Override Idempotency: Same trace_id re-request → duplicate blocked at DB level
    (uq_override_per_trace partial unique index).
  - Post-override: Triggers granular cache invalidation for job_id bucket.
"""

import logging
import re
from datetime import datetime
from typing import Optional

import asyncpg  # type: ignore

from packages.imh_stats.audit_timeline import AuditEventType, AuditTimelineRepository
from packages.imh_stats.aggregator import GranularStatsCache

logger = logging.getLogger("imh.service.drift_guard")

# Fields that must not change after status = 'DECIDED'
LATE_MUTATION_BLOCKED_FIELDS = frozenset([
    "decision",
    "evaluation_policy",
    "decided_at",
    "status",
    "interview_mode",
])


def _get_conn_config() -> dict:
    from packages.imh_core.config import IMHConfig
    cfg = IMHConfig.load()
    cs = cfg.POSTGRES_CONNECTION_STRING or ""
    m = re.match(r"postgresql(?:\+asyncpg)?://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", cs)
    if m:
        u, p, h, port, db = m.groups()
        return dict(host=h, port=int(port), user=u, password=p, database=db)
    raise RuntimeError("POSTGRES_CONNECTION_STRING not configured")


# ---------------------------------------------------------------------------
# Late Mutation Guard
# ---------------------------------------------------------------------------

async def check_late_mutation_forbidden(session_id: str) -> Optional[dict]:
    """
    Returns an error dict if session is DECIDED (mutation forbidden).
    Returns None if mutation is allowed.

    Error contract:
      - HTTP 409
      - X-Error-Code: E_LATE_MUTATION_FORBIDDEN
      - X-Trace-Id: must be added by the caller
    """
    conn = await asyncpg.connect(**_get_conn_config())
    try:
        row = await conn.fetchrow(
            "SELECT status, decided_at FROM interviews WHERE session_id = $1",
            session_id,
        )
        if not row:
            return None  # Let 404 handler deal with missing session

        if row["status"] == "DECIDED":
            decided_ts = row["decided_at"].isoformat() if row["decided_at"] else "unknown"
            return {
                "error_code": "E_LATE_MUTATION_FORBIDDEN",
                "detail": f"Session is DECIDED as of {decided_ts}. "
                           "Modifications to decided sessions are permanently forbidden.",
                "decided_at": decided_ts,
            }
        return None
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Decision Override Service
# ---------------------------------------------------------------------------

class DecisionOverrideService:
    """
    Handles the Decision Override flow.

    Policy:
      1. Original DECISION_MADE is NEVER modified.
      2. A DECISION_OVERRIDDEN event is appended (Append-Only).
      3. Idempotency is enforced by a partial unique DB index on (session_id, trace_id)
         for DECISION_OVERRIDDEN events. Duplicate trace_id returns False (no-op).
      4. After a successful override, the stats cache for the job is invalidated
         (granular: job_id scope).
    """

    def __init__(self):
        try:
            self._audit_repo = AuditTimelineRepository(_get_conn_config())
        except Exception as exc:
            logger.warning("[Override] AuditTimelineRepository init failed: %s", exc)
            self._audit_repo = None
        self._cache = GranularStatsCache()

    async def apply_override(
        self,
        *,
        session_id: str,
        trace_id: str,
        new_decision: str,
        actor_id: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> dict:
        """
        Apply a decision override.

        Returns:
          {"status": "appended", ...}   — first successful call
          {"status": "duplicate", ...}  — same trace_id re-request (no-op)
          {"status": "error", ...}      — unexpected failure
        """
        if self._audit_repo is None:
            return {"status": "error", "reason": "Audit repository unavailable"}

        # 1. Get current DECISION_MADE to record previous_decision
        current = await self._audit_repo.get_decision_event(session_id)
        previous_decision = (
            (current.get("payload") or {}).get("decision", "UNKNOWN")
            if current else "UNKNOWN"
        )

        # 2. Attempt to append DECISION_OVERRIDDEN (idempotency via DB unique index)
        conn = await asyncpg.connect(**_get_conn_config())
        try:
            import json
            result = await conn.execute(
                """
                INSERT INTO session_audit_events
                    (session_id, event_type, trace_id, actor_id, payload, occurred_at)
                VALUES ($1, 'DECISION_OVERRIDDEN', $2, $3, $4, $5)
                ON CONFLICT ON CONSTRAINT uq_override_per_trace DO NOTHING
                """,
                session_id,
                trace_id,
                actor_id,
                json.dumps({
                    "new_decision": new_decision,
                    "previous_decision": previous_decision,
                    "job_id": job_id,
                }),
                datetime.utcnow(),
            )
        except asyncpg.UniqueViolationError:
            logger.info("[Override] Duplicate trace_id=%s for session=%s blocked.", trace_id, session_id)
            return {"status": "duplicate", "trace_id": trace_id, "session_id": session_id}
        finally:
            conn.close() if not conn.is_closed() else None

        # Check if INSERT actually inserted (rowcount=0 → ON CONFLICT hit → duplicate)
        if result == "INSERT 0 0":
            logger.info("[Override] Duplicate trace_id=%s blocked (ON CONFLICT).", trace_id)
            return {"status": "duplicate", "trace_id": trace_id, "session_id": session_id}

        logger.info(
            "[Override] DECISION_OVERRIDDEN appended session=%s trace=%s new=%s prev=%s",
            session_id, trace_id, new_decision, previous_decision,
        )

        # 3. Granular cache invalidation (job_id scope only — no global flush)
        if job_id:
            self._cache.invalidate_for_job(job_id)
            logger.info("[Override] Cache invalidated for job_id=%s", job_id)

        return {
            "status": "appended",
            "session_id": session_id,
            "trace_id": trace_id,
            "new_decision": new_decision,
            "previous_decision": previous_decision,
            "cache_invalidated": bool(job_id),
        }
