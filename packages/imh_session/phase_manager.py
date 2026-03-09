"""
TASK-034 Step 4: PhaseManager
Orchestrates session step flow: OPENING → MAIN → FOLLOW_UP → CLOSING.
Enforces the deterministic sequence and FOLLOW_UP tag_code inheritance.
"""
from __future__ import annotations

from typing import Optional, List
from .dto import SessionQuestion, SessionStepType, SessionQuestionType


class PhaseManager:
    """
    Manages the session step type assignment and flow transitions.

    Sequence Contract (Immutable):
        Distribution → MAIN confirmed → FOLLOW_UP generated

    Rules:
    - Step 1 (index 0): always OPENING
    - Step N (last): always CLOSING
    - Middle steps: MAIN, optionally followed by FOLLOW_UP
    - FOLLOW_UP inherits tag_code from its parent MAIN question
    - FOLLOW_UP does NOT trigger distribution or sampling
    """

    def __init__(self, main_question_n: int, tail_question_limit: int = 2):
        """
        :param main_question_n: Number of MAIN questions (excludes OPENING/CLOSING/FOLLOW_UP)
        :param tail_question_limit: Max FOLLOW_UP depth per MAIN question
        """
        self.main_question_n = main_question_n
        self.tail_question_limit = tail_question_limit
        self._follow_up_counts: dict[str, int] = {}   # parent_id -> follow_up_count

    def get_step_type(self, step_index: int, total_steps: int) -> SessionStepType:
        """
        Returns the step type for a given step index.
        Step 0 = OPENING; Step (total-1) = CLOSING; otherwise MAIN.
        FOLLOW_UP is assigned externally by request_follow_up().
        """
        if step_index == 0:
            return SessionStepType.OPENING
        if step_index == total_steps - 1:
            return SessionStepType.CLOSING
        return SessionStepType.MAIN

    def request_follow_up(
        self, parent_question: SessionQuestion
    ) -> Optional[SessionStepType]:
        """
        Determines if a FOLLOW_UP can be generated for the given parent question.
        Returns SessionStepType.FOLLOW_UP if allowed, None if limit is reached.

        FOLLOW_UP inherits the parent's tag_code implicitly — callers must copy it.
        """
        if parent_question.step_type != SessionStepType.MAIN:
            return None  # FOLLOW_UP can only be generated from MAIN

        count = self._follow_up_counts.get(parent_question.id, 0)
        if count >= self.tail_question_limit:
            return None  # Depth limit reached

        self._follow_up_counts[parent_question.id] = count + 1
        return SessionStepType.FOLLOW_UP

    def build_follow_up_question(
        self, question_id: str, content: str, parent_question: SessionQuestion
    ) -> SessionQuestion:
        """
        Creates a FOLLOW_UP SessionQuestion that inherits tag_code from parent.
        This is the canonical way to create a FOLLOW_UP.
        FOLLOW_UP does NOT go through distribution sampling.
        """
        return SessionQuestion(
            id=question_id,
            content=content,
            source_type=SessionQuestionType.GENERATED,
            step_type=SessionStepType.FOLLOW_UP,
            tag_code=parent_question.tag_code,          # inherited, not re-sampled
            parent_question_id=parent_question.id,
            question_relaxed=False,
            rag_triggered=False,
        )

    def validate_sequence(self, questions: List[SessionQuestion]) -> bool:
        """
        Validates that the question list follows the required sequence.
        Contract: Distribution → MAIN → FOLLOW_UP (sequence immutable)
        """
        if not questions:
            return True

        if questions[0].step_type != SessionStepType.OPENING:
            return False
        if questions[-1].step_type != SessionStepType.CLOSING:
            return False

        # Verify FOLLOW_UP always comes after a MAIN
        for i, q in enumerate(questions):
            if q.step_type == SessionStepType.FOLLOW_UP:
                if i == 0 or questions[i - 1].step_type not in (
                    SessionStepType.MAIN, SessionStepType.FOLLOW_UP
                ):
                    return False
        return True
