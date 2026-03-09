from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class EvidenceData(BaseModel):
    """
    Evidence for the evaluation score.
    Fields correspond to the Rubric Guide's logic requirements.
    """
    # Job Competency
    cosine_similarity: Optional[float] = Field(None, description="Cosine similarity with RAG result")
    keyword_match: Optional[List[str]] = Field(None, description="Matched keywords found in answer")
    ast_complexity: Optional[float] = Field(None, description="Cyclomatic complexity or similar metric")
    
    # Problem Solving
    hint_count: Optional[int] = Field(None, description="Number of hints used in the turn")
    rephrasing_detected: Optional[bool] = Field(None, description="Whether rephrasing was detected")
    
    # Communication
    star_structure: Optional[bool] = Field(None, description="Whether STAR structure was followed")
    semantic_relevance: Optional[float] = Field(None, description="Relevance score with question")
    
    # Attitude / Non-verbal
    gaze_center_percent: Optional[float] = Field(None, description="Percentage of time gaze was in center box")
    negative_emotion_percent: Optional[float] = Field(None, description="Percentage of negative emotions (Fear/Sad)")
    
    # Generic extension for future-proofing
    raw_metrics: Optional[Dict[str, Any]] = Field(None, description="Additional raw metrics if needed")

class RubricScoreItem(BaseModel):
    """
    Score and evidence for a single rubric category.
    """
    category: str = Field(..., description="Evaluation Category Name (e.g. 직무 역량)")
    tag_code: str = Field(..., description="Identifier for the evaluation item (e.g. capability.knowledge)")
    score: int = Field(..., ge=1, le=5, description="Score 1-5")
    rationale: str = Field(..., description="Reasoning for the score")
    evidence_data: EvidenceData = Field(..., description="Structured evidence data")
    improvement_feedback: Optional[str] = Field(None, description="Feedback for improvement")

class EvaluationResult(BaseModel):
    """
    Final aggregated result of the evaluation.
    """
    total_score: float = Field(..., description="Weighted total score")
    details: List[RubricScoreItem] = Field(..., description="List of detailed scores per category")
    details: List[RubricScoreItem] = Field(..., description="List of detailed scores per category")
    job_category: str = Field(..., description="Job Category (DEV or NON_TECH)")
    job_id: Optional[str] = Field(None, description="Job ID")
