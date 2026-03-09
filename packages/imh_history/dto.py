from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class HistoryMetadata(BaseModel):
    """
    Metadata for a stored interview report.
    Used for list views without loading the full report.
    """
    interview_id: str = Field(..., description="Unique identifier for the interview")
    timestamp: datetime = Field(..., description="When the interview/report was saved")
    total_score: float = Field(..., description="Total score from the report header")
    grade: str = Field(..., description="Grade from the report header")
    job_category: str = Field(..., description="Job Category from the report header")
    job_id: Optional[str] = Field(default=None, description="Job ID from the report header")
    status: str = Field(default="COMPLETED", description="Session Status (COMPLETED/EVALUATED)")
    started_at: Optional[datetime] = Field(default=None, description="Interview start time")
    file_path: str = Field(..., description="Relative path to the storage file")
