"""
TASK-034 Step 1: DistributionCalculator
Pure Python, no LLM. Deterministic topic distribution for MAIN questions only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


# Epsilon: weights below this are excluded from residual distribution
EPSILON: float = 0.01


@dataclass
class DistributionResult:
    """
    Immutable output of the DistributionCalculator.
    Frozen into the session snapshot at session start.
    """
    slots: Dict[str, int]           # { tag_code: question_count }
    policy_relaxed: bool = False    # True if CF or weight constraints were relaxed
    low_confidence_sample: bool = False  # True if n < 5


@dataclass
class DistributionInput:
    """
    Input for DistributionCalculator.
    weights: { tag_code: float } — must sum to 1.0 (fractions) or 100.0 (percent)
    n: main_question_n — MAIN questions only. OPENING/FOLLOW_UP/CLOSING excluded.
    """
    weights: Dict[str, float]   # tag_code -> weight (normalized 0.0-1.0)
    n: int                      # main_question_n (MAIN only)


class DistributionCalculator:
    """
    Computes deterministic MAIN question slot distribution.

    Contract:
    - Input → always same output (deterministic)
    - Zero LLM usage
    - FOLLOW_UP, OPENING, CLOSING are NOT inputs here
    - Policy relaxation is flagged in metadata, never silently discarded
    """

    @staticmethod
    def calculate(di: DistributionInput) -> DistributionResult:
        weights = di.weights
        n = di.n

        # ── Hard Guard ──────────────────────────────────────────────────
        if n < 3:
            raise ValueError(f"main_question_n must be >= 3. Got {n}.")

        # ── Normalize weights to sum=1.0 if given as percent ──────────
        total_w = sum(weights.values())
        if abs(total_w - 100.0) < 0.1:
            weights = {k: v / 100.0 for k, v in weights.items()}
        elif abs(total_w - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0 or 100.0. Got {total_w:.4f}")

        # ── Epsilon Guard ────────────────────────────────────────────────
        active_categories: List[str] = sorted(
            [k for k, v in weights.items() if v >= EPSILON],
            key=lambda k: (-weights[k], k)   # Descending weight, ASC tag_code as tiebreak
        )

        policy_relaxed = False

        # ── Coverage Floor ───────────────────────────────────────────────
        # n >= 4: Cover all active categories (up to 4 core)
        # n == 3: Cover top-3 active categories
        coverage_target = min(len(active_categories), 4 if n >= 4 else 3)
        covered_categories = active_categories[:coverage_target]

        if len(active_categories) > coverage_target:
            policy_relaxed = True  # Some categories excluded due to n constraint

        if n < coverage_target:
            # n is smaller than intended coverage; cover as many as n allows
            covered_categories = active_categories[:n]
            policy_relaxed = True

        # Allocate 1 slot per covered category
        slots: Dict[str, int] = {cat: 1 for cat in covered_categories}
        n_allocated = len(covered_categories)
        n_rem = n - n_allocated

        # ── Largest Remainder Method (Proportional Filling) ──────────────
        if n_rem > 0 and covered_categories:
            total_covered_weight = sum(weights[c] for c in covered_categories)
            if total_covered_weight == 0:
                total_covered_weight = 1.0  # Safety guard

            # Ideal fractional slots per category
            ideal: List[Tuple[float, str]] = []
            for cat in covered_categories:
                share = (weights[cat] / total_covered_weight) * n_rem
                ideal.append((share, cat))

            # Floor passes
            floors = {cat: int(share) for share, cat in ideal}
            remainders: List[Tuple[float, str]] = sorted(
                [(share - int(share), cat) for share, cat in ideal],
                key=lambda x: (-x[0], -weights[x[1]], x[1])   # remainder DESC, weight DESC, tag ASC
            )

            distributed = sum(floors.values())
            leftover = n_rem - distributed

            for i in range(leftover):
                _, cat = remainders[i]
                floors[cat] = floors.get(cat, 0) + 1

            for cat, extra in floors.items():
                slots[cat] = slots.get(cat, 0) + extra

        # ── Step 6: Audit ────────────────────────────────────────────────
        # If any active category is missing but has non-zero weight, flag relaxation
        missing = [c for c in active_categories if c not in slots]
        if missing:
            policy_relaxed = True

        # ── Sample-size Confidence ───────────────────────────────────────
        low_confidence_sample = n < 5

        return DistributionResult(
            slots=slots,
            policy_relaxed=policy_relaxed,
            low_confidence_sample=low_confidence_sample,
        )
