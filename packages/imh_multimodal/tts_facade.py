"""
TASK-M Sprint 2: gTTS facade (plan §5)

Design:
  - Non-blocking: never runs on the WebRTC main thread.
  - Timeout: configurable, default 8 seconds.
  - Fallback: on any failure, returns None (Text-only mode in UI).
  - Caching: keyed on hash(question_text). Cache is volatile (in-memory dict).
  - Endpoint served by: GET /api/v1/sessions/{id}/multimodal/tts?turn_index={n}

Authority contract:
  - gTTS output (MP3 bytes) is ephemeral — not persisted to PostgreSQL.
  - No STT/multimodal data dependency; purely a TTS convenience layer.

If MM_ENABLE_TTS=False (default), tts_generate() returns None immediately.
"""
from __future__ import annotations
import hashlib
import io
import logging
import threading
from typing import Optional

from packages.imh_multimodal.mm_flags import MMFlags

logger = logging.getLogger("imh.multimodal.tts")

# In-memory cache: hash(text) → MP3 bytes
_cache: dict[str, bytes] = {}
_cache_lock = threading.Lock()

_TTS_TIMEOUT_SEC = 8


def tts_generate(
    question_text: str,
    lang: str = "ko",
    timeout: int = _TTS_TIMEOUT_SEC,
) -> Optional[bytes]:
    """
    Generate MP3 audio for the given question text using gTTS.

    Returns:
        MP3 bytes on success.
        None if TTS is disabled, generation failed, or timed out.
    """
    if not MMFlags.tts_active():
        return None

    # Cache lookup
    cache_key = hashlib.sha256(question_text.encode()).hexdigest()
    with _cache_lock:
        if cache_key in _cache:
            logger.debug("TTS cache hit for key=%s", cache_key[:8])
            return _cache[cache_key]

    # Generate in a thread to enforce timeout (non-blocking contract)
    result: list[Optional[bytes]] = [None]

    def _generate():
        try:
            from gtts import gTTS  # type: ignore
            buf = io.BytesIO()
            tts = gTTS(text=question_text, lang=lang)
            tts.write_to_fp(buf)
            result[0] = buf.getvalue()
        except Exception as exc:
            logger.warning("gTTS generation failed: %s — Fallback to Text-only", exc)

    thread = threading.Thread(target=_generate, daemon=True, name="gtts-gen")
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        logger.warning("gTTS timed out after %ds — Fallback to Text-only", timeout)
        return None

    if result[0] is not None:
        with _cache_lock:
            _cache[cache_key] = result[0]

    return result[0]
