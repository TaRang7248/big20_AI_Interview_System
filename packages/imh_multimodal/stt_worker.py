"""
TASK-M Sprint 3: STT Worker (plan §4.1, §4.4-STT, §4.5-STT)

Responsibility:
  - Consume audio messages from Redis Streams (XREADGROUP).
  - Acquire GPU mutex (LLM > STT priority).
  - Analyze audio with Faster-Whisper (Finalized segment only).
  - Normalize stt_confidence.
  - Return observation dict for Persistence Worker.

Data rules (plan §4.4-STT, §9.2):
  - DB: only Finalized segments stored (no partials).
  - Partial transcript: Redis Projection Cache ONLY, TTL 10s.
  - STT text: NEVER stored in PostgreSQL (security contract).
  - PII masking: Regex → Truncate 100 chars → "" on failure.
  - After turn FINALIZED state: Drop any arriving STT results.
  - stt_confidence: average confidence of the finalized segment.
  - Turn-unit file strategy: analyze full file from start on re-attempt.

OOM handling (plan §11.1 GPU Failure Mode Matrix):
  - CUDA OOM → immediately Deactivate STT Worker for the session.
  - Redis oom_count_stt incremented on each OOM event.
  - No VRAM re-allocation attempts.

Sprint 3 status: STUB — Faster-Whisper call is a no-op placeholder.
                 Real integration wired once GPU Mutex tests pass.
"""
from __future__ import annotations
import logging
import re
from typing import Optional

from packages.imh_multimodal.normalizer import normalize, DEFAULT_PROFILE_ID
from packages.imh_multimodal.signal_id import generate_signal_id
from packages.imh_multimodal.redis_streams import (
    OOM_COUNT_STT_KEY,
    stt_partial_key,
)
from packages.imh_multimodal.mm_flags import MMFlags

logger = logging.getLogger("imh.multimodal.stt_worker")

# PII masking patterns (plan §9.2 — deterministic rule)
_PII_PATTERNS = [
    re.compile(r"\b\d{2,4}-\d{3,4}-\d{4}\b"),          # phone
    re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}"),  # email
    re.compile(r"\b\d{6}-\d{7}\b"),                      # resident ID
]
_MAX_PROJECTION_LEN = 100  # L chars, plan §9.2


def _mask_pii(text: str) -> str:
    """
    Deterministic PII masking: Regex replace → Truncate to L chars.
    Returns "" on any exception (plan §9.2 fail-safe).
    """
    try:
        masked = text
        for pat in _PII_PATTERNS:
            masked = pat.sub("[MASKED]", masked)
        return masked[:_MAX_PROJECTION_LEN]
    except Exception:
        return ""


def _push_partial_to_projection(
    redis_client,
    session_id: str,
    partial_text: str,
) -> None:
    """
    Store masked partial transcript in Redis Projection Cache (TTL 10s).
    This is the ONLY place STT text is stored — Projection-only, volatile.
    """
    try:
        masked = _mask_pii(partial_text)
        key = stt_partial_key(session_id)
        redis_client.set(key, masked, ex=MMFlags.MM_STT_PARTIAL_TTL)
    except Exception:
        logger.warning("Partial STT push failed (non-fatal): session=%s", session_id, exc_info=True)


def process_stt(
    message: dict,
    redis_client=None,
    gpu_mutex_manager=None,
    turn_finalized: bool = False,
) -> Optional[dict]:
    """
    Process one STT analysis request from the Redis Streams payload.

    Args:
        message:           Stream payload dict.
        redis_client:      Redis client (for projection + OOM counter).
        gpu_mutex_manager: GPUMutexManager instance (for mutex acquire).
        turn_finalized:    True if turn is already FINALIZED → Drop.

    Returns:
        Observation dict if analysis produced a finalized result.
        None if skipped (mutex unavailable, OOM, turn finalized, etc.).

    Contract:
        - Text NEVER returned in the observation dict (numeric only).
        - stt_confidence = average confidence of finalized segments.
    """
    session_id = message["session_id"]

    # Drop after turn FINALIZED (plan §4.4-STT Drop Logic)
    if turn_finalized:
        logger.debug("STT: turn finalized — dropping late result for session=%s", session_id)
        return None

    turn_index = int(message["turn_index"])
    ts_offset = float(message.get("ts", 0.0))
    profile_id = message.get("profile_id", DEFAULT_PROFILE_ID)
    session_profile_id = message.get("session_profile_id")

    # Acquire GPU mutex (STT path)
    if gpu_mutex_manager is not None:
        acquired = gpu_mutex_manager.try_acquire_stt()
        if not acquired:
            logger.debug("STT: mutex not acquired — skipping turn=%d session=%s", turn_index, session_id)
            return None

    try:
        # Real Faster-Whisper transcription
        avg_confidence: Optional[float] = None
        finalized_text: Optional[str] = None

        artifact = message.get("buffer_ref_id") or message.get("artifact_id")
        if artifact:
            try:
                from faster_whisper import WhisperModel  # type: ignore
                import os

                model_size = os.environ.get("WHISPER_MODEL_SIZE", "large-v3-turbo")
                device = os.environ.get("WHISPER_DEVICE", "cuda")
                compute_type = os.environ.get("WHISPER_COMPUTE_TYPE", "int8_float16")

                # Model is kept resident in VRAM (plan §11 — no reload).
                # Global singleton pattern prevents repeated instantiation.
                if not hasattr(process_stt, "_model"):
                    process_stt._model = WhisperModel(
                        model_size, device=device, compute_type=compute_type
                    )

                segments, _info = process_stt._model.transcribe(
                    artifact,
                    beam_size=5,
                    language="ko",
                    condition_on_previous_text=False,
                )
                seg_list = list(segments)   # materialise generator

                if seg_list:
                    import statistics
                    # avg_logprob is negative; convert to a 0-1 confidence proxy
                    log_probs = [s.avg_logprob for s in seg_list if s.avg_logprob is not None]
                    if log_probs:
                        # exp(avg_logprob) gives a rough probability in (0, 1]
                        import math
                        avg_confidence = float(statistics.mean(math.exp(lp) for lp in log_probs))
                    finalized_text = " ".join(s.text.strip() for s in seg_list)

            except MemoryError:
                raise   # Re-raise so outer except MemoryError catches it below
            except Exception as exc:
                logger.warning("Faster-Whisper transcription failed (fallback Neutral): %s", exc)

        # Push masked partial to Projection Cache (non-blocking)
        if finalized_text and redis_client:
            _push_partial_to_projection(redis_client, session_id, finalized_text)

        # Build numeric-only observation (text blocked from DB, plan §9.2)
        norm_conf = normalize("stt_confidence", avg_confidence, profile_id, session_profile_id)
        sig = generate_signal_id(session_id, turn_index, "STT", 1, "stt_confidence")

        return {
            "session_id": session_id,
            "turn_index": turn_index,
            "chunk_seq": 1,    # STT: turn-level, always chunk_seq=1 (plan §3.2)
            "signal_id": sig,
            "modality": "STT",
            "metric_key": "stt_confidence",
            "timestamp_offset": ts_offset,
            "normalized_value": norm_conf,
            "extra_payload": None,
            # text intentionally excluded
        }

    except MemoryError:
        # CUDA OOM path (plan §11.1)
        logger.error("STT Worker CUDA OOM for session=%s — deactivating STT", session_id)
        if redis_client:
            try:
                redis_client.incr(OOM_COUNT_STT_KEY)
            except Exception:
                pass
        return None

    finally:
        if gpu_mutex_manager is not None:
            gpu_mutex_manager.release()
