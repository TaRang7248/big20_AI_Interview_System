from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
import uuid

class SourceType(str, Enum):
    """
    Source of the question.
    """
    STATIC_BANK = "STATIC_BANK"
    GENERATED = "GENERATED"
    MIXED = "MIXED"

class QuestionStatus(str, Enum):
    """
    Status of the question in the bank.
    """
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"  # Soft Deleted

@dataclass
class SourceMetadata:
    """
    Metadata about the source of the question.
    """
    source_type: SourceType
    bank_id: Optional[str] = None  # If STATIC_BANK, reference to bank ID
    generation_context: Optional[Dict[str, Any]] = None  # If GENERATED, context info
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class Question:
    """
    Represents a question asset in the Question Bank.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    tags: List[str] = field(default_factory=list) # e.g. ["JAVA", "CLEAN_CODE"]
    difficulty: str = "MEDIUM" # EASY, MEDIUM, HARD
    job_role: Optional[str] = None # e.g. "BACKEND", "FRONTEND"
    
    source: SourceMetadata = field(default_factory=lambda: SourceMetadata(SourceType.STATIC_BANK))
    status: QuestionStatus = QuestionStatus.ACTIVE
    
    updated_at: datetime = field(default_factory=datetime.now)

    def mark_deleted(self):
        """Soft delete the question."""
        self.status = QuestionStatus.DELETED
        self.updated_at = datetime.now()

    def is_active(self) -> bool:
        return self.status == QuestionStatus.ACTIVE
