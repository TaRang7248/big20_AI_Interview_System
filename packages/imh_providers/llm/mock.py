import asyncio
from typing import Optional, List
from packages.imh_providers.llm.base import ILLMProvider
from packages.imh_core.dto import LLMMessageDTO, LLMResponseDTO
from packages.imh_core.config import IMHConfig

class MockLLMProvider(ILLMProvider):
    def __init__(self, config: IMHConfig = None):
        self.config = config
        self.latency_ms = 0
        if config and hasattr(config, 'MOCK_LATENCY_MS'):
            self.latency_ms = config.MOCK_LATENCY_MS

    async def chat(self, messages: List[LLMMessageDTO], system_prompt: Optional[str] = None) -> LLMResponseDTO:
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)
            
        return LLMResponseDTO(
            content="This is a mock LLM response based on the input.",
            token_usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            finish_reason="stop"
        )
