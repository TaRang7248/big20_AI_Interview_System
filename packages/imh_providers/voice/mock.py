import asyncio
from packages.imh_providers.voice.base import IVoiceProvider
from packages.imh_core.dto import VoiceResultDTO
from packages.imh_core.config import IMHConfig

class MockVoiceProvider(IVoiceProvider):
    def __init__(self, config: IMHConfig = None):
        self.config = config
        self.latency_ms = 0
        if config and hasattr(config, 'MOCK_LATENCY_MS'):
            self.latency_ms = config.MOCK_LATENCY_MS

    async def analyze_audio(self, audio_path: str) -> VoiceResultDTO:
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)
            
        return VoiceResultDTO(
            pitch_mean=120.5,
            jitter=0.015,
            shimmer=0.03,
            hnr=20.5
        )
