"""
TASK-034 Step 7: MetadataFlagManager
Computes all 4 session/question metadata flags independently.
No cross-flag synchronization allowed.
"""
from __future__ import annotations

from typing import Optional
from .dto import SessionQuestion, SessionStepType


class MetadataFlagManager:
    """
    Computes and sets metadata flags explicitly and independently.

    Flag Definitions:
    ┌─────────────────────────┬───────────┬──────────────────────────────────────────────┐
    │ Flag                    │ Scope     │ Meaning                                      │
    ├─────────────────────────┼───────────┼──────────────────────────────────────────────┤
    │ policy_relaxed          │ Session   │ Distribution deviated from target weights     │
    │ question_relaxed        │ Question  │ Question deviated from target category        │
    │ LOW_CONFIDENCE_SAMPLE   │ Session   │ n < 5 → high variance in final score         │
    │ RAG_TRIGGERED           │ Question  │ RAG path was used for this question           │
    └─────────────────────────┴───────────┴──────────────────────────────────────────────┘

    Independence Principle:
    - Each flag is set explicitly. No automatic propagation.
    - policy_relaxed=True does NOT imply question_relaxed=True (and vice versa).
    """

    # ── Session-Level Flags ─────────────────────────────────────────────

    @staticmethod
    def compute_policy_relaxed(distribution_policy_relaxed: bool) -> bool:
        """
        Set by the DistributionCalculator when CF or weight constraints forced a deviation.
        Source: DistributionResult.policy_relaxed
        """
        return distribution_policy_relaxed

    @staticmethod
    def compute_low_confidence_sample(main_question_n: int) -> bool:
        """
        True when n < 5, indicating statistically high variance in the final score.
        """
        return main_question_n < 5

    # ── Question-Level Flags ────────────────────────────────────────────

    @staticmethod
    def mark_rag_triggered(question: SessionQuestion) -> SessionQuestion:
        """
        Explicitly marks a question as having been generated via RAG path.
        Returns a new SessionQuestion with rag_triggered=True.
        """
        return question.model_copy(update={"rag_triggered": True})

    @staticmethod
    def mark_question_relaxed(
        question: SessionQuestion, reason: Optional[str] = None
    ) -> SessionQuestion:
        """
        Explicitly marks a question as having deviated from its target category.
        E.g., RAG fallback returned a different category, or FOLLOW_UP was out-of-category.
        Returns a new SessionQuestion with question_relaxed=True.
        """
        metadata = dict(question.source_metadata)
        if reason:
            metadata["relaxation_reason"] = reason
        return question.model_copy(update={"question_relaxed": True, "source_metadata": metadata})

    @staticmethod
    def check_rag_trigger(
        step_type: SessionStepType,
        intent: Optional[str],
        resume_summary: Optional[str],
        job_requirements: Optional[str],
        source_type: Optional[str],
        llm_fallback_signal: bool = False,
    ) -> bool:
        """
        Stage Guard Rule + Refinement Rule evaluation.
        Returns True only if RAG should be triggered.

        Stage Guard (Hard Block):
        - OPENING step: never triggers RAG
        - GENERAL_SMALLTALK intent: never triggers RAG

        Trigger Conditions (any one sufficient, must pass Stage Guard first):
        1. intent == TECHNICAL_DEPTH
        2. source_type == STATIC_BANK
        3. resume_summary exists AND job_requirements length > 300
        4. LLM generation fallback signal
        """
        # ── Stage Guard Rule (hard block) ───────────────────────────────
        if step_type == SessionStepType.OPENING:
            return False
        if intent == "GENERAL_SMALLTALK":
            return False

        # ── Extended Trigger Set ─────────────────────────────────────────
        if intent == "TECHNICAL_DEPTH":
            return True
        if source_type == "STATIC_BANK":
            return True
        if resume_summary and job_requirements and len(job_requirements) > 300:
            return True
        if llm_fallback_signal:
            return True

        return False
