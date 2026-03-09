from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

# --- Request Schemas ---

class SessionCreateRequest(BaseModel):
    job_id: str
    user_id: str = Field(..., description="Mock User ID for prototyping")

class AnswerSubmitRequest(BaseModel):
    answer_type: Literal["TEXT", "AUDIO", "VIDEO"]
    file_path: Optional[str] = None
    text_content: Optional[str] = None
    duration_seconds: float = 0.0

# --- Response Schemas ---

class QuestionSchema(BaseModel):
    sequence: int
    content: str
    q_type: str  # "MAIN", "FOLLOWUP" based on logic

class SessionResponse(BaseModel):
    session_id: str
    status: str
    current_question_index: int
    total_questions: int
    current_question: Optional[QuestionSchema] = None
    created_at: Optional[datetime] = None

class JobPostingResponse(BaseModel):
    job_id: str
    title: str
    status: str
    # Simplified for admin list

class AdminSessionSummary(BaseModel):
    session_id: str
    job_id: str
    user_id: str
    status: str
    score: Optional[float] = None
    created_at: Optional[datetime] = None
