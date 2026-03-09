from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

class VisualResultDTO(BaseModel):
    """
    Data Transfer Object for Visual Analysis Results (TASK-010)
    Focuses on Presence, Attention, and Pose as per Phase 2 Baseline.
    """
    has_face: bool = Field(..., description="Whether a face is detected in the frame")
    
    # Analysis Scores (0.0 - 1.0)
    presence_score: float = Field(..., description="Confidence score for user presence")
    attention_score: float = Field(..., description="Confidence score for visual attention (gaze)")
    pose_score: float = Field(..., description="Confidence score for posture stability")
    
    # State Judgments
    is_looking_center: bool = Field(..., description="Whether the user is looking at the center/camera")
    is_posture_good: bool = Field(..., description="Whether the user has good posture")
    
    # Metadata for debugging or future extension
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Raw analysis data (e.g., landmark coordinates)")
