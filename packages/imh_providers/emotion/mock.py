import asyncio
from packages.imh_providers.emotion.base import IEmotionProvider
from packages.imh_core.dto import EmotionResultDTO
from packages.imh_providers.emotion.dto import VideoEmotionAnalysisResultDTO, FrameEmotionDTO, VideoEmotionAnalysisMetadataDTO, EmotionScoreDTO
from packages.imh_core.config import IMHConfig

class MockEmotionProvider(IEmotionProvider):
    def __init__(self, config: IMHConfig = None):
        self.config = config
        self.latency_ms = 0
        if config and hasattr(config, 'MOCK_LATENCY_MS'):
            self.latency_ms = config.MOCK_LATENCY_MS

    async def analyze_face(self, image_path: str) -> EmotionResultDTO:
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)
            
        return EmotionResultDTO(
            dominant_emotion="neutral",
            scores={"neutral": 1.0},
            region={"x": 10, "y": 10, "w": 100, "h": 100}
        )

    async def analyze_video(self, video_path: str) -> VideoEmotionAnalysisResultDTO:
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)
        
        # Mock 3 frames
        frames = []
        for i in range(3):
            frames.append(FrameEmotionDTO(
                timestamp=float(i),
                face_detected=True,
                dominant_emotion="neutral",
                emotion_scores=EmotionScoreDTO(neutral=0.9, happy=0.1),
                box=[10, 10, 100, 100]
            ))
            
        return VideoEmotionAnalysisResultDTO(
            metadata=VideoEmotionAnalysisMetadataDTO(
                total_duration=3.0,
                total_frames_analyzed=3,
                model="MockEmotion"
            ),
            results=frames
        )
