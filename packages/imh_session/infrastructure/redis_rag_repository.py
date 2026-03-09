import logging
import json
import hashlib
from typing import Optional, Any
from datetime import datetime, timedelta
import asyncio

from packages.imh_dto.rag_cache import RAGCacheDTO
from packages.imh_core.infra.redis import RedisClient
from redis.exceptions import RedisError

class RedisRAGRepository:
    """
    Redis Repository for RAG Result Cache (CP2).
    Implements Read Optimization Only. Not Authority.
    """
    TTL_DEFAULT_SECONDS = 86400  # 24 Hours
    TTL_HIGH_TRAFFIC_SECONDS = 172800 # 48 Hours
    TTL_DEBUG_SECONDS = 3600 # 1 Hour

    def __init__(self):
        self.redis = RedisClient.get_instance()
        self.logger = logging.getLogger("imh.rag_cache")

    def _generate_key(
        self, 
        job_id: str, 
        policy_version: str, 
        prompt_version: str,
        model_name: str,
        user_input: str,
        generation_params: dict,
        retrieval_params: dict
    ) -> str:
        """
        Generates Versioned Cache Key based on CP2 Plan.
        Key = rag:{job_id}:{policy_version}:{hash(components)}
        """
        # 1. Normalize Input (Trim, Collapse WS, Normalize Line Breaks, Preserve Case)
        normalized_input = " ".join(user_input.strip().split()).replace("\r\n", "\n").replace("\r", "\n")
        
        # 2. Construct Component String (Fixed Order)
        # Components: PromptVer + Model + Params + RetrievalParams + NormalizedInput
        # Generation/Retrieval params must be sorted to ensure deterministic string
        gen_param_str = json.dumps(generation_params, sort_keys=True)
        ret_param_str = json.dumps(retrieval_params, sort_keys=True)
        
        components = f"{prompt_version}|{model_name}|{gen_param_str}|{ret_param_str}|{normalized_input}"
        
        # 3. Hash
        component_hash = hashlib.sha256(components.encode("utf-8")).hexdigest()
        
        # 4. Final Key
        return f"rag:{job_id}:{policy_version}:{component_hash}"

    def get(self, key: str) -> Optional[RAGCacheDTO]:
        """
        Retrieves cached RAG result.
        Returns None on Miss or Redis Error (Graceful Degradation).
        """
        try:
            data = self.redis.get(key)
            if not data:
                return None
            
            # Simple Deserialization
            payload = json.loads(data)
            return RAGCacheDTO(**payload)
            
        except RedisError as e:
            self.logger.warning(f"Redis RAG Cache unavailable (Get): {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error deserializing RAG cache: {e}")
            return None

    async def save_async(self, key: str, dto: RAGCacheDTO, ttl_seconds: int = TTL_DEFAULT_SECONDS):
        """
        Asynchronously saves RAG result to Redis.
        Fire-and-forget logic should be handled by caller (using asyncio.create_task).
        This method performs the actual Redis I/O.
        """
        try:
            payload = dto.json()
            # Use setex for atomic Set + TTL
            self.redis.setex(key, timedelta(seconds=ttl_seconds), payload)
            self.logger.info(f"Saved RAG Cache: {key} (TTL: {ttl_seconds}s)")
        except RedisError as e:
            self.logger.warning(f"Redis RAG Cache unavailable (Save): {e}")
        except Exception as e:
            self.logger.error(f"Error saving RAG cache: {e}")
            
    def calculate_ttl(self, active_candidates: int, is_debug: bool = False, model_cost_high: bool = False) -> int:
        """
        Determines TTL based on Dynamic Rules (CP2).
        """
        if is_debug:
            return self.TTL_DEBUG_SECONDS
        
        if active_candidates > 100 or model_cost_high:
            return self.TTL_HIGH_TRAFFIC_SECONDS
            
        return self.TTL_DEFAULT_SECONDS
