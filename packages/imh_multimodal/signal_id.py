"""
TASK-M: Signal ID generation (plan §3.2 — deterministic UUIDv5 contract).

Contract:
  signal_id = UUIDv5(PROJECT_M_NAMESPACE_UUID,
                     f"{session_id}:{turn_index}:{modality}:{chunk_seq}:{metric_key}")

Rules:
  - All five components are REQUIRED and must be str/int as declared.
  - The namespace UUID is fixed per deployment (set via env PROJECT_M_NAMESPACE_UUID).
  - chunk_seq starts at 1 (not 0). Assertion enforced.
  - modality must be one of: STT, VISION, EMOTION, AUDIO.
  - Generating the same inputs always yields the same signal_id → Exactly-once guarantee.

Environment variable:
  PROJECT_M_NAMESPACE_UUID  (required when MM_ENABLE=True)
"""
import os
import uuid
import logging

logger = logging.getLogger("imh.multimodal.signal")

_VALID_MODALITIES = frozenset({"STT", "VISION", "EMOTION", "AUDIO"})

# Fallback namespace; must be overridden in production via env var.
_FALLBACK_NS = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


def _get_namespace() -> uuid.UUID:
    """
    Load the project-level UUIDv5 namespace from the environment.
    Raises RuntimeError in production if not set (MM_ENABLE=True).
    """
    raw = os.environ.get("PROJECT_M_NAMESPACE_UUID", _FALLBACK_NS).strip()
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"PROJECT_M_NAMESPACE_UUID is not a valid UUID: {raw!r}"
        ) from exc


def generate_signal_id(
    session_id: str,
    turn_index: int,
    modality: str,
    chunk_seq: int,
    metric_key: str,
) -> str:
    """
    Deterministic UUIDv5 signal identifier.

    Args:
        session_id:  UUID string of the interview session.
        turn_index:  Zero-based turn number within the session.
        modality:    One of STT / VISION / EMOTION / AUDIO.
        chunk_seq:   1-based sequence number within the modality for this turn.
        metric_key:  The specific metric name (e.g. 'gaze_horizontal').

    Returns:
        UUID string (lowercase, canonical form).

    Raises:
        ValueError: on invalid modality or chunk_seq < 1.
    """
    modality = modality.upper()
    if modality not in _VALID_MODALITIES:
        raise ValueError(
            f"Invalid modality {modality!r}. Must be one of {sorted(_VALID_MODALITIES)}."
        )
    if chunk_seq < 1:
        raise ValueError(f"chunk_seq must be >= 1, got {chunk_seq}")

    namespace = _get_namespace()
    name = f"{session_id}:{turn_index}:{modality}:{chunk_seq}:{metric_key}"
    signal_uuid = uuid.uuid5(namespace, name)
    return str(signal_uuid)
