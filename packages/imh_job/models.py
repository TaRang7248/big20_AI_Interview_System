from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, PrivateAttr, validator, model_validator

from .enums import JobStatus
from .errors import JobStateError, PolicyValidationError
from packages.imh_session.dto import SessionConfig
from packages.imh_session.policy import InterviewMode

class JobPolicy(BaseModel):
    """
    AI Evaluation Schema & Policy Configuration.
    These fields are considered AI-Sensitive and are IMMUTABLE after publishing.
    """
    mode: InterviewMode = Field(..., description="Interview Mode (ACTUAL/PRACTICE)")
    
    # Session Control
    total_question_limit: int = Field(..., gt=0, description="Total number of questions")
    min_question_count: int = Field(default=10, ge=10, description="Minimum questions (Must be >= 10)")
    question_timeout_sec: int = Field(default=120, gt=0, description="Time limit per question")
    silence_timeout_sec: int = Field(default=15, gt=0, description="Silence detection timeout")
    
    # Interaction Policy
    allow_retry: bool = Field(default=False, description="Allow retrying answers")
    
    # Context & Criteria
    description: str = Field(..., min_length=10, description="Job Description (Context)")
    requirements: List[str] = Field(default_factory=list, description="Mandatory Requirements")
    preferences: List[str] = Field(default_factory=list, description="Preferred Qualifications")
    
    # Evaluation
    evaluation_weights: Dict[str, float] = Field(
        default_factory=lambda: {"job": 40.0, "comm": 30.0, "attitude": 30.0},
        description="Weights for evaluation areas"
    )
    
    # Result Exposure
    result_exposure: str = Field(default="AFTER_14_DAYS", description="Result exposure policy")

    # ── Persona & Fixed Questions (AI Policy — Frozen at Publish) ──────────────
    persona: Optional[str] = Field(
        default="professional",
        description="Interviewer persona: 'professional' | 'friendly' | 'strict'"
    )
    fixed_questions: Optional[List[str]] = Field(
        default_factory=list,
        description="Fixed questions always injected into the session (before LLM generation)"
    )

    # ── Wiring Flags (Feature On/Off — Frozen at Publish) ────────────────────
    wiring_resume_q_enabled: bool = Field(
        default=True,
        description="Enable resume-based question generation"
    )
    wiring_rag_enabled: bool = Field(
        default=True,
        description="Enable RAG (question bank vector search) for question generation"
    )
    wiring_multimodal_enabled: bool = Field(
        default=True,
        description="Enable multimodal analysis (STT, emotion, gaze)"
    )

    @validator("min_question_count")
    def validate_min_questions(cls, v):
        if v < 10:
            raise ValueError("Minimum question count must be at least 10 (System Policy).")
        return v

class Job(BaseModel):
    """
    Job Posting Aggregate Root.
    Manages lifecycle and policy immutability.
    
    Note: We use PrivateAttr for _policy to enforce strict immutability via property setter.
    However, to support Pydantic initialization and JSON serialization, we need careful handling.
    """
    job_id: str = Field(..., description="Unique Job ID")
    title: str = Field(..., min_length=2, description="Job Title")
    status: JobStatus = Field(default=JobStatus.DRAFT, description="Current Status")
    
    # We declare policy as a constructor field, but store it in _policy
    _policy: JobPolicy = PrivateAttr()
    
    metadata: Dict = Field(default_factory=dict, description="Editable Metadata (Location, Headcount, etc.)")
    
    created_at: datetime = Field(default_factory=datetime.now)
    published_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    def __init__(self, **data):
        super().__init__(**data)
        if "policy" in data:
            self._policy = data["policy"]
        elif not hasattr(self, "_policy"):
            # Should not happen if policy is required, but Pydantic validation happens before this.
            # To make 'policy' required in __init__, we can't easily rely on Field(...) validation
            # since it's not a field.
            # Workaround: Check manually or accept that standard initialization requires 'policy'.
            pass

    @property
    def policy(self) -> JobPolicy:
        return self._policy

    @policy.setter
    def policy(self, value: JobPolicy):
        # Allow assignment only in DRAFT state
        if self.status != JobStatus.DRAFT:
            raise PolicyValidationError(
                f"Cannot update AI-Sensitive policy fields in {self.status} state. "
                "Job Posting is an Immutable AI Evaluation Schema."
            )
        self._policy = value

    def publish(self):
        """
        Transition DRAFT -> PUBLISHED.
        Locks the policy.
        """
        if self.status != JobStatus.DRAFT:
            raise JobStateError(f"Cannot publish job in {self.status} state.")
        
        # Validation is implicit in JobPolicy model
        self.status = JobStatus.PUBLISHED
        self.published_at = datetime.now()

    def close(self):
        """
        Transition PUBLISHED -> CLOSED.
        """
        if self.status != JobStatus.PUBLISHED:
            raise JobStateError(f"Cannot close job in {self.status} state. only PUBLISHED jobs can be CLOSED.")
        
        self.status = JobStatus.CLOSED
        self.closed_at = datetime.now()

    def update_policy(self, new_policy: JobPolicy):
        """
        Update policy. Allowed only in DRAFT state.
        STRICT: AI-Sensitive fields cannot be changed in PUBLISHED/CLOSED state.
        """
        # Setter logic will enforce validation
        self.policy = new_policy

    def update_metadata(self, new_metadata: Dict):
        """
        Update metadata. Allowed in DRAFT/PUBLISHED.
        """
        if self.status == JobStatus.CLOSED:
            raise JobStateError("Cannot update metadata for CLOSED job.")
        self.metadata.update(new_metadata)

    def create_session_config(self) -> SessionConfig:
        """
        Create a SessionConfig snapshot from the current policy.
        """
        return SessionConfig(
            total_question_limit=self.policy.total_question_limit,
            min_question_count=self.policy.min_question_count,
            question_timeout_sec=self.policy.question_timeout_sec,
            silence_timeout_sec=self.policy.silence_timeout_sec,
            mode=self.policy.mode,
            job_id=self.job_id,
            result_exposure=self.policy.result_exposure,
            early_exit_enabled=False
        )
