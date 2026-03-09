from typing import Dict, Any, Optional, Protocol
from pydantic import BaseModel, Field

class MetricsResult(BaseModel):
    """
    STT 평가 지표를 담는 DTO
    """
    wer: float = Field(..., description="Word Error Rate")
    cer: float = Field(..., description="Character Error Rate")
    digit_accuracy: Optional[float] = Field(None, description="숫자 인식 정확도 (0~1)")
    foreign_term_accuracy: Optional[float] = Field(None, description="영어/외래어 단어 생성 정확도 (0~1)")

class STTResultDTO(BaseModel):
    """
    STTEngineProtocol을 구현하는 STT 모델이 반환해야 하는 표준 결과 DTO
    """
    raw_text: str = Field(..., description="정규화 전 최초 STT 출력 텍스트")
    normalized_text: str = Field(..., description="기본 정규화(공백, 구두점, 숫자 등) 처리가 완료된 텍스트")
    inference_time_seconds: float = Field(..., description="순수 STT 추론에 소요된 시간 (초)")
    audio_duration_seconds: float = Field(..., description="입력 오디오 파일의 총 재생 길이 (초)")
    rtf: float = Field(..., description="Real Time Factor (inference_time / audio_duration)")
    peak_vram_mb: Optional[float] = Field(None, description="추론 중 측정된 Peak VRAM (MB)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="모델 이름, 디바이스 등 부가 정보")

class TestCase(BaseModel):
    """
    STT 평가를 위한 단일 테스트 케이스 DTO
    """
    audio_path: str = Field(..., description="오디오 파일 경로")
    ground_truth: str = Field(..., description="정답 텍스트")
    scenario_id: Optional[str] = Field(None, description="시나리오 또는 카테고리 ID")

class STTEngineProtocol(Protocol):
    """
    벤치마크 대상 STT 엔진이 반드시 구현해야 하는 프로토콜
    """
    def load_model(self) -> None:
        """모델을 메모리 및 디바이스(VRAM)에 로드한다."""
        ...

    def warmup(self) -> None:
        """First Token 지연 왜곡 방지를 위해 1회 더미 추론을 수행한다."""
        ...

    def transcribe(self, audio_path: str) -> STTResultDTO:
        """
        주어진 오디오 파일을 16kHz mono로 리샘플링한 뒤 추론하여
        지정된 규격의 DTO를 반환한다.
        """
        ...
