import logging
import json
import hashlib
from typing import Optional, Dict, Any, List
from datetime import timedelta

from packages.imh_core.infra.redis import RedisClient
from packages.imh_core.constants import LOGICAL_PROMPT_VERSION, MAX_PROMPT_CACHE_SIZE_BYTES
from redis.exceptions import RedisError


class RedisPromptRepository:
    """
    CP4: Prompt Composition Cache Repository.
    Responsible for caching composed prompts to reduce composition overhead.
    Follows 'Read Optimization Only' contract.
    """
    
    TTL_SECONDS = 3600  # Default TTL 1 hour
    TTL_JITTER_RANGE = 300 # +/- 5 minutes jitter
    LOCK_TTL_SECONDS = 5 # Very short lock for stampede protection

    def __init__(self):
        self.redis = RedisClient.get_instance()
        self.logger = logging.getLogger("imh.prompt_cache")


    def _generate_key(
        self,
        snapshot_id: str,
        persona_id: str,
        interview_mode: str,
        job_policy_snapshot_hash: str,
        model_id: str,
        input_hash: str
    ) -> str:
        """
        Generates Cache Key ensuring Input Completeness.
        Includes Logical Prompt Version Identifier.
        """
        # Logical Version is embedded in the key structure
        # Key Pattern: prompt:{version}:{snapshot}:{persona}:{mode}:{policy}:{model}:{input}
        components = [
            "prompt",
            LOGICAL_PROMPT_VERSION, # Essential for Anti-Corruption
            snapshot_id,
            persona_id,
            interview_mode,
            job_policy_snapshot_hash, 
            model_id,
            input_hash
        ]
        return ":".join(components)

    def get_prompt(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Fail-Open Read.
        Returns None on any Redis failure or Miss.
        """
        try:
            val = self.redis.get(key)
            if val:
                return json.loads(val)
            return None
        except RedisError as e:
            # Observability: Log failure but do not break flow
            self.logger.warning(f"Redis Prompt Cache Read Failed: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error deserializing Prompt cache: {e}")
            return None

    def save_prompt(self, key: str, prompt_data: Dict[str, Any], ttl: int = TTL_SECONDS):
        """
        Best-Effort Write.
        Fire-and-forget or async saving is recommended in service layer.
        """
        try:
            # Apply Jitter
            import random
            jitter = random.randint(0, self.TTL_JITTER_RANGE)
            final_ttl = ttl + jitter
            
            # Serialize
            val = json.dumps(prompt_data)
            
            # Max Size Check (Optimization Skip)
            size_bytes = len(val.encode('utf-8'))
            if size_bytes > MAX_PROMPT_CACHE_SIZE_BYTES:
                self.logger.warning(f"Prompt Cache Skip: Size ({size_bytes}B) exceeds limit ({MAX_PROMPT_CACHE_SIZE_BYTES}B). Key: {key}")
                return

            # Set with TTL
            self.redis.setex(key, timedelta(seconds=final_ttl), val)

        except RedisError as e:
             # Observability: Log failure
            self.logger.warning(f"Redis Prompt Cache Write Failed: {e}")
        except Exception as e:
            self.logger.error(f"Error saving Prompt cache: {e}")

    def invalidate_by_pattern(self, pattern: str):
        """
        Manual Invalidation Support.
        Use with caution.
        """
        try:
            # SCAN is better strictly speaking, but KEYS is acceptable for admin tools if pattern is specific
            keys = self.redis.keys(pattern)
            if keys:
                self.redis.delete(*keys)
        except Exception as e:
            self.logger.error(f"Redis Invalidation Failed: {e}")

    def try_acquire_lock(self, key: str) -> bool:
        """
        Stampede Protection: Try to acquire a fast lock.
        Returns True if acquired (Leader), False if not (Follower).
        Follows Fail-Open: If Redis fails, return True to allow generation.
        """
        lock_key = f"lock:{key}"
        try:
            # NX=True (Only set if not exists), EX=Lock TTL
            result = self.redis.set(lock_key, "LOCKED", ex=self.LOCK_TTL_SECONDS, nx=True)
            return bool(result)
        except Exception as e:
            self.logger.warning(f"Redis Lock Check Failed: {e}")
            return True # Fail-Open: Allow generation if lock check fails

