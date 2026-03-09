"""
TASK-M Sprint 2: Metric Normalizer (plan §3.3)

Applies the normalization profile to a raw metric value.

Contract:
  Normal(x) = clip((x - min) / (max - min), 0, 1)
  - Outlier policy: 3-sigma values are hard-clipped to [min, max].
  - Missing policy: always Neutral = 0.5 (no zero/penalty option).
  - Profile integrity: profile_id from payload MUST match the session
    snapshot profile_id; mismatch → Drop + Alert (plan §3.3).
  - All profiles are frozen at job_policy_snapshot creation time.

Profile Registry:
  A hardcoded read-only dict keyed by metric_key.
  Sprint 2: uses the default Phase 1 profile (plan §3.3 table).
  Sprint 3+: profile_id from stream payload selects the right entry.
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger("imh.multimodal.normalizer")

# ------------------------------------------------------------------ #
# Default Phase 1 normalization profile (plan §3.3)                   #
# All missing values default to 0.5 (Neutral).                        #
# ------------------------------------------------------------------ #
DEFAULT_PROFILE_ID = "phase1_default_v1"

NORMALIZATION_PROFILE: dict[str, dict] = {
    "gaze_horizontal":  {"min": -30.0, "max": 30.0},
    "gaze_vertical":    {"min": -20.0, "max": 20.0},
    "pitch_hz":         {"min": 50.0,  "max": 500.0},
    "intensity_db":     {"min": 30.0,  "max": 90.0},
    "emotion_happy":    {"min": 0.0,   "max": 1.0},
    "emotion_neutral":  {"min": 0.0,   "max": 1.0},
    "stt_confidence":   {"min": 0.0,   "max": 1.0},
    "speaking_rate":    {"min": 0.0,   "max": 5.0},   # syllables/sec
}

NEUTRAL = 0.5


def normalize(
    metric_key: str,
    raw_value: Optional[float],
    profile_id: str = DEFAULT_PROFILE_ID,
    session_profile_id: Optional[str] = None,
) -> float:
    """
    Normalize a single raw metric value using the profile registry.

    Args:
        metric_key:         The metric identifier (e.g. 'gaze_horizontal').
        raw_value:          Raw measured value. None → Neutral(0.5).
        profile_id:         Profile ID from the Redis Stream payload.
        session_profile_id: Profile ID from the session_config_snapshot
                            (passed in by the Producer).

    Returns:
        Float in [0.0, 1.0]. Missing data → exactly 0.5.

    Side effects:
        Logs a warning and returns Neutral on profile mismatch
        (plan §3.3 drop handled upstream by the Worker, not here).
    """
    # Profile ID integrity check (plan §3.3)
    if session_profile_id is not None and profile_id != session_profile_id:
        logger.warning(
            "Profile ID mismatch: payload=%r snapshot=%r metric=%r — returning Neutral",
            profile_id, session_profile_id, metric_key,
        )
        return NEUTRAL

    # Missing value → Neutral (plan §3.3, §12)
    if raw_value is None:
        return NEUTRAL

    profile = NORMALIZATION_PROFILE.get(metric_key)
    if profile is None:
        logger.warning("Unknown metric_key %r — returning Neutral", metric_key)
        return NEUTRAL

    lo, hi = profile["min"], profile["max"]

    # Hard-clip outliers before normalising (plan §3.3 Outlier policy)
    clamped = max(lo, min(hi, raw_value))

    span = hi - lo
    if span == 0:
        return NEUTRAL

    result = (clamped - lo) / span
    # Final safety clip (floating-point guard)
    return max(0.0, min(1.0, result))
