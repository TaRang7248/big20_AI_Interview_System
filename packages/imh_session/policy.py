from enum import Enum
from abc import ABC, abstractmethod

class InterviewMode(str, Enum):
    """
    Interview Mode Enum.
    Distinguishes between Actual (Job Posting) and Practice (Free) modes.
    """
    ACTUAL = "ACTUAL"
    PRACTICE = "PRACTICE"

class InterviewPolicy(ABC):
    """
    Abstract Base Class for Interview Policies.
    Defines the contract for "What is allowed" in a session.
    Engine consults this policy, but Policy does not change Engine state.
    """
    
    @property
    @abstractmethod
    def mode(self) -> InterviewMode:
        pass

    @abstractmethod
    def can_pause(self) -> bool:
        """Can the session be paused?"""
        pass
    
    @abstractmethod
    def can_retry_answer(self) -> bool:
        """Can the user retry an answer?"""
        pass

    @abstractmethod
    def can_resume_from_interruption(self) -> bool:
        """Can a session be resumed after interruption?"""
        pass

    @abstractmethod
    def requires_min_questions_for_early_exit(self) -> bool:
        """Is meeting min_question_count mandatory before early exit?"""
        pass

    @abstractmethod
    def should_terminate_on_interruption(self) -> bool:
        """Should the session immediately terminate (INTERRUPTED) on interruption?"""
        pass
        
    @abstractmethod
    def get_result_exposure_level(self) -> str:
        """Return result exposure policy description."""
        pass

class ActualModePolicy(InterviewPolicy):
    """
    Policy for Actual Mode (Job Posting 1st Interview).
    Strict rules.
    """
    @property
    def mode(self) -> InterviewMode:
        return InterviewMode.ACTUAL

    def can_pause(self) -> bool:
        return False

    def can_retry_answer(self) -> bool:
        return False

    def can_resume_from_interruption(self) -> bool:
        # Strict Rule: No resume allowed for Actual Mode
        return False

    def requires_min_questions_for_early_exit(self) -> bool:
        # Strict Rule: Must complete min questions
        return True

    def should_terminate_on_interruption(self) -> bool:
        # Strict Rule: Immediate termination
        return True
    
    def get_result_exposure_level(self) -> str:
        return "ADMIN_CONFIGURED"

class PracticeModePolicy(InterviewPolicy):
    """
    Policy for Practice Mode (Free Training).
    Flexible rules.
    """
    @property
    def mode(self) -> InterviewMode:
        return InterviewMode.PRACTICE

    def can_pause(self) -> bool:
        return True

    def can_retry_answer(self) -> bool:
        return True

    def can_resume_from_interruption(self) -> bool:
        # Flexible Rule: Resume allowed
        return True

    def requires_min_questions_for_early_exit(self) -> bool:
        # Flexible Rule: User can stop anytime (or minimal constraint)
        # For consistency with plan "Use system defaults", currently implied as "No strict mandate"
        # But for 'early exit' triggering based on score, we might still want some data.
        # Plan says: "Practice: System default / User convenience first".
        return False 

    def should_terminate_on_interruption(self) -> bool:
        # Flexible Rule: Do not auto-terminate, allow resume
        return False
    
    def get_result_exposure_level(self) -> str:
        return "FULL_DETAIL"

def get_policy(mode: InterviewMode) -> InterviewPolicy:
    """Factory to get policy instance."""
    if mode == InterviewMode.ACTUAL:
        return ActualModePolicy()
    elif mode == InterviewMode.PRACTICE:
        return PracticeModePolicy()
    else:
        raise ValueError(f"Unknown mode: {mode}")
