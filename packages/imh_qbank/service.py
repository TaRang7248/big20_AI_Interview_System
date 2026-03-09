from typing import List, Optional
from .domain import Question, QuestionStatus, SourceType, SourceMetadata
from .repository_interface import QuestionRepository
from packages.imh_core.logging import get_logger

logger = get_logger("imh_qbank.service")

class QuestionBankService:
    """
    Facade for accessing the Question Bank (Candidate Provider).
    Responsible for providing candidate questions based on criteria.
    Enforces Soft Delete policy (Active-only filtering).
    """

    def __init__(self, repository: QuestionRepository):
        self.repository = repository

    def add_static_question(self, content: str, tags: List[str], difficulty: str = "MEDIUM", job_role: Optional[str] = None) -> Question:
        """
        Helper to add a new static question to the bank.
        """
        question = Question(
            content=content,
            tags=tags,
            difficulty=difficulty,
            job_role=job_role,
            source=SourceMetadata(SourceType.STATIC_BANK),
            status=QuestionStatus.ACTIVE
        )
        self.repository.save(question)
        return question

    def get_candidates(self, job_role: Optional[str] = None, tags: List[str] = None) -> List[Question]:
        """
        Get ACTIVE candidate questions matching criteria.
        Soft Deleted questions are automatically excluded by repository's find_all_active,
        but we can add more specific filtering logic here.
        """
        candidates = self.repository.find_all_active()
        
        filtered = []
        for q in candidates:
            # 1. Active Check (Redundant but safe - CP3 Contract: Read-Time Filtering)
            if not q.is_active():
                continue
            
            # 2. Job Role Filter (if specified)
            if job_role and q.job_role and q.job_role != job_role:
                continue
            
            # 3. Tags Filter (if specified, e.g. MUST have at least one tag)
            if tags:
                has_tag = False
                for t in tags:
                    if t in q.tags:
                        has_tag = True
                        break
                if not has_tag:
                    continue
            
            filtered.append(q)
            
        return filtered

    def get_question_by_id(self, question_id: str) -> Optional[Question]:
        """
        Retrieve a question by ID, even if Soft Deleted.
        This is useful for Audit or History, but NOT for new sessions.
        Note: Use with caution to respect Session Immutability (session should store value, not ref).
        """
        return self.repository.find_by_id(question_id)

    def soft_delete_question(self, question_id: str) -> bool:
        """
        Soft delete a question.
        Returns True if successful, False if not found.
        """
        return self.repository.delete(question_id)
