import asyncio
from packages.imh_providers.stt.base import ISTTProvider
from packages.imh_core.dto import TranscriptDTO, TranscriptSegmentDTO
from packages.imh_core.config import IMHConfig

class MockSTTProvider(ISTTProvider):
    def __init__(self, config: IMHConfig = None):
        # Config might not be strictly typed throughout, but good to have
        self.config = config
        self.latency_ms = 0
        if config and hasattr(config, 'MOCK_LATENCY_MS'):
            self.latency_ms = config.MOCK_LATENCY_MS

    async def transcribe(self, audio_file_path: str) -> TranscriptDTO:
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)
            
        return TranscriptDTO(
            text="This is a mock transcription result.",
            language="ko",
            segments=[
                TranscriptSegmentDTO(start=0.0, end=1.0, text="This is"),
                TranscriptSegmentDTO(start=1.0, end=2.0, text="a mock"),
                TranscriptSegmentDTO(start=2.0, end=3.0, text="transcription result.")
            ]
        )
