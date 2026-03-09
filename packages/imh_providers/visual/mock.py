import asyncio
from packages.imh_providers.visual.base import IVisualProvider
from packages.imh_core.dto import VisualResultDTO
from packages.imh_core.config import IMHConfig

class MockVisualProvider(IVisualProvider):
    def __init__(self, config: IMHConfig = None):
        self.config = config
        self.latency_ms = 0
        if config and hasattr(config, 'MOCK_LATENCY_MS'):
            self.latency_ms = config.MOCK_LATENCY_MS

    async def analyze_frame(self, image_path: str) -> VisualResultDTO:
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)
            
        return VisualResultDTO(
            gaze_vector=[0.1, 0.2, 0.9],
            pose_landmarks=[{"x": 0.5, "y": 0.5, "visible": True}],
            face_landmarks=[]
        )
