from abc import ABC, abstractmethod
from packages.imh_core.dto import VoiceResultDTO

class IVoiceProvider(ABC):
    @abstractmethod
    async def analyze_audio(self, audio_path: str) -> VoiceResultDTO:
        """
        Analyze voice features (pitch, jitter, etc.) from audio file.
        Returns VoiceResultDTO.
        """
        pass
