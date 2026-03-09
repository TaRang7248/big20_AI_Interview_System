from abc import ABC, abstractmethod
from typing import Optional, List
from packages.imh_core.dto import LLMMessageDTO, LLMResponseDTO

class ILLMProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: List[LLMMessageDTO],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponseDTO:
        """
        Chat with LLM.
        Args:
            messages: List of LLMMessageDTO
            system_prompt: Optional system prompt override
            max_tokens: Optional hard cap on output tokens (num_predict / max_tokens)
        Returns:
            LLMResponseDTO
        """
        pass
