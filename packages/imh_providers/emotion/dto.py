from pydantic import BaseModel, Field
from packages.imh_core.dto import BaseDTO

class EmotionScoreDTO(BaseDTO):
    neutral: float = 0.0
    happy: float = 0.0
    sad: float = 0.0
    angry: float = 0.0
    fear: float = 0.0
    surprise: float = 0.0
    disgust: float = 0.0

class FrameEmotionDTO(BaseDTO):
    timestamp: float
    face_detected: bool
    dominant_emotion: str | None = None
    emotion_scores: EmotionScoreDTO | None = None
    # x, y, w, h
    box: list[int] | None = None

class VideoEmotionAnalysisMetadataDTO(BaseDTO):
    total_duration: float
    total_frames_analyzed: int
    model: str

class VideoEmotionAnalysisResultDTO(BaseDTO):
    metadata: VideoEmotionAnalysisMetadataDTO
    results: list[FrameEmotionDTO]
