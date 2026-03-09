"""
TASK-M Sprint 4: Multimodal API Router (plan §5, §10, §4.4)

Endpoints:
  POST /api/v1/sessions/{session_id}/multimodal/webrtc/offer
       Accepts SDP offer → returns SDP answer (Full SDP Exchange, plan §4.4).
       MVP: Trickle ICE disabled. TURN server not supported (Phase 2).
       Returns HTTP 429 if concurrent session limit exceeded.
       Returns HTTP 503 if aiortc not available.

  GET  /api/v1/sessions/{session_id}/multimodal/projection
       Polling-based Read-only Projection snapshot (plan §10).

  GET  /api/v1/sessions/{session_id}/multimodal/stream
       SSE push endpoint. Publishes from Redis Pub/Sub (plan §10).

  GET  /api/v1/sessions/{session_id}/multimodal/tts?turn_index={n}
       Returns MP3 bytes from gTTS cache or live generation (plan §5).

Design constraints (plan §4.4 MVP):
  - No Trickle ICE.
  - No TURN server.
  - Max concurrent sessions: MMFlags.MM_WEBRTC_MAX_SESSIONS (5).
  - WebRTC session is strictly optional: mm_flags.webrtc_active() → False skips.
  - Isolation: this router MUST NOT access jobs, interviews, or evaluation_scores
    tables directly. Read-only Projection via Redis only.
"""
from __future__ import annotations
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Response, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from packages.imh_multimodal.mm_flags import MMFlags
from packages.imh_multimodal.redis_streams import (
    projection_key,
    ACTIVE_SESSIONS_KEY,
    GPU_MUTEX_KEY,
)

logger = logging.getLogger("imh.multimodal.api")

router = APIRouter(
    prefix="/sessions",
    tags=["Multimodal"],
)


# ------------------------------------------------------------------ #
# Pydantic schemas                                                     #
# ------------------------------------------------------------------ #

class WebRTCOfferRequest(BaseModel):
    sdp: str
    type: str   # "offer"


class WebRTCAnswerResponse(BaseModel):
    sdp: str
    type: str   # "answer"


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _get_redis():
    from packages.imh_core.infra.redis import RedisClient
    return RedisClient.get_instance()


# ------------------------------------------------------------------ #
# POST /sessions/{session_id}/multimodal/webrtc/offer                 #
# ------------------------------------------------------------------ #

@router.post("/{session_id}/multimodal/webrtc/offer", response_model=WebRTCAnswerResponse)
async def webrtc_offer(session_id: str, req: WebRTCOfferRequest):
    """
    WebRTC Signaling: Full SDP Exchange (plan §4.4).

    MVP constraints:
      - Trickle ICE not supported.
      - TURN server not provided (Phase 2 scope).
      - NAT Traversal may fail in restrictive environments.

    If MM_ENABLE_WEBRTC=False, returns 503 (feature disabled).
    If active session count ≥ MM_WEBRTC_MAX_SESSIONS, returns 429.
    """
    if not MMFlags.webrtc_active():
        raise HTTPException(
            status_code=503,
            detail="WebRTC not enabled. Set MM_ENABLE=true and MM_ENABLE_WEBRTC=true.",
        )

    # Session concurrency gate (Section 11 / Phase 3-FIX-D)
    r = _get_redis()
    import uuid as _uuid
    _trace = f"tr-{_uuid.uuid4().hex[:16]}"
    
    # LUA: atomic check and increment - Section 4.1
    lua_incr = """
    local current = redis.call('GET', KEYS[1]) or '0'
    if tonumber(current) >= tonumber(ARGV[1]) then
        return -1
    else
        return redis.call('INCR', KEYS[1])
    end
    """
    active = r.register_script(lua_incr)(keys=[ACTIVE_SESSIONS_KEY], args=[MMFlags.MM_WEBRTC_MAX_SESSIONS])
    
    if active == -1:
        raise HTTPException(
            status_code=429,
            detail=f"WebRTC session limit reached ({MMFlags.MM_WEBRTC_MAX_SESSIONS} max). Retry when a session slot is free.",
            headers={
                "X-Error-Code": "E_GPU_QUEUE_LIMIT",
                "X-Trace-Id": _trace,
                "Retry-After": "30",
            },
        )
    
    # Standard header for 503 - Phase 3-FIX-E
    try:
        from aiortc import RTCPeerConnection, RTCSessionDescription  # type: ignore
    except ImportError:
        # Atomic rollback of the counter on failure
        r.decr(ACTIVE_SESSIONS_KEY)
        raise HTTPException(
            status_code=503,
            detail="aiortc not installed. WebRTC unavailable.",
            headers={
                "X-Error-Code": "E_WEBRTC_DISABLED",
                "X-Trace-Id": _trace,
            }
        )
    
    pc = RTCPeerConnection()
    try:
        offer = RTCSessionDescription(sdp=req.sdp, type=req.type)
        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
    except Exception as e:
        logger.error("WebRTC offer processing failed session_id=%s trace=%s: %s", session_id, _trace, e)
        # Atomic rollback of the counter on failure
        r.decr(ACTIVE_SESSIONS_KEY)
        raise HTTPException(
            status_code=500,
            detail=f"WebRTC Signaling Failed: {str(e)}",
            headers={
                "X-Error-Code": "E_WEBRTC_FAILED",
                "X-Trace-Id": _trace,
            }
        )

    logger.info("WebRTC offer processed for session_id=%s", session_id)
    return WebRTCAnswerResponse(
        sdp=pc.localDescription.sdp,
        type=pc.localDescription.type,
    )


# ------------------------------------------------------------------ #
# GET /sessions/{session_id}/multimodal/projection                     #
# ------------------------------------------------------------------ #

@router.get("/{session_id}/multimodal/projection")
def get_projection(session_id: str):
    """
    Read-only Projection Cache snapshot (plan §10).

    Returns the current multimodal state for the session.
    Non-authoritative: for UI display only.
    Authority = PostgreSQL.
    """
    r = _get_redis()
    key = projection_key(session_id)
    data = r.hgetall(key)

    if not data:
        return {
            "session_id": session_id,
            "inactive": True,
            "metrics": {},
            "note": "No active projection data. Session may be inactive.",
        }

    # Parse metric fields: "{MODALITY}:{metric_key}:{turn_index}" -> value
    metrics: dict = {}
    for field, value in data.items():
        parts = field.split(":", 2)
        if len(parts) == 3:
            modality, metric_key, turn = parts
            metrics.setdefault(modality, {})[f"{metric_key}@turn{turn}"] = float(value)

    return {
        "session_id": session_id,
        "inactive": False,
        "metrics": metrics,
    }


# ------------------------------------------------------------------ #
# GET /sessions/{session_id}/multimodal/stream   (SSE)                #
# ------------------------------------------------------------------ #

@router.get("/{session_id}/multimodal/stream")
async def projection_stream(
    session_id: str,
    last_event_id: str = Query(None, alias="lastEventId"),
):
    """
    Server-Sent Events push for real-time multimodal updates (plan §10).

    Uses Redis Pub/Sub channel: mm:pubsub:{session_id}

    event_seq Contract (Section 37 / Implementation Plan SSE Guard):
    - Each event carries `event_seq` in BOTH the SSE `id:` field AND the JSON data body.
    - The `id:` field enables Last-Event-ID reconnection.
    - The JSON `event_seq` enables client-side inversion detection.
    - On reconnect, client sends `lastEventId` query param; server notes the gap.
    - Gap events beyond a threshold → client must fallback to GET /projection.

    Client guard:
    - If received event_seq <= last_seen_seq: discard the event and trigger authority pull.
    - If gap (received_seq - last_seen_seq) > 1: trigger authority pull, then resume SSE.
    """
    import asyncio
    r = _get_redis()
    channel = f"mm:pubsub:{session_id}"
    pubsub = r.pubsub()
    pubsub.subscribe(channel)

    # Resolve starting seq from Last-Event-ID (reconnect continuity)
    start_seq = 0
    if last_event_id:
        try:
            start_seq = int(last_event_id)
            logger.info(
                "SSE reconnect session=%s last_event_id=%s (gap detection active)",
                session_id, last_event_id
            )
        except (TypeError, ValueError):
            pass

    async def event_generator():
        import json as _json
        import asyncio
        event_seq = start_seq
        try:
            while True:
                message = pubsub.get_message(ignore_subscribe_messages=True)
                if message and message["type"] == "message":
                    event_seq += 1
                    raw = message["data"]

                    # Embed event_seq in JSON payload for client-side inversion guard
                    try:
                        payload = _json.loads(raw) if isinstance(raw, (str, bytes)) else {}
                    except Exception:
                        payload = {"raw": str(raw)}

                    payload["event_seq"] = event_seq
                    payload["session_id"] = session_id

                    data_str = _json.dumps(payload)
                    # SSE id: field = event_seq (enables Last-Event-ID)
                    yield f"id: {event_seq}\nevent: projection\ndata: {data_str}\n\n"
                else:
                    await asyncio.sleep(0.1)
        except GeneratorExit:
            pass
        finally:
            pubsub.unsubscribe(channel)
            pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ------------------------------------------------------------------ #
# GET /sessions/{session_id}/multimodal/tts                            #
# ------------------------------------------------------------------ #

@router.get("/{session_id}/multimodal/tts")
def get_tts(
    session_id: str,
    turn_index: int = Query(0, description="Turn index for cache key disambiguation"),
    text: str = Query("", description="Question text to synthesize"),
):
    """
    gTTS endpoint (plan §5).

    Returns MP3 binary on success.
    Returns 204 (No Content) if TTS is disabled or generation failed.
    This endpoint MUST NOT block the WebRTC main flow.
    """
    if not MMFlags.tts_active():
        return Response(status_code=204)

    if not text:
        return Response(status_code=400)

    from packages.imh_multimodal.tts_facade import tts_generate
    mp3_bytes = tts_generate(text)

    if mp3_bytes is None:
        return Response(status_code=204)

    return Response(
        content=mp3_bytes,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": (
                f'attachment; filename="question_{session_id}_t{turn_index}.mp3"'
            )
        },
    )
