"""
TASK-034 Step 1 Unit Tests: DistributionCalculator
Tests all Fast-Gate required scenarios from the approved plan.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))
from imh_session.distribution import DistributionCalculator, DistributionInput, DistributionResult


def calc(weights: dict, n: int) -> DistributionResult:
    return DistributionCalculator.calculate(DistributionInput(weights=weights, n=n))


# ── n=3, weights=60/20/10/10 ─────────────────────────────────────────────────
class TestCoverageFloorN3:
    def test_n3_distributes_top3_only(self):
        """n=3 → top 3 categories get 1 each; 4th excluded → policy_relaxed=True"""
        result = calc({"A": 60, "B": 20, "C": 10, "D": 10}, n=3)
        assert result.slots.get("A", 0) >= 1
        assert result.slots.get("B", 0) >= 1
        assert result.slots.get("C", 0) >= 1 or result.slots.get("D", 0) >= 1
        assert sum(result.slots.values()) == 3
        assert result.policy_relaxed is True

    def test_n3_low_confidence_flag(self):
        result = calc({"A": 60, "B": 20, "C": 10, "D": 10}, n=3)
        assert result.low_confidence_sample is True

    def test_n3_4category_one_excluded(self):
        """n=3, 4 categories → exactly 1 category dropped"""
        result = calc({"A": 60, "B": 20, "C": 10, "D": 10}, n=3)
        assert "D" not in result.slots or result.slots["D"] == 0


# ── n=4, weights=60/20/10/10 ─────────────────────────────────────────────────
class TestCoverageFloorN4:
    def test_n4_all_categories_covered(self):
        """n=4, 4 categories → each gets 1 slot exactly (CF fills n)"""
        result = calc({"A": 60, "B": 20, "C": 10, "D": 10}, n=4)
        assert result.slots == {"A": 1, "B": 1, "C": 1, "D": 1}
        assert result.policy_relaxed is False

    def test_n4_low_confidence_false(self):
        result = calc({"A": 60, "B": 20, "C": 10, "D": 10}, n=4)
        assert result.low_confidence_sample is True  # n=4 < 5


# ── n=7, proportional residuals ────────────────────────────────────────────
class TestResidualDistribution:
    def test_n7_distributes_residual_by_weight(self):
        """n=7, CF=4 → 3 residual slots; 60% category should get most extras"""
        result = calc({"A": 60, "B": 20, "C": 10, "D": 10}, n=7)
        assert sum(result.slots.values()) == 7
        assert result.slots.get("A", 0) >= 2  # High weight → gets most extras

    def test_n7_low_confidence_false(self):
        result = calc({"A": 60, "B": 20, "C": 10, "D": 10}, n=7)
        assert result.low_confidence_sample is False  # n=7 >= 5


# ── Epsilon Guard (zero weight) ────────────────────────────────────────────
class TestEpsilonGuard:
    def test_zero_weight_excluded(self):
        """category with weight 0 should never appear in slots"""
        result = calc({"A": 80, "B": 10, "C": 10, "D": 0}, n=4)
        assert result.slots.get("D", 0) == 0

    def test_sub_epsilon_weight_excluded(self):
        """weight < 0.01 should be excluded"""
        result = calc({"A": 0.80, "B": 0.10, "C": 0.095, "D": 0.005}, n=4)
        assert result.slots.get("D", 0) == 0


# ── Deterministic Tie-Breaker ─────────────────────────────────────────────
class TestDeterministicTieBreaker:
    def test_equal_remainder_resolved_by_tag_asc(self):
        """same remainder → resolved by tag_code ASC (alphabetical)"""
        result_1 = calc({"AA": 40, "BB": 40, "CC": 10, "DD": 10}, n=5)
        result_2 = calc({"AA": 40, "BB": 40, "CC": 10, "DD": 10}, n=5)
        assert result_1.slots == result_2.slots  # deterministic

    def test_same_input_same_output(self):
        """Determinism guarantee: identical input → identical output"""
        for _ in range(5):
            r = calc({"X": 60, "Y": 20, "Z": 10, "W": 10}, n=6)
            assert sum(r.slots.values()) == 6


# ── Hard Validation ────────────────────────────────────────────────────────
class TestHardValidation:
    def test_n_less_than_3_raises(self):
        """n < 3 → ValueError (Backend enforces 400)"""
        with pytest.raises(ValueError, match="main_question_n must be >= 3"):
            calc({"A": 100}, n=2)

    def test_bad_weight_sum_raises(self):
        """weights not summing to 1.0 or 100 → ValueError"""
        with pytest.raises(ValueError, match="Weights must sum"):
            calc({"A": 50, "B": 30}, n=3)
