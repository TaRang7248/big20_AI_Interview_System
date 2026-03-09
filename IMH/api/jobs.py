"""
Jobs API - 채용공고 CRUD 라우터 (TASK-UI)

Endpoints:
- GET    /api/v1/jobs              - list all jobs
- POST   /api/v1/jobs              - create job (admin)
- GET    /api/v1/jobs/{job_id}     - get job detail + stats
- PATCH  /api/v1/jobs/{job_id}     - update job (admin)
- GET    /api/v1/jobs/{job_id}/candidates          - candidate list
- GET    /api/v1/jobs/{job_id}/candidates/{user_id} - candidate detail
"""

import re
import json
import uuid
import logging
from datetime import datetime
from typing import Optional, List

import asyncpg  # type: ignore
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from IMH.api.auth import require_admin, require_user, get_current_user_id
from IMH.api.audit_log import write_audit_log

logger = logging.getLogger("imh.jobs")
router = APIRouter(prefix="/jobs", tags=["Jobs"])
security = HTTPBearer(auto_error=False)


def _get_conn_params() -> dict:
    from packages.imh_core.config import IMHConfig
    cfg = IMHConfig.load()
    cs = cfg.POSTGRES_CONNECTION_STRING or ""
    m = re.match(r"postgresql(?:\+asyncpg)?://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", cs)
    if m:
        u, p, h, port, db = m.groups()
        return dict(host=h, port=int(port), user=u, password=p, database=db)
    raise RuntimeError("POSTGRES_CONNECTION_STRING not configured")


# --- Schemas ---

class JobCreateRequest(BaseModel):
    title: str
    company: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    headcount: Optional[int] = None
    deadline: Optional[str] = None
    tags: Optional[List[str]] = None
    total_question_limit: int = 10
    question_timeout_sec: int = 120
    mode: str = "ACTUAL"
    requirements: Optional[List[str]] = None
    preferences: Optional[List[str]] = None
    # ── AI Policy fields (Frozen at Publish) ──────────────────────────────
    evaluation_weights: Optional[dict] = None  # e.g. {"job": 40.0, "comm": 30.0, "attitude": 30.0}
    persona: Optional[str] = "professional"    # 'professional' | 'friendly' | 'strict'
    fixed_questions: Optional[List[str]] = None  # Always-inject questions list
    wiring_resume_q_enabled: Optional[bool] = True
    wiring_rag_enabled: Optional[bool] = True
    wiring_multimodal_enabled: Optional[bool] = True


class JobUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    headcount: Optional[int] = None
    deadline: Optional[str] = None
    tags: Optional[List[str]] = None
    action: Optional[str] = None  # 'PUBLISH' | 'CLOSE'


# Helper: get trace_id from request headers or generate one
def _get_trace_id(request: Request) -> str:
    return request.headers.get("X-Trace-Id") or f"tr-{uuid.uuid4().hex[:16]}"


# Helper: assert admin owns this job (Section 22 - Single Ownership)
async def _assert_ownership(conn, job_id: str, admin_id: str) -> dict:
    """Fetch job and enforce creator_admin_id ownership. Raises 403 or 404."""
    row = await conn.fetchrow("SELECT * FROM jobs WHERE job_id=$1", job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    owner = row.get("creator_admin_id")
    # Allow if creator_admin_id is NULL (legacy rows) or matches
    if owner and owner != admin_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: you do not own this job",
            headers={"X-Error-Code": "E_FORBIDDEN"},
        )
    d = dict(row)
    if d.get("immutable_snapshot") and isinstance(d["immutable_snapshot"], str):
        d["immutable_snapshot"] = json.loads(d["immutable_snapshot"])
    if d.get("mutable_data") and isinstance(d["mutable_data"], str):
        d["mutable_data"] = json.loads(d["mutable_data"])
    return d


# --- Helpers ---

async def _fetch_job(conn, job_id: str) -> Optional[dict]:
    row = await conn.fetchrow("SELECT * FROM jobs WHERE job_id=$1", job_id)
    if not row:
        return None
    d = dict(row)
    if d.get("immutable_snapshot") and isinstance(d["immutable_snapshot"], str):
        d["immutable_snapshot"] = json.loads(d["immutable_snapshot"])
    if d.get("mutable_data") and isinstance(d["mutable_data"], str):
        d["mutable_data"] = json.loads(d["mutable_data"])
    return d


def _job_to_response(d: dict) -> dict:
    mutable = d.get("mutable_data") or {}
    snap = d.get("immutable_snapshot") or {}
    return {
        "job_id": d["job_id"],
        "title": d.get("title", ""),
        "company": d.get("company"),
        "status": d.get("status", "DRAFT"),
        "description": d.get("description") or mutable.get("description"),
        "location": d.get("location") or mutable.get("location"),
        "headcount": d.get("headcount") or mutable.get("headcount"),
        "deadline": str(d["deadline"]) if d.get("deadline") else mutable.get("deadline"),
        "tags": d.get("tags") or mutable.get("tags", []),
        "published_at": d.get("published_at").isoformat() if d.get("published_at") else None,
        "created_at": d.get("created_at").isoformat() if d.get("created_at") else None,
        "policy": snap,
    }


# --- Routes ---

@router.get("")
async def list_jobs(
    status: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """List jobs. Candidates see PUBLISHED only. Admins see ONLY their own jobs."""
    from IMH.api.auth import _get_user_id_from_token, _user_type_store
    user_id = _get_user_id_from_token(
        credentials.credentials if credentials else None
    )
    is_admin = user_id and _user_type_store.get(user_id) == "ADMIN"

    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        if is_admin:
            # Section 22: Admin sees ONLY their own jobs
            if status:
                rows = await conn.fetch(
                    "SELECT * FROM jobs WHERE creator_admin_id=$1 AND status=$2::job_status ORDER BY created_at DESC",
                    user_id, status.upper()
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM jobs WHERE creator_admin_id=$1 ORDER BY created_at DESC",
                    user_id
                )
        else:
            # Candidates see all PUBLISHED jobs
            rows = await conn.fetch(
                "SELECT * FROM jobs WHERE status='PUBLISHED'::job_status ORDER BY created_at DESC"
            )

        results = []
        for r in rows:
            d = dict(r)
            if d.get("immutable_snapshot") and isinstance(d["immutable_snapshot"], str):
                d["immutable_snapshot"] = json.loads(d["immutable_snapshot"])
            if d.get("mutable_data") and isinstance(d["mutable_data"], str):
                d["mutable_data"] = json.loads(d["mutable_data"])
            results.append(_job_to_response(d))
        return results
    finally:
        await conn.close()


@router.post("", status_code=201)
async def create_job(
    req: JobCreateRequest,
    user_id: str = Depends(require_admin),
):
    """Create a new job posting (Admin only). Binds creator_admin_id."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        policy = {
            "mode": req.mode,
            "total_question_limit": req.total_question_limit,
            "min_question_count": 10,
            "question_timeout_sec": req.question_timeout_sec,
            "silence_timeout_sec": 15,
            "allow_retry": False,
            "description": req.description or "",
            "requirements": req.requirements or [],
            "preferences": req.preferences or [],
            "evaluation_weights": req.evaluation_weights or {"job": 40.0, "comm": 30.0, "attitude": 30.0},
            "result_exposure": "AFTER_14_DAYS",
            # ── New AI Policy Fields ─
            "persona": req.persona or "professional",
            "fixed_questions": req.fixed_questions or [],
            "wiring_resume_q_enabled": req.wiring_resume_q_enabled if req.wiring_resume_q_enabled is not None else True,
            "wiring_rag_enabled": req.wiring_rag_enabled if req.wiring_rag_enabled is not None else True,
            "wiring_multimodal_enabled": req.wiring_multimodal_enabled if req.wiring_multimodal_enabled is not None else True,
        }
        deadline = None
        if req.deadline:
            try:
                deadline = datetime.strptime(req.deadline, "%Y-%m-%d").date()
            except ValueError:
                pass

        # Section 22: Bind creator_admin_id at creation (may be NULL if column not yet added)
        try:
            await conn.execute(
                """
                INSERT INTO jobs
                    (job_id, title, company, status, description, location, headcount, deadline, tags,
                     immutable_snapshot, creator_admin_id, created_at, updated_at)
                VALUES ($1,$2,$3,'DRAFT'::job_status,$4,$5,$6,$7,$8,$9,$10,NOW(),NOW())
                """,
                job_id, req.title, req.company,
                req.description, req.location, req.headcount,
                deadline, req.tags or [],
                json.dumps(policy), user_id,
            )
        except Exception:
            # Fallback if creator_admin_id column not yet migrated
            await conn.execute(
                """
                INSERT INTO jobs
                    (job_id, title, company, status, description, location, headcount, deadline, tags,
                     immutable_snapshot, created_at, updated_at)
                VALUES ($1,$2,$3,'DRAFT'::job_status,$4,$5,$6,$7,$8,$9,NOW(),NOW())
                """,
                job_id, req.title, req.company,
                req.description, req.location, req.headcount,
                deadline, req.tags or [],
                json.dumps(policy),
            )
        return {"job_id": job_id, "message": "Job created", "creator_admin_id": user_id}
    finally:
        await conn.close()


@router.get("/{job_id}")
async def get_job(job_id: str):
    """Get job detail with pass/fail statistics."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        job = await _fetch_job(conn, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        evals = await conn.fetch(
            """
            SELECT ie.decision, COUNT(*) as cnt
            FROM interview_evaluations ie
            JOIN interviews i ON i.session_id = ie.session_id
            WHERE i.job_id=$1
            GROUP BY ie.decision
            """,
            job_id
        )
        stats = {"PASS": 0, "FAIL": 0}
        for row in evals:
            stats[row["decision"]] = row["cnt"]

        total = await conn.fetchval(
            "SELECT COUNT(*) FROM interviews WHERE job_id=$1", job_id
        )

        result = _job_to_response(job)
        result["stats"] = {
            "total_applicants": total,
            "pass_count": stats["PASS"],
            "fail_count": stats["FAIL"],
        }
        return result
    finally:
        await conn.close()


@router.patch("/{job_id}")
async def update_job(
    job_id: str,
    req: JobUpdateRequest,
    user_id: str = Depends(require_admin),
):
    """Update job info or change status (PUBLISH/CLOSE). Section 22: ownership enforced."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        job = await _assert_ownership(conn, job_id, user_id)

        updates = []
        values = []
        idx = 1

        if req.title is not None:
            updates.append(f"title=${idx}"); values.append(req.title); idx += 1
        if req.description is not None:
            updates.append(f"description=${idx}"); values.append(req.description); idx += 1
        if req.location is not None:
            updates.append(f"location=${idx}"); values.append(req.location); idx += 1
        if req.headcount is not None:
            updates.append(f"headcount=${idx}"); values.append(req.headcount); idx += 1
        if req.deadline is not None:
            try:
                dl = datetime.strptime(req.deadline, "%Y-%m-%d").date()
                updates.append(f"deadline=${idx}"); values.append(dl); idx += 1
            except ValueError:
                pass
        if req.tags is not None:
            updates.append(f"tags=${idx}"); values.append(req.tags); idx += 1

        if req.action == "PUBLISH" and job["status"] == "DRAFT":
            updates.append("status='PUBLISHED'::job_status")
            updates.append(f"published_at=${idx}"); values.append(datetime.now()); idx += 1
        elif req.action == "CLOSE" and job["status"] == "PUBLISHED":
            updates.append("status='CLOSED'::job_status")

        if updates:
            updates.append(f"updated_at=${idx}"); values.append(datetime.now()); idx += 1
            values.append(job_id)
            await conn.execute(
                f"UPDATE jobs SET {', '.join(updates)} WHERE job_id=${idx}",
                *values
            )
        return {"message": "Job updated"}
    finally:
        await conn.close()


@router.post("/{job_id}/publish", status_code=200)
async def publish_job(
    job_id: str,
    request: Request,
    user_id: str = Depends(require_admin),
):
    """
    Phase 2-1: Publish a DRAFT job. Section 22 ownership enforced.
    Writes audit log before state change. Returns trace_id.
    """
    trace_id = _get_trace_id(request)
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        # Ownership + status check
        job = await _assert_ownership(conn, job_id, user_id)
        if job["status"] not in ("DRAFT", "draft"):
            raise HTTPException(
                status_code=400,
                detail=f"Job cannot be published from status '{job['status']}'",
                headers={"X-Error-Code": "E_CONFLICT", "X-Trace-Id": trace_id},
            )
        # Write audit BEFORE state change
        await write_audit_log(
            trace_id=trace_id,
            actor_user_id=user_id,
            actor_role="ADMIN",
            resource_type="JOB",
            resource_id=job_id,
            access_reason_code="JOB_PUBLISH",
            additional_metadata={"from_status": job["status"], "to_status": "PUBLISHED"},
        )
        await conn.execute(
            "UPDATE jobs SET status='PUBLISHED'::job_status, published_at=NOW(), updated_at=NOW() WHERE job_id=$1",
            job_id
        )
        logger.info("JOB_PUBLISHED job_id=%s admin=%s trace=%s", job_id, user_id, trace_id)
        return {"job_id": job_id, "status": "PUBLISHED", "trace_id": trace_id}
    finally:
        await conn.close()


@router.post("/{job_id}/close", status_code=200)
async def close_job(
    job_id: str,
    request: Request,
    user_id: str = Depends(require_admin),
):
    """
    Phase 2-1: Close a PUBLISHED job. Section 22 ownership enforced.
    Writes audit log. Returns trace_id. Closed job = E_JOB_CLOSED for candidates.
    """
    trace_id = _get_trace_id(request)
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        job = await _assert_ownership(conn, job_id, user_id)
        if job["status"] not in ("PUBLISHED", "published"):
            raise HTTPException(
                status_code=400,
                detail=f"Only PUBLISHED jobs can be closed (current: {job['status']})",
                headers={"X-Error-Code": "E_JOB_NOT_PUBLISHED", "X-Trace-Id": trace_id},
            )
        # Write audit BEFORE state change
        await write_audit_log(
            trace_id=trace_id,
            actor_user_id=user_id,
            actor_role="ADMIN",
            resource_type="JOB",
            resource_id=job_id,
            access_reason_code="JOB_CLOSE",
            additional_metadata={"from_status": job["status"], "to_status": "CLOSED"},
        )
        await conn.execute(
            "UPDATE jobs SET status='CLOSED'::job_status, updated_at=NOW() WHERE job_id=$1",
            job_id
        )
        logger.info("JOB_CLOSED job_id=%s admin=%s trace=%s", job_id, user_id, trace_id)
        return {"job_id": job_id, "status": "CLOSED", "trace_id": trace_id}
    finally:
        await conn.close()


@router.get("/{job_id}/candidates")
async def list_candidates(
    job_id: str,
    user_id: str = Depends(require_admin),
):
    """Candidate list. Section 22: ownership enforced – only own job."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    # Ownership check
    await _assert_ownership(conn, job_id, user_id)
    try:
        rows = await conn.fetch(
            """
            SELECT i.session_id, i.user_id, i.status, i.created_at,
                   u.name, u.email,
                   ie.decision, ie.tech_score, ie.problem_score, ie.comm_score, ie.nonverbal_score
            FROM interviews i
            LEFT JOIN user_info u ON u.user_id = i.user_id
            LEFT JOIN interview_evaluations ie ON ie.session_id = i.session_id
            WHERE i.job_id=$1
            ORDER BY i.created_at DESC
            """,
            job_id
        )
        return [
            {
                "session_id": r["session_id"],
                "user_id": r["user_id"],
                "name": r["name"] or r["user_id"],
                "email": r["email"],
                "interview_status": r["status"],
                "decision": r["decision"],
                "tech_score": r["tech_score"],
                "problem_score": r["problem_score"],
                "comm_score": r["comm_score"],
                "nonverbal_score": r["nonverbal_score"],
                "applied_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    finally:
        await conn.close()


@router.get("/{job_id}/candidates/{candidate_user_id}")
async def get_candidate_detail(
    job_id: str,
    candidate_user_id: str,
    admin_id: str = Depends(require_admin),
):
    """Full candidate detail. Section 22: ownership enforced."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        user = await conn.fetchrow(
            "SELECT user_id, name, birth_date, gender, email, address, phone FROM user_info WHERE user_id=$1",
            candidate_user_id
        )

        resume = await conn.fetchrow(
            "SELECT file_name, file_path, uploaded_at FROM resumes WHERE user_id=$1 ORDER BY uploaded_at DESC LIMIT 1",
            candidate_user_id
        )

        interview = await conn.fetchrow(
            "SELECT session_id, status, created_at FROM interviews WHERE job_id=$1 AND user_id=$2 ORDER BY created_at DESC LIMIT 1",
            job_id, candidate_user_id
        )

        chat = []
        eval_data = None
        if interview:
            sid = interview["session_id"]
            chat_rows = await conn.fetch(
                "SELECT role, content, phase, created_at FROM chat_history WHERE session_id=$1 ORDER BY created_at",
                sid
            )
            chat = [
                {
                    "role": r["role"],
                    "content": r["content"],
                    "phase": r["phase"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in chat_rows
            ]

            eval_row = await conn.fetchrow(
                "SELECT decision, summary, tech_score, problem_score, comm_score, nonverbal_score FROM interview_evaluations WHERE session_id=$1",
                sid
            )
            if eval_row:
                eval_data = dict(eval_row)

        user_dict = {}
        if user:
            user_dict = dict(user)
            if user_dict.get("birth_date"):
                user_dict["birth_date"] = str(user_dict["birth_date"])

        return {
            "user": user_dict or {"user_id": candidate_user_id},
            "resume": {
                "file_name": resume["file_name"],
                "uploaded_at": resume["uploaded_at"].isoformat() if resume["uploaded_at"] else None,
            } if resume else None,
            "interview": {
                "session_id": interview["session_id"],
                "status": interview["status"],
                "created_at": interview["created_at"].isoformat() if interview["created_at"] else None,
            } if interview else None,
            "chat_history": chat,
            "evaluation": eval_data,
        }
    finally:
        await conn.close()
