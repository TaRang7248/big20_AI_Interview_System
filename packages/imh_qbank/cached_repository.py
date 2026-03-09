from typing import List, Optional
from packages.imh_core.logging import get_logger
from .repository_interface import QuestionRepository
from .redis_repository import RedisCandidateRepository
from .domain import Question

logger = get_logger("imh_qbank.cached_repository")

class CachedQuestionRepository(QuestionRepository):
    """
    Composite Repository for Candidate Pool Caching (CP3).
    Implements Read-Through Strategy with Redis.
    Structure:
    - Service -> CachedQuestionRepository -> RedisCandidateRepository (Cache)
                                        -> SourceQuestionRepository (DB/File)
    Contract:
    - Source of Truth: SourceRepository
    - Cache Miss -> Load from Source -> Save to Cache
    - Write/Delete -> Update Source -> Invalidate Cache
    - Fallback: Redis failure -> Degradation to Source Only
    """

    def __init__(self, source_repository: QuestionRepository, redis_repository: RedisCandidateRepository):
        self.source = source_repository
        self.redis = redis_repository

    def save(self, question: Question) -> None:
        """
        Save to Source, then Invalidate Cache.
        No Write-Back (Redis -> Source) allowed.
        """
        # 1. Write to Source of Truth first
        self.source.save(question)
        
        # 2. Invalidate Cache (Delete Stale Data)
        try:
            self.redis.delete_question_cache(question.id)
            self.redis.invalidate_all_active_candidates()
        except Exception as e:
            logger.warning(f"Failed to invalidate cache after save: {e}. Data consistency relying on TTL.")

    def find_by_id(self, question_id: str) -> Optional[Question]:
        """
        Read-Through Strategy for Entity.
        Cache Hit -> Return
        Cache Miss -> Load Source -> Cache -> Return
        """
        # 1. Try Cache
        cached_q = self.redis.get_question(question_id)
        if cached_q:
            return cached_q
            
        # 2. Cache Miss: Load from Source
        q = self.source.find_by_id(question_id)
        
        # 3. Save to Cache if exists
        if q:
            try:
                self.redis.save_question(q)
            except Exception as e:
                 logger.warning(f"Failed to populate cache for question {question_id}: {e}")
        
        return q

    def find_all_active(self) -> List[Question]:
        """
        Read-Through Strategy for Candidate List.
        Cache Hit -> Return
        Cache Miss -> Load Source -> Cache -> Return
        """
        # 1. Try Cache
        cached_list = self.redis.get_all_active_candidates()
        if cached_list is not None:
            return cached_list
            
        # 2. Cache Miss: Load from Source
        questions = self.source.find_all_active()
        
        # 3. Save to Cache
        try:
            self.redis.save_all_active_candidates(questions)
        except Exception as e:
             logger.warning(f"Failed to populate candidate list cache: {e}")
             
        return questions

    def delete(self, question_id: str) -> bool:
        """
        Soft Delete in Source, then Invalidate Cache.
        """
        # 1. Execute in Source
        deleted = self.source.delete(question_id)
        
        # 2. Invalidate Cache
        if deleted:
            try:
                self.redis.delete_question_cache(question_id)
                self.redis.invalidate_all_active_candidates()
            except Exception as e:
                logger.warning(f"Failed to invalidate cache after delete: {e}")
                
        return deleted
