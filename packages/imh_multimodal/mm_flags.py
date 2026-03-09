"""
TASK-M: Multimodal Feature Flags

Design mirrors existing WiringFlags in packages/imh_core/wiring_flags.py.
All flags default to False for safety. Enable via environment variables.

Usage:
    from packages.imh_multimodal.mm_flags import MMFlags
    if MMFlags.MM_ENABLE_WEBRTC:
        ...

Environment matrix:
    DEV (Live MVP):  MM_ENABLE_WEBRTC=true, MM_ENABLE_TTS=true
    DEV (Storage):   leave all False, pipeline persist-only
    PROD (Initial):  all False (data collection only)
    PROD (Stable):   MM_ENABLE_WEBRTC=true, MM_ENABLE_TTS=true,
                     MM_ENABLE_EVAL_INTEGRATION=true
"""
import os


def _bool_env(key: str, default: bool = False) -> bool:
    """Parse boolean env var the same way as WiringFlags."""
    val = os.environ.get(key, "").strip().lower()
    if val in ("1", "true", "yes"):
        return True
    if val in ("0", "false", "no"):
        return False
    return default


class MMFlags:
    """
    Master gate: MM_ENABLE
      When False -> all multimodal processing is OFF (no-op).
      When True  -> sub-flags are evaluated individually.

    Sub-flags:
      MM_ENABLE_WEBRTC         - Real-time WebRTC audio/video streaming
      MM_ENABLE_TTS            - gTTS interviewer voice synthesis
      MM_ENABLE_PDF_TEXT       - PDF resume text extraction + prompt injection
      MM_ENABLE_EVAL_INTEGRATION - Multimodal metrics fed into EvaluationEngine
                                  (Phase 2, Default: False)
    Constraints (hardcoded, plan §7):
      MM_WEBRTC_MAX_SESSIONS   - max concurrent WebRTC sessions (GTX 1660s limit)
      MM_MUTEX_QUEUE_MAX       - gpu_mutex wait queue depth limit
      MM_STREAMS_MAXLEN        - global Redis Streams MAXLEN
    """

    # Master gate
    MM_ENABLE: bool = _bool_env("MM_ENABLE", default=False)

    # Sub-flags (all default False for safety)
    MM_ENABLE_WEBRTC: bool = _bool_env("MM_ENABLE_WEBRTC", default=False)
    MM_ENABLE_TTS: bool = _bool_env("MM_ENABLE_TTS", default=False)
    MM_ENABLE_PDF_TEXT: bool = _bool_env("MM_ENABLE_PDF_TEXT", default=False)
    MM_ENABLE_EVAL_INTEGRATION: bool = _bool_env("MM_ENABLE_EVAL_INTEGRATION", default=False)

    # Schema/profile mismatch handling
    MM_FAILFAST_ON_SCHEMA_MISMATCH: bool = _bool_env(
        "MM_FAILFAST_ON_SCHEMA_MISMATCH", default=True
    )

    # Hardcoded resource limits (plan §7, GTX 1660 Super 6GB constraints)
    MM_WEBRTC_MAX_SESSIONS: int = int(os.environ.get("MM_WEBRTC_MAX_SESSIONS", "5"))
    MM_MUTEX_QUEUE_MAX: int = int(os.environ.get("MM_MUTEX_QUEUE_MAX", "10"))
    MM_STREAMS_MAXLEN: int = int(os.environ.get("MM_STREAMS_MAXLEN", "10000"))

    # STT Projection Cache TTL for Partial transcripts (seconds)
    MM_STT_PARTIAL_TTL: int = int(os.environ.get("MM_STT_PARTIAL_TTL", "10"))

    # Temp file TTL (seconds); enforced by cleanup scheduler
    MM_TEMP_FILE_TTL: int = int(os.environ.get("MM_TEMP_FILE_TTL", "300"))

    # Evaluation flush wait before timing-out to Neutral(0.5)
    MM_FLUSH_WAIT_SEC: int = int(os.environ.get("MM_FLUSH_WAIT_SEC", "3"))

    # ------------------------------------------------------------------ #
    # Convenience helpers (mirror WiringFlags.weight_sync_active pattern)  #
    # ------------------------------------------------------------------ #

    @classmethod
    def webrtc_active(cls) -> bool:
        """WebRTC streaming is active only when master + sub-flag both True."""
        return cls.MM_ENABLE and cls.MM_ENABLE_WEBRTC

    @classmethod
    def tts_active(cls) -> bool:
        return cls.MM_ENABLE and cls.MM_ENABLE_TTS

    @classmethod
    def pdf_text_active(cls) -> bool:
        return cls.MM_ENABLE and cls.MM_ENABLE_PDF_TEXT

    @classmethod
    def eval_integration_active(cls) -> bool:
        return cls.MM_ENABLE and cls.MM_ENABLE_EVAL_INTEGRATION
