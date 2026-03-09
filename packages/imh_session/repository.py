from abc import ABC, abstractmethod
from typing import Optional, Any
from .dto import SessionContext
from .state import SessionStatus

class SessionStateRepository(ABC):
    """
    Interface for Hot State Storage (Redis-like).
    Handles rapid state updates during the session.
    """
    @abstractmethod
    def save_state(self, session_id: str, context: SessionContext) -> None:
        pass

    @abstractmethod
    def get_state(self, session_id: str) -> Optional[SessionContext]:
        pass

    @abstractmethod
    def update_status(self, session_id: str, status: SessionStatus) -> None:
        pass

    @abstractmethod
    def find_by_job_id(self, job_id: str) -> list[SessionContext]:
        """
        Find active sessions by Job ID.
        Essential for Admin Dashboard monitoring.
        """
        pass

class SessionHistoryRepository(ABC):
    """
    Interface for Cold Storage (PostgreSQL).
    Handles persistence of finalized session data.
    """
    @abstractmethod
    def save_interview_result(self, session_id: str, result_data: Any) -> None:
        """
        Save the finalized interview result and evaluations.
        Maps to 'interview_evaluations' and 'evaluation_scores' tables.
        """
        pass

    @abstractmethod
    def update_interview_status(self, session_id: str, status: SessionStatus) -> None:
        """
        Update the 'interviews' table status.
        """
        pass
