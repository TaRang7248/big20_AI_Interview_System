"""
TASK-M Sprint 1: Redis Streams configuration and key constants.

Defines all Redis key namespaces and Stream names used by the
multimodal pipeline. Centralising here prevents typo-related bugs
and makes stream names easy to audit.

Authority contracts (plan §7, §8):
  - Streams use XTRIM MAXLEN (not TTL) for retention.
  - Per-session frame limits: Video 1,000 frames, Audio 500 chunks.
  - Global MAXLEN: 10,000 (MM_STREAMS_MAXLEN).
  - Workers enqueue via XADD, acknowledge via XACK after PG COMMIT.
"""
from packages.imh_multimodal.mm_flags import MMFlags


# ------------------------------------------------------------------ #
# Stream names (producer/consumer groups)                              #
# ------------------------------------------------------------------ #
STREAM_AUDIO = "stream:multimodal:raw:audio"
STREAM_VIDEO = "stream:multimodal:raw:video"

# Consumer group name shared by all multimodal workers
CONSUMER_GROUP = "cg_multimodal_workers"


# ------------------------------------------------------------------ #
# Projection Cache key helpers (plan §10)                              #
# The Projection Cache is Read-only, volatile, and non-authoritative. #
# All keys carry a 5-minute inactivity TTL.                           #
# ------------------------------------------------------------------ #
PROJECTION_TTL_SEC = 300  # 5 minutes inactivity TTL


def projection_key(session_id: str) -> str:
    """Redis hash key for a session's real-time projection cache."""
    return f"mm:projection:{session_id}"


def stt_partial_key(session_id: str) -> str:
    """Redis key for STT partial transcript (TTL 10 s)."""
    return f"mm:stt:partial:{session_id}"


# ------------------------------------------------------------------ #
# GPU Mutex key (plan §4.1)                                            #
# ------------------------------------------------------------------ #
GPU_MUTEX_KEY = "lock:gpu_mutex"
GPU_MUTEX_TTL_SEC = 10       # heartbeat-protected TTL
GPU_MUTEX_HEARTBEAT_SEC = 3  # renewal interval

# LLM yield-request signal key (written by LLM Dispatcher,
# read by STT Worker at heartbeat to trigger cooperative yield).
LLM_YIELD_REQUEST_KEY = "signal:gpu:llm_wants_lock"


# ------------------------------------------------------------------ #
# OOM counters (plan §11.1 GPU Failure Mode Matrix)                    #
# ------------------------------------------------------------------ #
OOM_COUNT_STT_KEY = "mm:oom_count_stt"
OOM_COUNT_LLM_KEY = "mm:oom_count_llm"


# ------------------------------------------------------------------ #
# Per-session concurrent session counter (plan §11)                    #
# ------------------------------------------------------------------ #
ACTIVE_SESSIONS_KEY = "mm:active_webrtc_sessions"


# ------------------------------------------------------------------ #
# Stream retention helpers                                             #
# ------------------------------------------------------------------ #
def trim_stream(redis_client, stream_name: str) -> None:
    """
    Trim a stream to the global MAXLEN limit.
    Called by Persistence Worker after each Turn finalisation.
    """
    redis_client.xtrim(stream_name, maxlen=MMFlags.MM_STREAMS_MAXLEN, approximate=True)


def ensure_consumer_group(redis_client, stream_name: str) -> None:
    """
    Idempotent: create consumer group if it does not already exist.
    Called once at worker startup.
    """
    try:
        redis_client.xgroup_create(stream_name, CONSUMER_GROUP, id="0", mkstream=True)
    except Exception as exc:
        # BUSYGROUP: group already exists — this is always acceptable
        if "BUSYGROUP" not in str(exc):
            raise
