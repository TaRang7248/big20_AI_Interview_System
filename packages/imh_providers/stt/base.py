from abc import ABC, abstractmethod
from packages.imh_core.dto import TranscriptDTO

class ISTTProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio_file_path: str) -> TranscriptDTO:
        """
        Audio file path is passed, returns TranscriptDTO.
        Async method for non-blocking I/O.
        """
        pass
