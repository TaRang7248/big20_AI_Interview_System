import logging
import asyncio
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

from packages.imh_providers.question import QuestionGenerator
from packages.imh_dto.rag_cache import RAGCacheDTO
from packages.imh_session.infrastructure.redis_rag_repository import RedisRAGRepository
from packages.imh_session.dto import SessionQuestion, SessionQuestionType
from packages.imh_service.ttl_resolver import TTLContextResolver

class CachedQuestionGenerator(QuestionGenerator):
    """
    RAG Cache Decorator (CP2).
    Wraps the real QuestionGenerator to add Read-Through Caching.
    """
    def __init__(
        self, 
        real_generator: QuestionGenerator, 
        repository: RedisRAGRepository,
        ttl_resolver: TTLContextResolver
    ):
        self.real_generator = real_generator
        self.repository = repository
        self.ttl_resolver = ttl_resolver
        self.logger = logging.getLogger("imh.cached_rag")

    async def generate_question(
        self, 
        job_id: str, 
        user_input: str, 
        history: List[Dict[str, str]],
        context_data: Optional[Dict[str, Any]] = None
    ) -> SessionQuestion:
        """
        Generates question with Cache-Aside logic.
        """
        # 1. Prepare Key Components (Mocking versioning for now)
        policy_version = context_data.get("policy_version", "v1") if context_data else "v1"
        prompt_version = "v1.0" # Should come from configuration
        model_name = "gpt-4" # Default model
        
        # Generation/Retrieval params (Fixed for now or from config)
        gen_params = {"temperature": 0.7} 
        ret_params = {"top_k": 3}

        key = self.repository._generate_key(
            job_id, policy_version, prompt_version, model_name, 
            user_input, gen_params, ret_params
        )

        # 2. Try Cache (Read Optimization)
        cached_result = self.repository.get(key)
        if cached_result:
            self.logger.info(f"RAG Cache HIT: {key}")
            # Reconstruct SessionQuestion from Cached Answer
            return SessionQuestion(
                id=str(uuid.uuid4()), # Generate new ID for this session instance
                content=cached_result.answer,
                source_type=SessionQuestionType.GENERATED,
                source_metadata={"cached": True, "key": key}
            )

        # 3. Miss -> Call Real Generator (Authority)
        self.logger.info(f"RAG Cache MISS: {key}. Calling Generator.")
        question = await self.real_generator.generate_question(job_id, user_input, history, context_data)
        
        # 4. Save to Cache (Async, Fire-and-Forget)
        # Resolve Dynamic TTL Context (Authority Check)
        try:
            ttl_context = self.ttl_resolver.resolve(job_id)
            ttl_seconds = self.repository.calculate_ttl(
                active_candidates=ttl_context.active_candidates,
                is_debug=ttl_context.is_debug,
                model_cost_high=ttl_context.model_cost_high
            )
        except Exception as e:
            self.logger.warning(f"TTL Resolution Failed: {e}. Using Default Safe TTL.")
            ttl_seconds = 86400 # Safe Default
        
        # Create DTO
        rag_dto = RAGCacheDTO(
            job_id=job_id,
            policy_version=policy_version,
            prompt_version=prompt_version,
            model_name=model_name,
            input_hash=key, # Storing full key or hash part
            answer=question.content,
            evidence=None, # Populate if available
            created_at=datetime.utcnow(),
            ttl_minutes=ttl_seconds // 60, # Store minutes for readability
            tokens_used=0, # Populate if available
            latency_ms=0
        )
        
        # Async Save (Non-blocking)
        # Note: In a real app, use a proper background task manager. 
        # Here we use asyncio.create_task for fire-and-forget simulation.
        asyncio.create_task(
            self.repository.save_async(key, rag_dto, ttl_seconds=ttl_seconds)
        )
        
        return question
