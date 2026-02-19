from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class SessionProjectionDTO(BaseModel):
    """
    CP1: Session Projection View (Read-Only Optimization).
    This DTO is for UI display purposes ONLY and must NOT be used for domain logic.
    """
    session_id: str
    status: str
    current_question: Optional[Dict[str, Any]] = None # Simplified view of current question
    progress: Dict[str, int] # {'answered': 0, 'total': 0}
    mode: str
    updated_at: datetime
