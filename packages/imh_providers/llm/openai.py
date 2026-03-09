import logging
import os
from typing import List, Optional

import openai

from packages.imh_providers.llm.base import ILLMProvider
from packages.imh_core.dto import LLMMessageDTO, LLMResponseDTO

logger = logging.getLogger("imh_providers.openai")

class OpenAILLMProvider(ILLMProvider):
    """
    OpenAI Provider Implementation (TASK-032).
    Connects to OpenAI's Cloud API.
    """
    
    def __init__(self, model_name: str = "gpt-4o", api_key: Optional[str] = None):
        auth_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not auth_key:
            raise ValueError("OPENAI_API_KEY must be provided or set in environment variables")
            
        self.client = openai.AsyncOpenAI(api_key=auth_key)
        self.model_name = model_name
        
    async def chat(self, messages: List[LLMMessageDTO], system_prompt: Optional[str] = None, max_tokens: Optional[int] = None) -> LLMResponseDTO:
        openai_messages = []
        if system_prompt:
            openai_messages.append({"role": "system", "content": system_prompt})
            
        for msg in messages:
            openai_messages.append({"role": msg.role, "content": msg.content})
            
        try:
            logger.debug(f"Sending request to OpenAI ({self.model_name}): {len(openai_messages)} messages")
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=openai_messages,
                stream=False,
                **(({"max_tokens": max_tokens}) if max_tokens else {})
            )
            
            choice = response.choices[0]
            usage = response.usage
            
            usage_dict = {
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0
            }
            
            return LLMResponseDTO(
                content=choice.message.content or "",
                token_usage=usage_dict,
                finish_reason=choice.finish_reason
            )
            
        except openai.OpenAIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise RuntimeError(f"Failed to communicate with OpenAI: {e}")
        except Exception as e:
            logger.error(f"Unexpected error calling OpenAI: {e}")
            raise
