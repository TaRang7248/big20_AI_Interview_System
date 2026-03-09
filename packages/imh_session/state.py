from enum import Enum, auto

class SessionStatus(str, Enum):
    """
    Interview Session Status Enum.
    Strictly follows TASK-017_PLAN.md.
    """
    APPLIED = "APPLIED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    INTERRUPTED = "INTERRUPTED"
    EVALUATED = "EVALUATED"
    ABORTED = "ABORTED"

class SessionEvent(str, Enum):
    """
    Events emitted by the Session Engine.
    """
    SILENCE_WARNING = "SILENCE_WARNING"    # Trigger UI Toast/Audio
    SILENCE_TIMEOUT = "SILENCE_TIMEOUT"    # Auto-advance due to silence
    QUESTION_TIMEOUT = "QUESTION_TIMEOUT"  # Auto-advance due to time limit
    ANSWER_COMPLETED = "ANSWER_COMPLETED"  # User clicked done
    SESSION_COMPLETED = "SESSION_COMPLETED"
    SESSION_INTERRUPTED = "SESSION_INTERRUPTED"

class TerminationReason(str, Enum):
    """
    Reason for session termination.
    """
    MAX_QUESTIONS_REACHED = "MAX_QUESTIONS_REACHED"
    EARLY_EXIT_SIGNAL = "EARLY_EXIT_SIGNAL"
    INTERRUPTED_BY_USER = "INTERRUPTED_BY_USER"
    INTERRUPTED_BY_ERROR = "INTERRUPTED_BY_ERROR"
    ABORTED_BY_SYSTEM = "ABORTED_BY_SYSTEM"
