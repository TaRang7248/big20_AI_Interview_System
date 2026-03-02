from pydantic import BaseModel, Field
from typing import Optional, List, Dict
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


# TASK-034: Step 2 — Phase type for deterministic session ordering
class SessionStepType(str, Enum):
    """
    Represents the phase of a question in the interview session.
    Distribution is calculated for MAIN only.
    OPENING, FOLLOW_UP, CLOSING are excluded from distribution.
    """
    OPENING = "OPENING"
    MAIN = "MAIN"
    FOLLOW_UP = "FOLLOW_UP"
    CLOSING = "CLOSING"

class SessionQuestion(BaseModel):
    """
    Represents a question in the session.
    Value Object that is part of the Session Snapshot.
    """
    id: str
    content: str
    source_type: SessionQuestionType
    source_metadata: dict = Field(default_factory=dict)
    # TASK-034: Step 2 — Phase, category, and question-level metadata flags
    step_type: SessionStepType = SessionStepType.MAIN
    tag_code: Optional[str] = None          # Capability category tag
    parent_question_id: Optional[str] = None  # For FOLLOW_UP: inherits parent tag_code
    question_relaxed: bool = False           # True if question deviated from target category
    rag_triggered: bool = False              # True if RAG was used for this question

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
    answers_history: list = Field(default_factory=list)

    # Snapshots
    job_policy_snapshot: Optional[dict] = None
    session_config_snapshot: Optional[dict] = None

    # TASK-034: Step 2 — Frozen snapshot fields (immutable after session start)
    # These are set once and never modified during the session.
    main_question_n: Optional[int] = None           # MAIN questions only; excludes OPENING/FOLLOW_UP/CLOSING
    evaluation_weights: Optional[Dict[str, float]] = None  # Frozen from JobPolicy Snapshot
    resume_summary: Optional[str] = None             # Generated once at session start; immutable
    distribution_result: Optional[Dict[str, int]] = None   # Slots per tag_code; frozen post-distribution

    # TASK-034: Step 2 — Session-level metadata flags (set independently)
    policy_relaxed: bool = False             # True if distribution deviated from target weights
    low_confidence_sample: bool = False      # True if main_question_n < 5
