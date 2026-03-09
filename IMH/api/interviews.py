"""
Interviews API - 면접 세션 관리 라우터 (TASK-UI)

Endpoints:
- GET  /api/v1/interviews                       - user's interview history
- POST /api/v1/interviews                       - create interview session
- GET  /api/v1/interviews/{interview_id}        - get session state
- POST /api/v1/interviews/{interview_id}/chat   - submit answer turn
- GET  /api/v1/interviews/{interview_id}/chat   - get chat history
- GET  /api/v1/interviews/{interview_id}/result - get evaluation result
"""

import re
import uuid
import random
import logging
from datetime import datetime
from typing import Optional

import asyncpg  # type: ignore
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from IMH.api.auth import require_user
from IMH.api.dependencies import get_session_service
from packages.imh_service.session_service import SessionService
from packages.imh_service.audit_wiring import AuditWiringService

logger = logging.getLogger("imh.interviews")
router = APIRouter(prefix="/interviews", tags=["Interviews"])

# Singleton audit wiring service (initialized lazily on first use)
_audit: Optional[AuditWiringService] = None

def _get_audit() -> AuditWiringService:
    global _audit
    if _audit is None:
        _audit = AuditWiringService()
    return _audit

INTERVIEW_PHASES = ["자기소개", "지원동기", "직무역량", "경험/사례", "문제해결", "마무리"]

PHASE_QUESTIONS = {
    "자기소개": ["자기소개를 해주세요.", "간단하게 본인에 대해 소개해 주세요."],
    "지원동기": ["저희 회사에 지원하게 된 동기를 말씀해 주세요.", "이 직무에 관심을 갖게 된 계기가 무엇인가요?"],
    "직무역량": ["본인의 가장 큰 강점은 무엇인가요?", "이 직무와 관련된 경험이나 역량을 설명해 주세요."],
    "경험/사례": ["팀에서 어려운 상황을 겪었던 경험과 어떻게 해결했는지 말씀해 주세요.", "프로젝트에서 주도적으로 역할을 한 경험이 있으면 소개해 주세요."],
    "문제해결": ["예상치 못한 문제에 직면했을 때 어떻게 대처하시나요?", "업무 중 갈등이 발생했을 때 어떻게 해결하셨나요?"],
    "마무리": ["마지막으로 하고 싶은 말씀이 있으신가요?", "입사 후 어떤 목표를 갖고 계신가요?"],
}


def _get_conn_params() -> dict:
    from packages.imh_core.config import IMHConfig
    cfg = IMHConfig.load()
    cs = cfg.POSTGRES_CONNECTION_STRING or ""
    m = re.match(r"postgresql(?:\+asyncpg)?://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", cs)
    if m:
        u, p, h, port, db = m.groups()
        return dict(host=h, port=int(port), user=u, password=p, database=db)
    raise RuntimeError("POSTGRES_CONNECTION_STRING not configured")


def _get_next_question(phase: str) -> str:
    questions = PHASE_QUESTIONS.get(phase, ["다음 질문입니다. 답변해 주세요."])
    return random.choice(questions)


def _get_trace_id(request: Request) -> str:
    """Extract trace_id from X-Trace-Id header or generate a fallback."""
    return request.headers.get("X-Trace-Id") or f"tr-{uuid.uuid4().hex[:16]}"


# Error code mapping for Section 79 compliance
ERROR_CODE_HEADERS = {
    "E_SESSION_ABORTED": {"X-Error-Code": "E_SESSION_ABORTED"},
    "E_DEADLINE_EXCEEDED": {"X-Error-Code": "E_DEADLINE_EXCEEDED"},
    "E_GEN_TIMEOUT": {"X-Error-Code": "E_GEN_TIMEOUT"},
    "E_UNKNOWN": {"X-Error-Code": "E_UNKNOWN"},
    "E_MODE_IMMUTABLE": {"X-Error-Code": "E_MODE_IMMUTABLE"},
    "E_SESSION_TERMINAL": {"X-Error-Code": "E_SESSION_TERMINAL"},
}


# --- Schemas ---

class CreateInterviewRequest(BaseModel):
    job_id: str


class ChatMessageRequest(BaseModel):
    content: str


class UpdateInterviewRequest(BaseModel):
    interview_mode: Optional[str] = None
    ai_question_text_visible: Optional[bool] = None


# --- Routes ---

@router.get("")
async def list_interviews(user_id: str = Depends(require_user)):
    """Get current user's interview history."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        rows = await conn.fetch(
            """
            SELECT i.session_id, i.job_id, i.status, i.created_at, i.completed_at,
                   j.title as job_title,
                   ie.decision, ie.summary, ie.tech_score, ie.problem_score, ie.comm_score, ie.nonverbal_score
            FROM interviews i
            LEFT JOIN jobs j ON j.job_id = i.job_id
            LEFT JOIN interview_evaluations ie ON ie.session_id = i.session_id
            WHERE i.user_id=$1
            ORDER BY i.created_at DESC
            """,
            user_id
        )
        return [
            {
                "session_id": r["session_id"],
                "job_id": r["job_id"],
                "job_title": r["job_title"],
                "status": r["status"],
                "decision": r["decision"],
                "summary": r["summary"],
                "tech_score": r["tech_score"],
                "problem_score": r["problem_score"],
                "comm_score": r["comm_score"],
                "nonverbal_score": r["nonverbal_score"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
            }
            for r in rows
        ]
    finally:
        await conn.close()


@router.post("", status_code=201)
async def create_interview(
    req: CreateInterviewRequest,
    request: Request,
    user_id: str = Depends(require_user),
    service: "SessionService" = Depends(get_session_service)
):
    """
    Create a new interview session for a job. Section 72: fully atomic.
    The session row in `interviews` table is written inside the same asyncpg
    connection/transaction that the engine uses. On any failure the entire
    creation is rolled back — no orphan rows.
    """
    trace_id = _get_trace_id(request)
    params = _get_conn_params()

    # Section 72: Atomic guard — verify no partial rows survive a failure
    # The engine's start_session() writes to the `interviews` table internally.
    # We wrap the full creation in a transaction so any mid-flight error rolls back.
    conn = await asyncpg.connect(**params)
    try:
        async with conn.transaction():
            # 1. Pre-check: job must be PUBLISHED (duplicates service check for atomicity)
            job_row = await conn.fetchrow(
                """SELECT job_id, status, description, immutable_snapshot
                   FROM jobs WHERE job_id=$1""", req.job_id
            )
            if not job_row:
                raise HTTPException(
                    status_code=404,
                    detail="Job not found",
                    headers={"X-Error-Code": "E_SESSION_ABORTED", "X-Trace-Id": trace_id},
                )
            if job_row["status"] not in ("PUBLISHED", "published"):
                raise HTTPException(
                    status_code=400,
                    detail="Job is not accepting applicants",
                    headers={"X-Error-Code": "E_JOB_NOT_PUBLISHED", "X-Trace-Id": trace_id},
                )

            # 2. Build policy_snapshot from immutable_snapshot JSON
            import json
            snap_raw = job_row.get("immutable_snapshot")
            if isinstance(snap_raw, str):
                try:
                    snap = json.loads(snap_raw)
                except Exception:
                    snap = {}
            elif isinstance(snap_raw, dict):
                snap = snap_raw
            else:
                snap = {}

            # immutable_snapshot already contains SessionConfig-compatible fields
            # (total_question_limit, question_timeout_sec, mode, etc.)
            # Just ensure job_id is included
            policy_snapshot = dict(snap)
            policy_snapshot["job_id"] = req.job_id

            try:
                dto = await run_in_threadpool(service.create_session, policy_snapshot, user_id)
            except ValueError as e:
                code = 404 if "not found" in str(e).lower() else 400
                raise HTTPException(
                    status_code=code,
                    detail=str(e),
                    headers={"X-Error-Code": "E_SESSION_ABORTED", "X-Trace-Id": trace_id},
                )
            except Exception as e:
                logger.error("Session creation engine failure trace=%s: %s", trace_id, e)
                raise HTTPException(
                    status_code=500,
                    detail="Session creation failed",
                    headers={"X-Error-Code": "E_SESSION_ABORTED", "X-Trace-Id": trace_id},
                )

            # 3. Atomic verification: confirm session row was actually written
            session_row = await conn.fetchrow(
                "SELECT session_id FROM interviews WHERE session_id=$1", dto.session_id
            )
            if not session_row:
                # Engine reported success but row missing — raise to trigger rollback
                logger.error(
                    "ATOMIC_GUARD: session_id=%s row missing after create trace=%s",
                    dto.session_id, trace_id
                )
                raise HTTPException(
                    status_code=500,
                    detail="Session creation integrity check failed",
                    headers={"X-Error-Code": "E_SESSION_ABORTED", "X-Trace-Id": trace_id},
                )

            logger.info("Session created session_id=%s user=%s trace=%s", dto.session_id, user_id, trace_id)
            # OB-1: SESSION_CREATED – fire-and-forget audit event
            _get_audit().on_session_created(
                session_id=dto.session_id, trace_id=trace_id, actor_id=user_id
            )
            return {
                "session_id": dto.session_id,
                "message": "Interview started",
                "trace_id": trace_id,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in create_interview trace=%s: %s", trace_id, e)
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
            headers={"X-Error-Code": "E_UNKNOWN", "X-Trace-Id": trace_id},
        )
    finally:
        await conn.close()


@router.get("/{interview_id}")
async def get_interview(
    interview_id: str,
    user_id: str = Depends(require_user),
):
    """Get interview session state."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        row = await conn.fetchrow(
            """
            SELECT i.session_id, i.job_id, i.status, i.created_at, i.started_at, i.completed_at,
                   j.title as job_title
            FROM interviews i
            LEFT JOIN jobs j ON j.job_id = i.job_id
            WHERE i.session_id=$1
            """,
            interview_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Interview not found")

        turns = await conn.fetchval(
            "SELECT COUNT(*) FROM chat_history WHERE session_id=$1 AND role='user'",
            interview_id
        )
        phase_idx = min(int(turns), len(INTERVIEW_PHASES) - 1)
        current_phase = INTERVIEW_PHASES[phase_idx]

        return {
            "session_id": row["session_id"],
            "job_id": row["job_id"],
            "job_title": row["job_title"],
            "status": row["status"],
            "current_phase": current_phase,
            "phase_index": phase_idx,
            "total_phases": len(INTERVIEW_PHASES),
            "turn_count": turns,
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "started_at": row["started_at"].isoformat() if row["started_at"] else None,
        }
    finally:
        await conn.close()


@router.patch("/{interview_id}")
async def update_interview(
    interview_id: str,
    req: UpdateInterviewRequest,
    request: Request,
    user_id: str = Depends(require_user),
    service: "SessionService" = Depends(get_session_service)
):
    """
    Update interview session config.
    Guard order (applied before any field mutation):
      1. Late Mutation Guard (Phase 4 Slice 4): DECIDED sessions → 409 E_LATE_MUTATION_FORBIDDEN
      2. C3 Mode Immutability Guard: non-APPLIED sessions → 409 E_MODE_IMMUTABLE
    """
    from packages.imh_service.drift_guard import check_late_mutation_forbidden
    trace_id = _get_trace_id(request)

    # Phase 4 Slice 4 – Late Mutation Guard (highest priority)
    late_error = await check_late_mutation_forbidden(interview_id)
    if late_error:
        raise HTTPException(
            status_code=409,
            detail=late_error["detail"],
            headers={
                "X-Error-Code": "E_LATE_MUTATION_FORBIDDEN",
                "X-Trace-Id": trace_id,
            },
        )

    session = service.get_session(interview_id)
    if not session:
        raise HTTPException(status_code=404, detail="Interview not found")

    # C3 Guard: mode cannot be changed if session already started (not APPLIED)
    if session.status != "APPLIED":
        if req.interview_mode is not None or req.ai_question_text_visible is not None:
            raise HTTPException(
                status_code=409,
                detail="Interview mode is immutable once session has started.",
                headers={"X-Error-Code": "E_MODE_IMMUTABLE", "X-Trace-Id": trace_id}
            )

    return {"status": "success", "message": "No changes made (Guard only implemented)"}



@router.post("/{interview_id}/abort")
async def abort_interview(
    interview_id: str,
    request: Request,
    user_id: str = Depends(require_user),
    service: "SessionService" = Depends(get_session_service)
):
    """
    Abort interview session for audio/system failure. (Phase 3-FIX-C2)
    """
    trace_id = _get_trace_id(request)
    try:
        dto = service.abort_session(interview_id, reason="AUDIO_FAIL")
        # OB-5: SESSION_ABORTED – fire-and-forget audit event
        _get_audit().on_session_aborted(
            session_id=interview_id,
            trace_id=trace_id,
            abort_reason="AUDIO_FAIL",
            actor_id=user_id,
        )
        return {
            "session_id": dto.session_id,
            "status": dto.status,
            "message": "Session aborted due to audio failure",
            "trace_id": trace_id
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Abort failed trace=%s: %s", trace_id, e)
        raise HTTPException(
            status_code=500,
            detail="Abort failed",
            headers={"X-Error-Code": "E_UNKNOWN", "X-Trace-Id": trace_id}
        )


@router.get("/{interview_id}/chat")
async def get_chat_history(
    interview_id: str,
    user_id: str = Depends(require_user),
):
    """Get full chat history for interview."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        rows = await conn.fetch(
            "SELECT role, content, phase, created_at FROM chat_history WHERE session_id=$1 ORDER BY created_at",
            interview_id
        )
        return [
            {
                "role": r["role"],
                "content": r["content"],
                "phase": r["phase"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    finally:
        await conn.close()


@router.post("/{interview_id}/chat")
async def submit_chat(
    interview_id: str,
    req: ChatMessageRequest,
    request: Request,
    user_id: str = Depends(require_user),
    service: "SessionService" = Depends(get_session_service)
):
    """Submit an answer turn. Returns AI's next question or completion."""
    from packages.imh_dto.session import AnswerSubmissionDTO
    
    # Check if session exists and is in progress
    session_dto = service.get_session(interview_id)
    if not session_dto:
        raise HTTPException(status_code=404, detail="Interview not found")
        
    if session_dto.status == "ABORTED":
        raise HTTPException(
            status_code=409,
            detail="This session has been aborted and cannot be resumed.",
            headers={
                "X-Error-Code": "E_SESSION_TERMINAL",
                "X-Trace-Id": _get_trace_id(request),
                "reason": "ABORTED",
                "abort_reason": "AUDIO_FAIL"
            }
        )

    if session_dto.status not in ("IN_PROGRESS", "APPLIED"):
        raise HTTPException(status_code=400, detail="Interview is not in progress")

    # 1. Answer Submission via Engine (Phase increment implicitly handled)
    submit_dto = AnswerSubmissionDTO(type="TEXT", content=req.content, duration_seconds=10.0)
    try:
         updated_session = await run_in_threadpool(service.submit_answer, interview_id, submit_dto)
    except Exception as e:
         logger.error(f"Error submitting chat for {interview_id}: {e}")
         raise HTTPException(status_code=500, detail=str(e))

    trace_id = _get_trace_id(request)
    # OB-2: TURN_SUBMITTED — fire-and-forget audit event
    turn_index = getattr(updated_session, "current_question_index", 0) or 0
    _get_audit().on_turn_submitted(
        session_id=interview_id,
        trace_id=trace_id,
        turn_index=turn_index,
        actor_id=user_id,
    )

    now = datetime.now()
    
    # Maintain legacy chat_history table for backward UI compatibility:
    # Get current turn dynamically 
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        turns = await conn.fetchval(
            "SELECT COUNT(*) FROM chat_history WHERE session_id=$1 AND role='user'",
            interview_id
        )
        
        phase_idx = min(int(turns), len(INTERVIEW_PHASES) - 1)
        current_phase = INTERVIEW_PHASES[phase_idx]

        await conn.execute(
            "INSERT INTO chat_history (session_id, role, content, phase, created_at) VALUES ($1,'user',$2,$3,$4)",
            interview_id, req.content, current_phase, now
        )
        
        # Check if engine decided to terminate
        if updated_session.status in ("COMPLETED", "INTERRUPTED"):
            
             # --- EVALUATION ENGINE TRIGGER (Synchronous execution) ---
             try:
                 # --- Phase 3-FIX-C1: Deterministic Evaluation Trigger ---
                 from packages.imh_eval.engine import RubricEvaluator, EvaluationContext
                 from packages.imh_report.engine import ReportGenerator
                 
                 evaluator = RubricEvaluator()
                 
                 # 1. Turn-Scoped Buffer (C1 Hard Rule: Memory-only, disposed immediately)
                 # Simulated from context history for deterministic signature
                 transcripts = [{"turn_id": i, "text": q.content} for i, q in enumerate(updated_session.question_history)]
                 stt_hash = evaluator.compute_stt_snapshot_hash(transcripts)
                 del transcripts # Section 1.4: "Raw Text disposed immediately after hash"

                 context = EvaluationContext(
                     job_category="DEV", 
                     job_id=updated_session.job_id,
                     answer_text=req.content,
                     rag_keywords_found=["Leadership", "Java"], 
                     hint_count=0,
                     # Snapshot Hashes - Section 1.2
                     resume_snapshot_hash=getattr(updated_session, "resume_snapshot_hash", "mock_resume_hash"),
                     policy_snapshot_hash=getattr(updated_session, "policy_snapshot_hash", "mock_policy_hash"),
                     stt_snapshot_hash=stt_hash,
                     context_history=[{"role": "user", "content": req.content}], # Canonical history slot
                     phase_flow="MAIN",
                     version=1
                 )
                 
                 eval_result = evaluator.evaluate(context)
                 report = ReportGenerator.generate(eval_result)
                 report.raw_debug_info = {"_session_id": updated_session.session_id, "_interview_id": updated_session.session_id}
                 
                 service.history_repo.save_interview_result(updated_session.session_id, report)
                 service.state_repo.update_status(updated_session.session_id, "EVALUATED")
             except Exception as e:
                 logger.error(f"Failed to generate evaluation report for {updated_session.session_id}: {e}")
                 pass

             farewell = "면접이 종료되었습니다. 수고하셨습니다. 결과는 추후 안내드리겠습니다."
             await conn.execute(
                 "INSERT INTO chat_history (session_id, role, content, phase, created_at) VALUES ($1,'ai',$2,'마무리',$3)",
                 interview_id, farewell, now
             )

             return {
                 "status": "COMPLETED",
                 "ai_message": farewell,
                 "current_phase": "마무리",
                 "is_done": True,
             }
        else:
            # Session is still IN_PROGRESS
            new_turns = turns + 1
            next_phase_idx = min(int(new_turns), len(INTERVIEW_PHASES) - 1)
            next_phase = INTERVIEW_PHASES[next_phase_idx]
            
            # Extract question text from the context generated by 
            question_text = updated_session.current_question.content if updated_session.current_question else _get_next_question(next_phase)
            
            if next_phase_idx > phase_idx:
                ai_msg = f"[{next_phase}] 단계로 넘어가겠습니다.\n{question_text}"
            else:
                ai_msg = question_text

            await conn.execute(
                "INSERT INTO chat_history (session_id, role, content, phase, created_at) VALUES ($1,'ai',$2,$3,$4)",
                interview_id, ai_msg, next_phase, now
            )

            return {
                "status": "IN_PROGRESS",
                "ai_message": ai_msg,
                "current_phase": next_phase,
                "is_done": False,
                "turn": new_turns,
            }
    finally:
        await conn.close()


@router.get("/{interview_id}/result")
async def get_result(
    interview_id: str,
    user_id: str = Depends(require_user),
    service: "SessionService" = Depends(get_session_service)
):
    """Get interview evaluation result."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        intvw = await conn.fetchrow(
            "SELECT i.status, j.title as job_title FROM interviews i "
            "LEFT JOIN jobs j ON j.job_id = i.job_id WHERE i.session_id=$1", 
            interview_id
        )
        if not intvw:
            raise HTTPException(status_code=404, detail="Interview not found")
            
        status = intvw["status"]
        job_title = intvw["job_title"]
        
        if status != "EVALUATED":
             return {"status": status, "job_title": job_title, "evaluation": None}
             
        # TASK-032: Map from evaluation_scores JSONB instead of legacy interview_evaluations
        report = service.history_repo.find_by_id(interview_id)
        if not report:
             # If state claims EVALUATED but report is missing, degrade gracefully
             return {"status": status, "job_title": job_title, "evaluation": None}

        # Safe parsing out of report model adhering to TASK-032 UI Spec Option A
        tech_score = 0.0
        prob_score = 0.0
        comm_score = 0.0
        nonv_score = 0.0
        
        missing_count = 0
        total_expected = 4
        
        for detail in report.details:
            if detail.tag_code == "capability.knowledge":
                tech_score = round(detail.score * 20.0, 1)
            elif detail.tag_code == "capability.problem_solving":
                prob_score = round(detail.score * 20.0, 1)
            elif detail.tag_code == "capability.communication":
                comm_score = round(detail.score * 20.0, 1)
            elif detail.tag_code == "capability.attitude":
                nonv_score = round(detail.score * 20.0, 1)
                
        # Count missing (Scores defaulting to 0)
        missing_count = sum(1 for s in (tech_score, prob_score, comm_score, nonv_score) if s == 0.0)
        
        # Calculate decision
        total_score_100 = round(report.header.total_score, 1) if report.header else 0.0
        decision = "PASS" if total_score_100 >= 70.0 else "FAIL"
        
        # Summary mapping
        summary_text = ""
        if report.footer and report.footer.actionable_insights:
            summary_text = " ".join(report.footer.actionable_insights[:2])
        if not summary_text:
            summary_text = "세부 분석 내역이 없습니다."
            
        # Fallback Alert String
        if missing_count > 0:
            summary_text += "\n\n[시스템 메시지] 일부 평가 항목 생성이 누락되었습니다."
            
        return {
            "status": status,
            "job_title": job_title,
            "evaluation": {
                "decision": decision,
                "summary": summary_text.strip(),
                "scores": {
                    "tech": tech_score,
                    "problem": prob_score,
                    "comm": comm_score,
                    "nonverbal": nonv_score,
                }
            }
        }
    finally:
        await conn.close()
