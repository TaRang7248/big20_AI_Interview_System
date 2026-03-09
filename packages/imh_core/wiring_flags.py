"""
TASK-035: Unified Wiring Feature Flags
Default: ALL False — old behavior is 100% preserved unless explicitly toggled.

Toggle via environment variable or direct attribute override in tests.

Usage:
    from packages.imh_core.wiring_flags import WiringFlags
    if WiringFlags.WIRING_WEIGHT_SYNC_ENABLED:
        ...
"""
import os


def _bool_env(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, "").strip().lower()
    if val in ("1", "true", "yes"):
        return True
    if val in ("0", "false", "no"):
        return False
    return default


class WiringFlags:
    """
    Master feature flag: LLM_WIRING_ENABLED
      When False → all sub-flags are implicitly False (old code path).
      When True  → sub-flags are evaluated individually.

    Sub-flags:
      WIRING_WEIGHT_SYNC_ENABLED  — snapshot weights override imh_eval defaults
      WIRING_PHASE_ENABLED        — PhaseManager drives session step-type
      WIRING_FIXED_Q_ENABLED      — fixed_question replaces last MAIN slot
    """

    # Master gate: all wiring is OFF by default
    LLM_WIRING_ENABLED: bool = _bool_env("LLM_WIRING_ENABLED", default=False)

    # Sub-flags (each is evaluated only when master is True)
    WIRING_WEIGHT_SYNC_ENABLED: bool = _bool_env("WIRING_WEIGHT_SYNC_ENABLED", default=False)
    WIRING_PHASE_ENABLED: bool = _bool_env("WIRING_PHASE_ENABLED", default=False)
    WIRING_FIXED_Q_ENABLED: bool = _bool_env("WIRING_FIXED_Q_ENABLED", default=False)

    @classmethod
    def weight_sync_active(cls) -> bool:
        """True only when both master and sub-flag are enabled."""
        return cls.LLM_WIRING_ENABLED and cls.WIRING_WEIGHT_SYNC_ENABLED

    @classmethod
    def phase_active(cls) -> bool:
        return cls.LLM_WIRING_ENABLED and cls.WIRING_PHASE_ENABLED

    @classmethod
    def fixed_q_active(cls) -> bool:
        return cls.LLM_WIRING_ENABLED and cls.WIRING_FIXED_Q_ENABLED
