from abc import ABC, abstractmethod
from packages.imh_core.dto import EmotionResultDTO
from packages.imh_providers.emotion.dto import VideoEmotionAnalysisResultDTO

class IEmotionProvider(ABC):
    @abstractmethod
    async def analyze_face(self, image_path: str) -> EmotionResultDTO:
        """
        Analyze face emotion from image path.
        Returns EmotionResultDTO.
        """
        pass

    @abstractmethod
    async def analyze_video(self, video_path: str) -> VideoEmotionAnalysisResultDTO:
        """
        Analyze video emotion frame by frame (1fps).
        Returns VideoEmotionAnalysisResultDTO.
        """
        pass
