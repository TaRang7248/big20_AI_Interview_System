import json
import logging
from typing import List, Optional

import aiohttp

from packages.imh_providers.llm.base import ILLMProvider
from packages.imh_core.dto import LLMMessageDTO, LLMResponseDTO

logger = logging.getLogger("imh_providers.ollama")

class OllamaLLMProvider(ILLMProvider):
    """
    Ollama Provider Implementation (TASK-032).
    Connects to local Ollama instance (default: http://localhost:11434).
    """
    
    def __init__(self, model_name: str, base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url.rstrip('/')
        
    async def chat(self, messages: List[LLMMessageDTO], system_prompt: Optional[str] = None, max_tokens: Optional[int] = None) -> LLMResponseDTO:
        url = f"{self.base_url}/api/chat"
        
        # Prepare messages
        ollama_messages = []
        if system_prompt:
            ollama_messages.append({"role": "system", "content": system_prompt})
            
        for msg in messages:
            ollama_messages.append({
                "role": msg.role,
                "content": msg.content
            })
            
        payload = {
            "model": self.model_name,
            "messages": ollama_messages,
            "stream": False,
            "options": {"num_predict": max_tokens} if max_tokens else {}
        }
        
        logger.debug(f"Sending request to Ollama ({self.model_name}): {len(ollama_messages)} messages")
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    
                    content = data.get("message", {}).get("content", "")
                    
                    # Estimate or extract usage if provided by Ollama
                    usage = {
                        "prompt_tokens": data.get("prompt_eval_count", 0),
                        "completion_tokens": data.get("eval_count", 0),
                        "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
                    }
                    
                    return LLMResponseDTO(
                        content=content.strip(),
                        token_usage=usage,
                        finish_reason=data.get("done_reason", "stop")
                    )
                    
            except aiohttp.ClientError as e:
                logger.error(f"Ollama API connection error: {e}")
                raise RuntimeError(f"Failed to communicate with Ollama: {e}")
            except Exception as e:
                logger.error(f"Unexpected error calling Ollama: {e}")
                raise
