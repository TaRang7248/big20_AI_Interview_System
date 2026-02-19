import logging
import time
import hashlib
import asyncio
from typing import Dict, Any, Optional

from packages.imh_session.infrastructure.redis_prompt_repository import RedisPromptRepository
from packages.imh_core.constants import LOGICAL_PROMPT_VERSION

class PromptComposer:
    """
    Base Prompt Composer.
    In a real scenario, this would format the prompt string from templates and context.
    """
    def compose(self, context: Dict[str, Any]) -> str:
        # Simulate composition cost
        # Here we just dump context as string for demonstration
        return f"System: You are an interviewer.\nContext: {context}"

class CachedPromptComposer:
    """
    CP4: Cached Prompt Composer.
    Wraps the composition logic with a Redis-based Read-Through Cache.
    """
    
    def __init__(self, repository: RedisPromptRepository):
        self.repository = repository
        self.real_composer = PromptComposer()
        self.logger = logging.getLogger("imh.prompt_composition")

    def compose_prompt(self, context: Dict[str, Any]) -> str:
        """
        Composes prompt with Cache-Aside strategy.
        Fail-Open: If Redis fails, proceeds to compose.
        """
        
        # 1. Extract Key Components from Context
        # These must be present in the context passed from Service/Engine
        snapshot_id = context.get("snapshot_id", "unknown_snap")
        persona_id = context.get("persona_id", "default_persona")
        interview_mode = context.get("interview_mode", "REAL")
        policy_hash = context.get("policy_hash", "no_policy")
        model_id = context.get("model_id", "gpt-4")
        
        # Input Hash: Hash of all other dynamic inputs (e.g., history, user input)
        # For simplicity, we assume 'input_data' in context contains these
        input_data = context.get("input_data", {})
        import json
        input_str = json.dumps(input_data, sort_keys=True)
        input_hash = hashlib.sha256(input_str.encode()).hexdigest()

        # 2. Generate Key
        key = self.repository._generate_key(
            snapshot_id, persona_id, interview_mode, 
            policy_hash, model_id, input_hash
        )

        # 3. Try Cache (Read Optimization)
        try:
            cached_prompt = self.repository.get_prompt(key)
            if cached_prompt:
                self.logger.info(f"Prompt Cache HIT: {key}")
                return cached_prompt["content"]
        except Exception as e:
             # Fail-Open: Log and proceed
             self.logger.warning(f"Prompt Cache Access Failed: {e}")

        # 4. Miss -> Stampede Protection & Compose
        # Try to acquire lock. If failed, it means someone else is computing.
        # We DO NOT wait (Fail-Fast/Open), we just compute locally but skip saving to reduce write contention?
        # Actually user said: "If concurrency control fails (lock busy), just allow generation".
        # So we just track if we are the leader.
        is_leader = self.repository.try_acquire_lock(key)
        
        self.logger.info(f"Prompt Cache MISS: {key}. Leader: {is_leader}. Composing...")
        start_time = time.time()
        
        prompt_content = self.real_composer.compose(context)
        
        duration = time.time() - start_time


        # 5. Save to Cache (Best Effort)
        # Only Leader saves to prevent redundant writes (Stampede Mitigation)
        # Fail-Open: If lock check failed (returned True), we save.
        if is_leader:
            try:
                prompt_data = {
                    "content": prompt_content,
                    "version": LOGICAL_PROMPT_VERSION,
                    "created_at": time.time(),
                    "latency": duration
                }
                # Calculate TTL based on context or use default
                self.repository.save_prompt(key, prompt_data)
            except Exception as e:
                self.logger.warning(f"Prompt Cache Save Failed: {e}")
        else:
            self.logger.info(f"Skipping Cache Save (Follower): {key}")


        return prompt_content
