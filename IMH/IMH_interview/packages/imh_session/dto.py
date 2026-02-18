from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from .policy import InterviewMode

class SessionConfig(BaseModel):
    """
    Configuration for an Interview Session.
    Derived from Job Posting options.
    """
    total_question_limit: int = Field(..., description="Total number of questions")
    min_question_count: int = Field(default=10, description="Minimum questions guaranteed")
    question_timeout_sec: int = Field(default=120, description="Time limit per question in seconds")
    silence_timeout_sec: int = Field(default=15, description="Silence timeout in seconds")
    early_exit_enabled: bool = Field(default=False, description="Whether early exit based on score is enabled")
    mode: InterviewMode = Field(default=InterviewMode.ACTUAL, description="Session Mode: ACTUAL or PRACTICE")
    job_id: Optional[str] = Field(default=None, description="Linked Job Posting ID (if applicable)")
    result_exposure: str = Field(default="AFTER_14_DAYS", description="Result exposure policy (Snapshot)")
    
    # Contract: min_question_count must default to 10 as per policy

class SessionQuestionType(str, Enum):
    STATIC = "STATIC"
    GENERATED = "GENERATED"

class SessionQuestion(BaseModel):
    """
    Represents a question in the session.
    Value Object that is part of the Session Snapshot.
    """
    id: str
    content: str
    source_type: SessionQuestionType
    source_metadata: dict = Field(default_factory=dict)

class SessionContext(BaseModel):
    """
    Runtime context for a session.
    Represents the Hot State (Redis-like).
    """
    session_id: str
    user_id: Optional[str] = None
    job_id: str
    status: str
    started_at: Optional[float] = None # Timestamp
    current_step: int = 0
    completed_questions_count: int = 0
    early_exit_signaled: bool = False # Signal from Evaluation Layer
    
    # Snapshot Data
    current_question: Optional[SessionQuestion] = None
    question_history: List[SessionQuestion] = Field(default_factory=list) 
    answers_history: list = Field(default_factory=list) # List of Answer (DTO not defined here yet, use generic list or dict)
    
    # Snapshots
    job_policy_snapshot: Optional[dict] = None
    session_config_snapshot: Optional[dict] = None
