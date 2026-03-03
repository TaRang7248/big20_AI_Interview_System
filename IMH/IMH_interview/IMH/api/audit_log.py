"""
Security Audit Logger (Implementation Plan - Section 46, 47)

Central audit logging module shared across API routers.
Writes to security_audit_logs table (or creates it if missing).

Mandatory fields per Section 46:
- trace_id
- actor_user_id
- actor_role
- resource_type
- resource_id
- access_reason_code
- created_at
"""

import logging
import re
from datetime import datetime
from typing import Optional

logger = logging.getLogger("imh.audit")


def _get_conn_params() -> dict:
    from packages.imh_core.config import IMHConfig
    cfg = IMHConfig.load()
    cs = cfg.POSTGRES_CONNECTION_STRING or ""
    m = re.match(r"postgresql(?:\+asyncpg)?://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", cs)
    if m:
        u, p, h, port, db = m.groups()
        return dict(host=h, port=int(port), user=u, password=p, database=db)
    raise RuntimeError("POSTGRES_CONNECTION_STRING not configured")


# Valid resource_type values (Section 46)
RESOURCE_TYPES = {
    "RESUME": "RESUME",
    "INTERVIEW_RECORDING": "INTERVIEW_RECORDING",
    "EVALUATION_REPORT": "EVALUATION_REPORT",
}

# Valid access_reason_code values admin must supply (Section 46)
VALID_REASON_CODES = {
    "HIRING_REVIEW",
    "COMPLIANCE_AUDIT",
    "SUPPORT_INVESTIGATION",
    "LEGAL_REQUEST",
    "QUALITY_ASSURANCE",
}


async def write_audit_log(
    *,
    trace_id: str,
    actor_user_id: str,
    actor_role: str,  # ADMIN | CANDIDATE
    resource_type: str,
    resource_id: str,
    access_reason_code: str,
    additional_metadata: Optional[dict] = None,
) -> bool:
    """
    Write an audit record to security_audit_logs.
    Returns True on success, False on failure (non-blocking).
    Never raises exceptions — audit failure must never block the request.
    """
    import asyncpg  # type: ignore
    import json

    try:
        params = _get_conn_params()
        conn = await asyncpg.connect(**params)
        try:
            # Ensure audit log table exists (self-creating for portability)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS security_audit_logs (
                    id SERIAL PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    actor_user_id TEXT NOT NULL,
                    actor_role TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    access_reason_code TEXT NOT NULL,
                    additional_metadata JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            await conn.execute(
                """
                INSERT INTO security_audit_logs
                    (trace_id, actor_user_id, actor_role, resource_type, resource_id, access_reason_code, additional_metadata, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                trace_id,
                actor_user_id,
                actor_role,
                resource_type,
                resource_id,
                access_reason_code,
                json.dumps(additional_metadata) if additional_metadata else None,
                datetime.now(),
            )
            logger.info(
                "AUDIT_LOG trace=%s actor=%s role=%s resource=%s/%s reason=%s",
                trace_id, actor_user_id, actor_role, resource_type, resource_id, access_reason_code
            )
            return True
        finally:
            await conn.close()
    except Exception as exc:
        logger.error("AUDIT_LOG_FAILURE: failed to write audit record. exc=%s", exc)
        return False


async def get_audit_logs_for_resource(resource_type: str, resource_id: str, limit: int = 50) -> list:
    """Retrieve audit history for a specific resource (Admin review)."""
    import asyncpg  # type: ignore

    try:
        params = _get_conn_params()
        conn = await asyncpg.connect(**params)
        try:
            rows = await conn.fetch(
                """
                SELECT trace_id, actor_user_id, actor_role, resource_type,
                       resource_id, access_reason_code, additional_metadata, created_at
                FROM security_audit_logs
                WHERE resource_type=$1 AND resource_id=$2
                ORDER BY created_at DESC LIMIT $3
                """,
                resource_type, resource_id, limit
            )
            return [
                {
                    "trace_id": r["trace_id"],
                    "actor_user_id": r["actor_user_id"],
                    "actor_role": r["actor_role"],
                    "resource_type": r["resource_type"],
                    "resource_id": r["resource_id"],
                    "access_reason_code": r["access_reason_code"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in rows
            ]
        finally:
            await conn.close()
    except Exception as exc:
        logger.error("AUDIT_LOG_READ_FAILURE: %s", exc)
        return []
