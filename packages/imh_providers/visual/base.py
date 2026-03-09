from abc import ABC, abstractmethod
from packages.imh_core.dto import VisualResultDTO

class IVisualProvider(ABC):
    @abstractmethod
    async def analyze_frame(self, image_path: str) -> VisualResultDTO:
        """
        Analyze visual features (gaze, pose) from image frame.
        Returns VisualResultDTO.
        """
        pass
