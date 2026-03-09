from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class AnswerSubmissionDTO(BaseModel):
    """
    User submission for an interview question.
    """
    content: str = Field(..., description="Text content or file path reference")
    type: str = Field(..., description="Type of the answer: AUDIO, VIDEO, TEXT")
    duration_seconds: Optional[float] = Field(None, description="Duration of the answer in seconds if applicable")

class QuestionDTO(BaseModel):
    """
    Data Transfer Object for Interview Questions.
    Decoupled from internal domain models.
    """
    id: str
    content: str
    type: str
    time_limit_seconds: int
    sequence_number: int

class SessionResponseDTO(BaseModel):
    """
    Data Transfer Object for Interview Session Strings.
    """
    session_id: str
    status: str
    created_at: datetime
    current_question: Optional[QuestionDTO] = None
    total_questions: int
    progress_percentage: float

class SessionListDTO(BaseModel):
    """
    DTO for listing multiple sessions (Admin/User view).
    """
    sessions: List[SessionResponseDTO]
    total_count: int
