"""
Track B: Operational Observability Meta-Model Enums.

CONTRACTS:
- These enums are Informational ONLY.
- NEVER used for business decisions (Pass/Fail, Scoring).
- Separated from Track A (StatQueryType, StatPeriod).
"""
from enum import Enum


class ObsReason(str, Enum):
    """Reason codes - WHY did an event happen."""
    LLM_TIMEOUT = "LLM_TIMEOUT"          # LLM provider timeout
    RAG_EMPTY = "RAG_EMPTY"              # Retrieval returned no context
    PROVIDER_ERROR = "PROVIDER_ERROR"    # External API 4xx/5xx
    FACE_NOT_DETECTED = "FACE_NOT_DETECTED"  # Vision: no face found
    AUDIO_SILENCE = "AUDIO_SILENCE"      # Audio: level too low
    SYSTEM_ERROR = "SYSTEM_ERROR"        # Internal unhandled exception


class ObsSpan(str, Enum):
    """
    Span codes - WHERE IN TIME did an event happen.

    SCOPE: Limited to currently implemented pipelines.
    TTS_SYNTHESIS is Reserved (HOLD state) and excluded from CP1.
    """
    STT_PROCESSING = "STT_PROCESSING"    # Speech-to-Text phase
    RAG_RETRIEVAL = "RAG_RETRIEVAL"      # Vector/RAG search phase
    LLM_GENERATION = "LLM_GENERATION"   # Text generation phase
    EVAL_SCORING = "EVAL_SCORING"        # Evaluation scoring phase
    TOTAL_SESSION = "TOTAL_SESSION"      # End-to-end session
    # TTS_SYNTHESIS = "TTS_SYNTHESIS"    # Reserved (TTS is HOLD)


class ObsLayer(str, Enum):
    """Layer codes - WHERE IN THE STACK did an event happen."""
    API = "API"              # HTTP Entrance/Exit
    SERVICE = "SERVICE"      # Business Logic Orchestration
    PROVIDER = "PROVIDER"    # External Service Adapter
    DB = "DB"                # PostgreSQL Persistence
    CACHE = "CACHE"          # Redis Caching
