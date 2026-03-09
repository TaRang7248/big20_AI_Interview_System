from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ReportHeader(BaseModel):
    """
    Summary section of the report.
    """
    total_score: float = Field(..., description="Weighted total score (0-100)")
    grade: str = Field(..., description="Letter grade (S/A/B/C/D)")
    job_category: str = Field(..., description="Job Category (DEV or NON_TECH)")
    job_id: Optional[str] = Field(default=None, description="Linked Job Posting ID")
    keywords: List[str] = Field(default_factory=list, description="Top keywords representing the candidate")

class ReportDetail(BaseModel):
    """
    Detailed analysis for a specific rubric category or item.
    """
    category: str = Field(..., description="Evaluation Category Name")
    score: float = Field(..., description="Category score")
    level_description: str = Field(..., description="Textual description of the score level")
    feedback: str = Field(..., description="Specific feedback based on tag_code")
    key_evidence: List[str] = Field(default_factory=list, description="List of evidence strings")
    tag_code: str = Field(..., description="Original tag code for reference")

class ReportFooter(BaseModel):
    """
    Closing section with aggregated insights.
    """
    strengths: List[str] = Field(default_factory=list, description="List of strong points")
    weaknesses: List[str] = Field(default_factory=list, description="List of weak points")
    actionable_insights: List[str] = Field(default_factory=list, description="Suggestions for improvement")

class InterviewReport(BaseModel):
    """
    Final Output DTO for the Reporting Layer.
    Structure designed for UI consumption.
    """
    version: str = Field("1.0", description="Schema version")
    header: ReportHeader
    details: List[ReportDetail]
    footer: ReportFooter
    raw_debug_info: Optional[Dict[str, Any]] = Field(None, description="Debugging info (optional)")
