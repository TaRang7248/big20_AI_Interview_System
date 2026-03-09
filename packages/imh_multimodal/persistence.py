"""
TASK-M Sprint 2: Persistence Worker (plan §7.1, §8, §10)

Responsibility:
  1. Receive analysis results from CPU/GPU Workers (dict payload).
  2. Insert into multimodal_observations (Append-only, ON CONFLICT DO NOTHING).
  3. After successful PG COMMIT → XACK the Redis Stream message.
  4. After successful PG COMMIT → update Redis Projection Cache (plan §10).
  5. XACK failure → PEL recovery on next restart (at-least-once → exactly-once via UNIQUE).
  6. Temp file cleanup after processing (5-min TTL scheduler is separate).

Authority contracts:
  - DB COMMIT = the ONLY definition of "Authoritative Complete" (plan §7.1).
  - Projection update MUST come AFTER successful COMMIT (plan §10).
  - No Write-Back to authority (interviews / evaluation_scores) — EVER.
  - Worker MUST NOT read or modify session state or snapshots.
"""
from __future__ import annotations
import json
import logging
import uuid
from typing import Any, Optional

logger = logging.getLogger("imh.multimodal.persistence")


def build_insert_params(
    session_id: str,
    turn_index: int,
    chunk_seq: int,
    signal_id: str,
    modality: str,
    metric_key: str,
    timestamp_offset: float,
    normalized_value: float,
    extra_payload: Optional[dict] = None,
) -> tuple:
    """
    Build the parameter tuple for: INSERT INTO multimodal_observations ...

    payload JSONB format:
      {"value": <float 0-1>}  plus optional extra fields

    Returns: tuple matching (session_id, turn_index, chunk_seq, signal_id,
             modality, metric_key, timestamp_offset, payload_json)
    """
    payload: dict[str, Any] = {"value": round(normalized_value, 6)}
    if extra_payload:
        payload.update(extra_payload)

    return (
        uuid.UUID(session_id),   # cast str → UUID for pg UUID column
        turn_index,
        chunk_seq,
        uuid.UUID(signal_id),
        modality.upper(),
        metric_key,
        timestamp_offset,
        json.dumps(payload),
    )


INSERT_SQL = """
    INSERT INTO multimodal_observations
        (session_id, turn_index, chunk_seq, signal_id,
         modality, metric_key, timestamp_offset, payload)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
    ON CONFLICT (signal_id) DO NOTHING
"""


async def persist_observation(
    conn,           # asyncpg connection
    session_id: str,
    turn_index: int,
    chunk_seq: int,
    signal_id: str,
    modality: str,
    metric_key: str,
    timestamp_offset: float,
    normalized_value: float,
    extra_payload: Optional[dict] = None,
) -> bool:
    """
    Insert one normalised observation row.

    Returns:
        True  — row inserted (new unique signal_id).
        False — silently ignored (duplicate signal_id, idempotent).

    Contract: caller must XACK the Redis Stream message ONLY after this
    function returns without error (success or duplicate‑skip).
    """
    params = build_insert_params(
        session_id, turn_index, chunk_seq, signal_id,
        modality, metric_key, timestamp_offset, normalized_value, extra_payload,
    )
    try:
        status = await conn.execute(INSERT_SQL, *params)
        # asyncpg returns "INSERT 0 0" for DO NOTHING
        inserted = status.endswith("INSERT 0 1")
        if not inserted:
            logger.debug(
                "Duplicate signal_id skipped (idempotent): %s", signal_id
            )
        return inserted
    except Exception:
        logger.exception(
            "persist_observation failed: session=%s turn=%d sig=%s metric=%s",
            session_id, turn_index, signal_id, metric_key,
        )
        raise


def update_projection_cache(
    redis_client,
    session_id: str,
    turn_index: int,
    modality: str,
    metric_key: str,
    normalized_value: float,
    projection_ttl: int = 300,
) -> None:
    """
    Update the Redis Projection Cache AFTER PG COMMIT (plan §10).

    Key: mm:projection:{session_id}  (Hash)
    Field: {modality}:{metric_key}:{turn_index}
    Value: normalized float string

    This is a best-effort push. If it fails, SSE clients fall back to
    Projection Polling to re-sync (plan §10 Recovery Sequence).
    """
    from packages.imh_multimodal.redis_streams import projection_key
    key = projection_key(session_id)
    field = f"{modality.upper()}:{metric_key}:{turn_index}"
    try:
        redis_client.hset(key, field, str(round(normalized_value, 6)))
        redis_client.expire(key, projection_ttl)
    except Exception:
        logger.warning(
            "Projection cache update failed (non-fatal): session=%s field=%s",
            session_id, field, exc_info=True,
        )
