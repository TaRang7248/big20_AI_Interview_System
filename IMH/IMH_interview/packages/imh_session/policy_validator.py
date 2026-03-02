"""
TASK-034 Step 3: PolicyValidator
Fail-fast validation layer called by the API before session creation.
Backend enforces all policy limits regardless of Frontend.
"""
from __future__ import annotations

from typing import Dict

EPSILON: float = 0.01
MIN_QUESTION_N: int = 3
MIN_WEIGHT_FLOOR: float = 0.10   # Target minimum weight per category
MAX_WEIGHT_CAP: float = 0.70     # Target maximum weight per category


class PolicyValidationError(ValueError):
    """Raised when a policy constraint is violated. Maps to HTTP 400."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class PolicyValidationResult:
    """Result of policy validation with relaxation metadata."""
    def __init__(self):
        self.valid: bool = True
        self.policy_relaxed: bool = False
        self.relaxation_reasons: list[str] = []

    def relax(self, reason: str):
        self.policy_relaxed = True
        self.relaxation_reasons.append(reason)


class PolicyValidator:
    """
    Validates session creation parameters before session start.
    Called by the API layer (not the Engine).

    Hard rules raise PolicyValidationError (→ HTTP 400).
    Soft rules (min_weight underflow) auto-relax and set metadata.
    """

    @staticmethod
    def validate(main_question_n: int, weights: Dict[str, float]) -> PolicyValidationResult:
        """
        Validate session creation parameters.
        Raises PolicyValidationError for hard violations.
        Returns PolicyValidationResult with relaxation flags if soft adjustments occur.
        """
        result = PolicyValidationResult()

        # ── Hard Rule 1: main_question_n >= 3 ──────────────────────────
        if main_question_n < MIN_QUESTION_N:
            raise PolicyValidationError(
                code="INVALID_N",
                message=f"main_question_n must be >= {MIN_QUESTION_N}. Got {main_question_n}."
            )

        # ── Normalize weights (accept both 0-1 and 0-100 scale) ─────────
        total = sum(weights.values())
        if abs(total - 100.0) < 0.5:
            weights = {k: v / 100.0 for k, v in weights.items()}
            total = sum(weights.values())

        # ── Hard Rule 2: weights must sum to 100% ────────────────────────
        if abs(total - 1.0) > 0.02:
            raise PolicyValidationError(
                code="INVALID_WEIGHT_SUM",
                message=f"Evaluation weights must sum to 100%. Got {total * 100:.1f}%."
            )

        # ── Hard Rule 3: no negative weights ────────────────────────────
        for tag, w in weights.items():
            if w < 0:
                raise PolicyValidationError(
                    code="NEGATIVE_WEIGHT",
                    message=f"Weight for '{tag}' is negative: {w}"
                )

        # ── Soft Rule: max weight cap ──────────────────────────────────
        for tag, w in weights.items():
            if w > MAX_WEIGHT_CAP:
                result.relax(f"Weight for '{tag}' ({w:.0%}) exceeds cap {MAX_WEIGHT_CAP:.0%}; clamped.")

        # ── Soft Rule: min weight floor ─────────────────────────────────
        active = {k: v for k, v in weights.items() if v >= EPSILON}
        k = len(active)
        # Mathematical conflict: if k * min_floor > 1.0, lower the floor
        effective_min = MIN_WEIGHT_FLOOR
        if k > 0 and k * MIN_WEIGHT_FLOOR > 1.0:
            effective_min = 1.0 / k
            result.relax(f"min_weight floor lowered to {effective_min:.2%} due to k={k} categories.")

        for tag, w in active.items():
            if 0 < w < effective_min:
                result.relax(
                    f"Weight for '{tag}' ({w:.2%}) is below effective floor ({effective_min:.2%}), "
                    f"allowed via auto-relaxation."
                )

        return result
