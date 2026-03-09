from typing import Any
from pydantic import BaseModel, ConfigDict

class BaseDTO(BaseModel):
    """
    IMH 프로젝트의 모든 DTO(Data Transfer Object)의 기반 클래스.
    
    Features:
        - from_attributes=True (ORM 객체 변환 지원)
        - str_strip_whitespace=True (문자열 공백 자동 제거)
    """
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        populate_by_name=True
    )


# -------------------------------------------------------------------------
# STT Provider DTOs
# -------------------------------------------------------------------------
class TranscriptSegmentDTO(BaseDTO):
    start: float
    end: float
    text: str

class TranscriptDTO(BaseDTO):
    text: str
    language: str | None = None
    segments: list[TranscriptSegmentDTO] = []


# -------------------------------------------------------------------------
# LLM Provider DTOs
# -------------------------------------------------------------------------
class LLMMessageDTO(BaseDTO):
    role: str  # "system", "user", "assistant"
    content: str

class LLMResponseDTO(BaseDTO):
    content: str
    token_usage: dict[str, int] | None = None
    finish_reason: str | None = None


# -------------------------------------------------------------------------
# Emotion Provider DTOs
# -------------------------------------------------------------------------
class EmotionResultDTO(BaseDTO):
    dominant_emotion: str
    scores: dict[str, float]  # e.g., {"happy": 0.9, "sad": 0.1}
    region: dict[str, int] | None = None  # x, y, w, h


# -------------------------------------------------------------------------
# Visual Provider DTOs
# -------------------------------------------------------------------------
class VisualResultDTO(BaseDTO):
    gaze_vector: list[float] | None = None
    pose_landmarks: list[dict] | None = None
    face_landmarks: list[dict] | None = None


# -------------------------------------------------------------------------
# Voice Provider DTOs
# -------------------------------------------------------------------------
class VoiceResultDTO(BaseDTO):
    pitch_mean: float | None = None
    pitch_min: float | None = None
    pitch_max: float | None = None
    intensity_mean: float | None = None
    intensity_min: float | None = None
    intensity_max: float | None = None
    jitter: float | None = None
    shimmer: float | None = None
    hnr: float | None = None  # Harmonics-to-Noise Ratio


# -------------------------------------------------------------------------
# PDF Provider DTOs
# -------------------------------------------------------------------------
class PDFPageDTO(BaseDTO):
    page_number: int
    text: str

class PDFExtractionResultDTO(BaseDTO):
    full_text: str
    pages: list[PDFPageDTO]
    metadata: dict[str, Any]


# -------------------------------------------------------------------------
# Embedding Provider DTOs (TASK-007)
# -------------------------------------------------------------------------
class EmbeddingRequestDTO(BaseDTO):
    text: str

class EmbeddingResponseDTO(BaseDTO):
    vector: list[float]
    dimension: int
    model_name: str | None = None
