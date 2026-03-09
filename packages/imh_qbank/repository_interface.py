from abc import ABC, abstractmethod
from typing import List, Optional
from .domain import Question

class QuestionRepository(ABC):
    """
    Abstract Interface for Question Bank Repository.
    """

    @abstractmethod
    def save(self, question: Question) -> None:
        """Save a question (create or update)."""
        pass

    @abstractmethod
    def find_by_id(self, question_id: str) -> Optional[Question]:
        """Find a question by ID, regardless of status (for audit/history)."""
        pass

    @abstractmethod
    def find_all_active(self) -> List[Question]:
        """Find all ACTIVE questions (candidates)."""
        pass

    @abstractmethod
    def delete(self, question_id: str) -> bool:
        """Soft delete a question by ID."""
        pass
