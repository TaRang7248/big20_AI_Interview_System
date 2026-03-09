"""
Phase 4 Slice 3: Audit Wiring Service
======================================

Observation Checkpoints (6):
  OB-1: SESSION_CREATED      — wired in create_session()
  OB-2: TURN_SUBMITTED       — wired in submit_answer() / submit_chat()
  OB-3: EVALUATION_STARTED   — wired before evaluation engine call
  OB-4: EVALUATION_COMPLETED — wired after evaluation engine call
  OB-5: SESSION_ABORTED      — wired in abort_session()
  OB-6: DECISION_MADE        — wired in record_decision() (DB unique constraint guards idempotency)

CONTRACTS:
- All events are appended via AuditTimelineRepository (Append-Only PG).
- This service NEVER modifies existing audit records.
- Failures in audit wiring MUST NOT block the main request (fire-and-forget style).
- trace_id is mandatory for all events and links Audit to Stats aggregation.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from packages.imh_stats.audit_timeline import AuditEventType, AuditTimelineRepository

logger = logging.getLogger("imh.service.audit_wiring")


def _get_conn_config() -> dict:
    """Resolve DB connection config from IMHConfig."""
    import re
    from packages.imh_core.config import IMHConfig
    cfg = IMHConfig.load()
    cs = cfg.POSTGRES_CONNECTION_STRING or ""
    m = re.match(r"postgresql(?:\+asyncpg)?://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", cs)
    if m:
        u, p, h, port, db = m.groups()
        return dict(host=h, port=int(port), user=u, password=p, database=db)
    raise RuntimeError("POSTGRES_CONNECTION_STRING not configured")


class AuditWiringService:
    """
    Audit event publisher for session lifecycle checkpoints.

    This service is injected into SessionService (or called directly from the API layer).
    All methods are fire-and-forget: they schedule background tasks and do NOT raise
    to the caller on failure.
    """

    def __init__(self):
        try:
            conn_config = _get_conn_config()
            self._repo = AuditTimelineRepository(conn_config)
        except Exception as exc:
            logger.warning("[Audit Wiring] Failed to initialize AuditTimelineRepository: %s", exc)
            self._repo = None

    def _fire(self, coro):
        """Schedule coroutine without blocking caller. Swallows errors silently."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(coro)
            else:
                loop.run_until_complete(coro)
        except Exception as exc:
            logger.warning("[Audit Wiring] fire-and-forget scheduling failed: %s", exc)

    async def _safe_append(self, **kwargs):
        if self._repo is None:
            return
        try:
            await self._repo.append_event(**kwargs)
        except Exception as exc:
            logger.warning("[Audit Wiring] append_event failed silently: %s", exc)

    # --- OB-1: Session Created --------------------------------------------
    def on_session_created(self, session_id: str, trace_id: str, actor_id: Optional[str] = None):
        """OB-1: Fired when a new interview session is created."""
        self._fire(self._safe_append(
            session_id=session_id,
            event_type=AuditEventType.SESSION_CREATED,
            trace_id=trace_id,
            actor_id=actor_id,
            payload={"session_id": session_id},
        ))

    # --- OB-2: Turn Submitted ---------------------------------------------
    def on_turn_submitted(
        self, session_id: str, trace_id: str, turn_index: int, actor_id: Optional[str] = None
    ):
        """OB-2: Fired when a candidate submits an answer (one per turn)."""
        self._fire(self._safe_append(
            session_id=session_id,
            event_type=AuditEventType.TURN_SUBMITTED,
            trace_id=trace_id,
            actor_id=actor_id,
            payload={"turn_index": turn_index},
        ))

    # --- OB-3: Evaluation Started -----------------------------------------
    def on_evaluation_started(self, session_id: str, trace_id: str):
        """OB-3: Fired just before the evaluation engine processes the session."""
        self._fire(self._safe_append(
            session_id=session_id,
            event_type=AuditEventType.EVALUATION_STARTED,
            trace_id=trace_id,
        ))

    # --- OB-4: Evaluation Completed ---------------------------------------
    def on_evaluation_completed(
        self, session_id: str, trace_id: str, evaluation_input_hash: Optional[str] = None
    ):
        """OB-4: Fired after evaluation engine writes scores to PG."""
        self._fire(self._safe_append(
            session_id=session_id,
            event_type=AuditEventType.EVALUATION_COMPLETED,
            trace_id=trace_id,
            payload={"evaluation_input_hash": evaluation_input_hash},
        ))

    # --- OB-5: Session Aborted -------------------------------------------
    def on_session_aborted(
        self, session_id: str, trace_id: str, abort_reason: str, actor_id: Optional[str] = None
    ):
        """OB-5: Fired when session transitions to ABORTED terminal state."""
        self._fire(self._safe_append(
            session_id=session_id,
            event_type=AuditEventType.SESSION_ABORTED,
            trace_id=trace_id,
            actor_id=actor_id,
            payload={"abort_reason": abort_reason},
        ))

    # --- OB-6: Decision Made ---------------------------------------------
    def on_decision_made(
        self,
        session_id: str,
        trace_id: str,
        decision: str,  # "PASS" or "FAIL"
        actor_id: Optional[str] = None,
        job_id: Optional[str] = None,
    ):
        """
        OB-6: Fired when admin records a hiring decision (PASS/FAIL).
        The DB Unique Constraint (session_id, event_type='DECISION_MADE') ensures
        exactly one DECISION_MADE per session. Duplicate calls return False (idempotent).
        """
        self._fire(self._safe_append(
            session_id=session_id,
            event_type=AuditEventType.DECISION_MADE,
            trace_id=trace_id,
            actor_id=actor_id,
            payload={"decision": decision, "job_id": job_id},
        ))

    def on_decision_overridden(
        self,
        session_id: str,
        trace_id: str,
        new_decision: str,
        previous_decision: str,
        actor_id: Optional[str] = None,
    ):
        """OB-6b: Fired when an existing decision is overridden. Triggers stats rebuild."""
        self._fire(self._safe_append(
            session_id=session_id,
            event_type=AuditEventType.DECISION_OVERRIDDEN,
            trace_id=trace_id,
            actor_id=actor_id,
            payload={"new_decision": new_decision, "previous_decision": previous_decision},
        ))
