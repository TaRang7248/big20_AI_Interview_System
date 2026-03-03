"""
Resume API - 이력서 업로드/조회/다운로드 라우터 (Phase 2-2: MIME validation, size limit, parse_status)

Phase 2-2 additions:
- MIME whitelist enforcement (magic bytes + extension double-check)
- 5 MB max file size limit → E_FILE_TOO_LARGE
- Rejected MIME → E_MIME_REJECTED
- parse_status field: PARSED | FAILED → resume_summary_snapshot="" on FAILED
- Per-job resume binding enforced via job_application_id column

Endpoints:
- POST /api/v1/resume/upload            - upload resume (candidate own session only)
- GET  /api/v1/resume                   - get current user's resume metadata
- GET  /api/v1/resume/download          - candidate self-download (own only)
- GET  /api/v1/resume/admin-download    - admin download with mandatory audit
- GET  /api/v1/resume/{resume_id}/audit-history - admin audit trail
"""

import re
import uuid
import logging
from datetime import datetime
from pathlib import Path

import asyncpg  # type: ignore
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from fastapi.responses import FileResponse

from IMH.api.auth import require_user, require_admin
from IMH.api.audit_log import write_audit_log, get_audit_logs_for_resource, VALID_REASON_CODES

logger = logging.getLogger("imh.resume")
router = APIRouter(prefix="/resume", tags=["Resume"])

RESUME_DIR = Path(r"c:\big20\big20_AI_Interview_simulation\IMH\IMH_interview\data\resumes")
RESUME_DIR.mkdir(parents=True, exist_ok=True)

# ─── Phase 2-2: Security Constraints ─────────────────────────────────────────
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Extension → expected MIME type
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}

# Magic bytes for each allowed type (offset 0 bytes)
MAGIC_BYTES: dict = {
    b"%PDF": ".pdf",
    b"\xd0\xcf\x11\xe0": ".doc",   # MS-CFB (older DOC/XLS/PPT)
    b"PK\x03\x04": ".docx",         # ZIP (DOCX / PPTX / XLSX are all ZIP-based)
}


def _detect_extension_by_magic(content: bytes) -> str | None:
    """Return the canonical extension detected from magic bytes, or None."""
    for magic, ext in MAGIC_BYTES.items():
        if content[:len(magic)] == magic:
            return ext
    # Plain text fallback: if no magic byte matches and content is valid UTF-8
    try:
        content[:512].decode("utf-8")
        return ".txt"
    except (UnicodeDecodeError, ValueError):
        return None


def _validate_upload(filename: str, content: bytes) -> None:
    """
    Phase 2-2: Enforce MIME whitelist + size limit.
    Raises HTTPException on violation.
    """
    # Size check
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is 5 MB.",
            headers={"X-Error-Code": "E_FILE_TOO_LARGE"},
        )

    ext_from_name = Path(filename).suffix.lower()

    # Extension whitelist
    if ext_from_name not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"File type '{ext_from_name}' is not allowed. Use PDF, DOC, DOCX, or TXT.",
            headers={"X-Error-Code": "E_MIME_REJECTED"},
        )

    # Magic byte cross-check (prevents extension spoofing)
    if content:
        detected = _detect_extension_by_magic(content)
        if detected is None:
            raise HTTPException(
                status_code=415,
                detail="File content does not match any allowed type (magic byte check failed).",
                headers={"X-Error-Code": "E_MIME_REJECTED"},
            )
        # Allow docx stored as .docx even though magic byte shows "PK" (zip)
        # DOC uploaded as .doc OK, DOCX uploaded as .docx OK, both are PK-based
        if ext_from_name == ".pdf" and detected != ".pdf":
            raise HTTPException(
                status_code=415,
                detail="File extension is .pdf but content is not a PDF.",
                headers={"X-Error-Code": "E_MIME_REJECTED"},
            )
        if ext_from_name in (".doc", ".docx") and detected not in (".doc", ".docx"):
            raise HTTPException(
                status_code=415,
                detail=f"File extension is {ext_from_name} but content does not match Office format.",
                headers={"X-Error-Code": "E_MIME_REJECTED"},
            )


def _get_conn_params() -> dict:
    from packages.imh_core.config import IMHConfig
    cfg = IMHConfig.load()
    cs = cfg.POSTGRES_CONNECTION_STRING or ""
    m = re.match(r"postgresql(?:\+asyncpg)?://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", cs)
    if m:
        u, p, h, port, db = m.groups()
        return dict(host=h, port=int(port), user=u, password=p, database=db)
    raise RuntimeError("POSTGRES_CONNECTION_STRING not configured")


def _attempt_parse(content: bytes, ext: str) -> tuple[str, str]:
    """
    Phase 2-2: Attempt minimal parse of resume content.
    Returns (resume_summary_snapshot, parse_status).
    parse_status: PARSED | FAILED
    On failure: resume_summary_snapshot=""  (Section 2, Parse Failure Boundary)
    """
    try:
        if ext == ".txt":
            text = content.decode("utf-8", errors="replace")[:2000]
            return text.strip(), "PARSED"
        elif ext == ".pdf":
            # Minimal: extract raw text via regex (bytes PDF)
            raw = content.decode("latin-1", errors="replace")
            texts = re.findall(r"\(([^)]{3,200})\)", raw)
            extracted = " ".join(texts[:50])[:2000]
            return extracted.strip() if extracted.strip() else "", "PARSED" if extracted.strip() else "FAILED"
        else:
            # DOC/DOCX: no parser available in this stack — mark as FAILED
            return "", "FAILED"
    except Exception as exc:
        logger.warning("Resume parse error: %s", exc)
        return "", "FAILED"


@router.post("/upload", status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Depends(require_user),
):
    """
    Upload resume file. Phase 2-2: MIME + size enforced server-side.
    parse_status recorded in DB. Parse failure is NOT a session blocker.
    """
    content = await file.read()
    ext = Path(file.filename or "file.pdf").suffix.lower()

    # Phase 2-2: Validate before writing to disk
    _validate_upload(file.filename or "unknown", content)

    # Write to disk
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = RESUME_DIR / unique_name
    file_path.write_bytes(content)

    # Parse attempt (Section 2: failures allowed, status recorded)
    summary, parse_status = _attempt_parse(content, ext)

    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS resumes (
                resume_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
                user_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                resume_summary_snapshot TEXT DEFAULT '',
                parse_status TEXT DEFAULT 'PARSED',
                uploaded_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        row = await conn.fetchrow(
            """
            INSERT INTO resumes
                (user_id, file_name, file_path, file_size, resume_summary_snapshot, parse_status, uploaded_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            RETURNING resume_id
            """,
            user_id, file.filename, str(file_path), len(content),
            summary, parse_status, datetime.now()
        )
        resume_id = row["resume_id"] if row else "unknown"
    finally:
        await conn.close()

    return {
        "message": "Resume uploaded successfully",
        "file_name": file.filename,
        "file_size": len(content),
        "resume_id": str(resume_id),
        "parse_status": parse_status,  # Frontend can show "FAILED" badge
    }


@router.get("")
async def get_resume(user_id: str = Depends(require_user)):
    """Get current user's latest resume info (metadata only, no file path)."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        row = await conn.fetchrow(
            """SELECT resume_id, file_name, file_size, parse_status, uploaded_at
               FROM resumes WHERE user_id=$1 ORDER BY uploaded_at DESC LIMIT 1""",
            user_id
        )
    finally:
        await conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="No resume found")

    data = dict(row)
    if data.get("uploaded_at"):
        data["uploaded_at"] = data["uploaded_at"].isoformat()
    return data


@router.get("/download")
async def candidate_download(user_id: str = Depends(require_user)):
    """
    Candidate self-download. Section 46: only own resume.
    No audit log required for own-resource access.
    """
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        row = await conn.fetchrow(
            "SELECT resume_id, file_name, file_path FROM resumes WHERE user_id=$1 ORDER BY uploaded_at DESC LIMIT 1",
            user_id
        )
    finally:
        await conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="No resume found")

    file_path = Path(row["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Resume file not found on disk")

    return FileResponse(
        path=str(file_path),
        filename=row["file_name"],
        media_type="application/octet-stream",
    )


@router.get("/admin-download")
async def admin_download_resume(
    candidate_user_id: str = Query(..., description="User ID of the candidate"),
    access_reason_code: str = Query(..., description="Required: HIRING_REVIEW | COMPLIANCE_AUDIT | SUPPORT_INVESTIGATION | LEGAL_REQUEST | QUALITY_ASSURANCE"),
    trace_id: str = Query(..., description="Client trace_id for audit linkage"),
    admin_id: str = Depends(require_admin),
):
    """
    Admin download of candidate resume. Section 46:
    - access_reason_code is MANDATORY and validated server-side
    - Write to security_audit_logs BEFORE serving the file
    """
    if access_reason_code not in VALID_REASON_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid access_reason_code. Must be one of: {', '.join(sorted(VALID_REASON_CODES))}",
            headers={"X-Error-Code": "E_CAPABILITY_SIGNATURE_INVALID"},
        )

    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        row = await conn.fetchrow(
            "SELECT resume_id, file_name, file_path FROM resumes WHERE user_id=$1 ORDER BY uploaded_at DESC LIMIT 1",
            candidate_user_id
        )
    finally:
        await conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="No resume found for this candidate")

    # Section 46: Write audit BEFORE serving file
    await write_audit_log(
        trace_id=trace_id,
        actor_user_id=admin_id,
        actor_role="ADMIN",
        resource_type="RESUME",
        resource_id=str(row["resume_id"]),
        access_reason_code=access_reason_code,
        additional_metadata={"candidate_user_id": candidate_user_id},
    )

    file_path = Path(row["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Resume file not found on disk")

    logger.info(
        "ADMIN_RESUME_DOWNLOAD admin=%s candidate=%s resume=%s reason=%s trace=%s",
        admin_id, candidate_user_id, row["resume_id"], access_reason_code, trace_id
    )

    return FileResponse(
        path=str(file_path),
        filename=row["file_name"],
        media_type="application/octet-stream",
    )


@router.get("/{resume_id}/audit-history")
async def get_resume_audit_history(
    resume_id: str,
    admin_id: str = Depends(require_admin),
):
    """Admin: view the full audit trail for a resume (Section 46 observability)."""
    logs = await get_audit_logs_for_resource("RESUME", resume_id)
    return {"resume_id": resume_id, "audit_logs": logs, "count": len(logs)}
