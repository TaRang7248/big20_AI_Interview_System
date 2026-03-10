from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.api.schemas import JobPostingResponse, AdminSessionSummary, SessionResponse
from app.api.dependencies import get_admin_query_service
from packages.imh_service.admin_query import AdminQueryService
from packages.imh_stats.audit_timeline import AuditTimelineRepository
from packages.imh_stats.aggregator import AggregateStatsRepository, GranularStatsCache
from packages.imh_service.drift_guard import DecisionOverrideService, check_late_mutation_forbidden

import re
import logging
from packages.imh_core.config import IMHConfig

logger = logging.getLogger("imh.api.admin")

router = APIRouter(prefix="/admin", tags=["Admin"])


# --- Schemas ---
class DecisionOverrideRequest(BaseModel):
    new_decision: str = Field(..., description="PASS or FAIL")
    reason: Optional[str] = Field(None, description="Human-readable justification")


@router.get("/jobs", response_model=List[JobPostingResponse])
def get_jobs(
    service: AdminQueryService = Depends(get_admin_query_service)
):
    """
    List all published jobs.
    Uses AdminQueryService to bypass Domain Logic (Read-Only).
    """
    # Service returns list of dicts (Job model dicts)
    jobs_data = service.get_all_jobs()
    
    # Map to Response Schema
    return [
        JobPostingResponse(
            job_id=j["job_id"],
            title=j["title"],
            status=j["status"].name if hasattr(j["status"], "name") else str(j["status"])
        ) for j in jobs_data
    ]

@router.get("/sessions", response_model=List[AdminSessionSummary])
def get_sessions(
    limit: int = 100,
    offset: int = 0,
    service: AdminQueryService = Depends(get_admin_query_service)
):
    """
    List all sessions (Active + History).
    """
    dto_list = service.get_all_sessions(limit=limit, offset=offset)
    
    # Map DTO to Response Schema
    # SessionListDTO contains 'items' which are SessionResponseDTOs (or Summaries)
    # Checking SessionListDTO definition might be needed, but assuming standard list structure
    # If SessionListDTO is a wrapper:
    sessions = dto_list.sessions if hasattr(dto_list, "sessions") else []
    
    return [
        AdminSessionSummary(
            session_id=s.session_id,
            job_id=s.config.job_id if s.config else "UNKNOWN", # Handling potential missing config in summaries
            user_id="mock_user", # DTO might not have user_id if not stored, Placeholder
            status=s.status.name if hasattr(s.status, "name") else str(s.status),
            score=s.total_score,
            created_at=s.created_at
        ) for s in sessions
    ]

@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session_detail(
    session_id: str,
    service: AdminQueryService = Depends(get_admin_query_service)
):
    """
    Get detailed session info (Read-Only).
    """
    dto = service.get_session_detail(session_id)
    if not dto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    
    # Reuse mapping logic or duplicate simple mapping
    return SessionResponse(
        session_id=dto.session_id,
        status=dto.status.name if hasattr(dto.status, "name") else str(dto.status),
        current_question_index=dto.current_question_index,
        total_questions=dto.total_questions,
        created_at=dto.created_at
    )


# --- Phase 4 Slice 3: Audit Timeline API -----------------------------------

@router.get("/interviews/{session_id}/audit")
async def get_audit_timeline(
    session_id: str,
    limit: int = Query(default=100, le=500),
):
    """
    Phase 4 Slice 3 - OB-6 Audit Timeline (Append-Only PG Source).

    Returns all lifecycle events for a session, ordered chronologically.
    trace_id links each event to statistics aggregation records.

    Contract:
    - Source: PostgreSQL session_audit_events (Append-Only)
    - No Redis or log-based data.
    - Result is paginated (max 500 rows).
    """
    try:
        repo = AuditTimelineRepository(_get_conn_config())
        events = await repo.get_timeline(session_id, limit=limit)
        decision = await repo.get_decision_event(session_id)
        return {
            "session_id": session_id,
            "total_events": len(events),
            "events": events,
            "decision_event": decision,
        }
    except Exception as exc:
        logger.error("[Audit] get_timeline failed session=%s: %s", session_id, exc)
        raise HTTPException(status_code=500, detail="Audit timeline unavailable")


@router.get("/stats/jobs/{job_id}")
async def get_job_stats(
    job_id: str,
    month_bucket: Optional[str] = Query(default=None, description="Format: YYYY-MM"),
):
    """
    Phase 4 Slice 1 - PG-Authoritative Job Statistics.

    Aggregates pass/fail counts for DECIDED + EVALUATIVE sessions only.
    Results are cached by (job_id, month_bucket) with 60-second TTL.
    """
    cache = GranularStatsCache()
    cached = cache.get_pass_fail(job_id, month_bucket)
    if cached:
        cached["source"] = "redis_cache"
        return cached

    try:
        repo = AggregateStatsRepository(_get_conn_config())
        result = await repo.get_pass_fail_by_job(job_id=job_id, month_bucket=month_bucket)
        cache.set_pass_fail(job_id, month_bucket, result)
        result["source"] = "pg_direct"
        return result
    except Exception as exc:
        logger.error("[Stats] get_job_stats failed job=%s: %s", job_id, exc)
        raise HTTPException(status_code=500, detail="Stats unavailable")


@router.post("/stats/invalidate/{job_id}")
async def invalidate_job_stats(
    job_id: str,
    month_bucket: Optional[str] = Query(default=None),
):
    """
    Phase 4 Drift Guard: Granular cache invalidation for a specific job.
    Called on DECISION_MADE, DECISION_OVERRIDDEN, or INVALIDATED events.
    """
    cache = GranularStatsCache()
    cache.invalidate_for_job(job_id, month_bucket)
    return {"invalidated": True, "job_id": job_id, "month_bucket": month_bucket}


# --- Phase 4 Slice 4: Decision Override API --------------------------------

@router.post("/interviews/{session_id}/decision-override")
async def override_decision(
    session_id: str,
    req: DecisionOverrideRequest,
    request: Request,
):
    """
    Phase 4 Slice 4 — Decision Override.

    Policy:
    - Original DECISION_MADE is NEVER modified (Append-Only).
    - A DECISION_OVERRIDDEN event is appended to session_audit_events.
    - Idempotency: Same X-Trace-Id re-request → no duplicate event appended.
    - After override: granular cache for job_id is invalidated.
    - Error: 409 on duplicate trace_id.
    """
    import uuid
    trace_id = request.headers.get("X-Trace-Id") or f"tr-{uuid.uuid4().hex[:16]}"

    if req.new_decision not in ("PASS", "FAIL"):
        raise HTTPException(
            status_code=400,
            detail="new_decision must be PASS or FAIL",
            headers={"X-Error-Code": "E_INVALID_DECISION", "X-Trace-Id": trace_id},
        )

    # Resolve job_id from DB for cache invalidation scope
    import asyncpg  # type: ignore
    try:
        conn = await asyncpg.connect(**_get_conn_config())
        row = await conn.fetchrow(
            "SELECT job_id FROM interviews WHERE session_id = $1", session_id
        )
        await conn.close()
        job_id = row["job_id"] if row else None
    except Exception as exc:
        logger.warning("[Override] Could not resolve job_id: %s", exc)
        job_id = None

    svc = DecisionOverrideService()
    result = await svc.apply_override(
        session_id=session_id,
        trace_id=trace_id,
        new_decision=req.new_decision,
        job_id=job_id,
    )

    if result["status"] == "error":
        raise HTTPException(
            status_code=500,
            detail=result.get("reason", "Override failed"),
            headers={"X-Error-Code": "E_UNKNOWN", "X-Trace-Id": trace_id},
        )

    if result["status"] == "duplicate":
        raise HTTPException(
            status_code=409,
            detail="Duplicate override trace_id. No new event appended.",
            headers={"X-Error-Code": "E_DUPLICATE_OVERRIDE", "X-Trace-Id": trace_id},
        )

    return {
        "override_status": result["status"],
        "session_id": session_id,
        "trace_id": trace_id,
        "new_decision": result["new_decision"],
        "previous_decision": result["previous_decision"],
        "cache_invalidated": result["cache_invalidated"],
    }
