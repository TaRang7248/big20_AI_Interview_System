import json
from typing import List, Optional, Dict, Any
from packages.imh_core.infra.redis import RedisClient
from packages.imh_core.logging import get_logger
from .domain import Question, QuestionStatus, SourceMetadata, SourceType
from datetime import datetime

logger = get_logger("imh_qbank.redis")

class RedisCandidateRepository:
    """
    Redis Cache Implementation for Candidate Questions.
    Responsibility:
    - Cache Question Entities (Single Source of Truth Projection)
    - Cache Candidate Lists (Active Questions Snapshot)
    - Handle Serialization/Deserialization
    - TTL Management (Static Policy: 1 Hour default)
    """

    KEY_PREFIX_ENTITY = "qbank:question:"
    KEY_PREFIX_LIST = "qbank:candidates:"
    TTL_SECONDS = 3600  # 1 Hour

    def __init__(self):
        try:
            self._redis = RedisClient.get_instance()
        except Exception as e:
            logger.error(f"Failed to connect to Redis for Candidate Cache: {e}")
            self._redis = None

    def _check_connection(self) -> bool:
        return self._redis is not None

    def _to_dict(self, q: Question) -> Dict[str, Any]:
        """Convert Question domain object to dictionary for JSON serialization."""
        return {
            'id': q.id,
            'content': q.content,
            'tags': q.tags,
            'difficulty': q.difficulty,
            'job_role': q.job_role,
            'source': {
                'source_type': q.source.source_type.value,
                'bank_id': q.source.bank_id,
                'generation_context': q.source.generation_context,
                'created_at': q.source.created_at.isoformat()
            },
            'status': q.status.value,
            'updated_at': q.updated_at.isoformat()
        }

    def _from_dict(self, data: Dict[str, Any]) -> Optional[Question]:
        """Convert dictionary to Question domain object."""
        try:
            return Question(
                id=data['id'],
                content=data['content'],
                tags=data['tags'],
                difficulty=data['difficulty'],
                job_role=data.get('job_role'),
                source=SourceMetadata(
                    source_type=SourceType(data['source']['source_type']),
                    bank_id=data['source'].get('bank_id'),
                    generation_context=data['source'].get('generation_context'),
                    created_at=datetime.fromisoformat(data['source']['created_at'])
                ),
                status=QuestionStatus(data['status']),
                updated_at=datetime.fromisoformat(data['updated_at'])
            )
        except Exception as e:
            logger.error(f"Failed to convert dict to Question: {e}")
            return None

    def get_question(self, question_id: str) -> Optional[Question]:
        if not self._check_connection():
            return None
            
        key = f"{self.KEY_PREFIX_ENTITY}{question_id}"
        try:
            data_str = self._redis.get(key)
            if data_str:
                data_dict = json.loads(data_str)
                return self._from_dict(data_dict)
        except Exception as e:
            logger.error(f"Redis get_question failed: {e}")
            # Fallback to source
        return None

    def save_question(self, question: Question):
        if not self._check_connection():
            return
            
        key = f"{self.KEY_PREFIX_ENTITY}{question.id}"
        try:
            data_dict = self._to_dict(question)
            data_str = json.dumps(data_dict, ensure_ascii=False)
            self._redis.setex(key, self.TTL_SECONDS, data_str)
        except Exception as e:
            logger.error(f"Redis save_question failed: {e}")

    def delete_question_cache(self, question_id: str):
        if not self._check_connection():
            return

        key = f"{self.KEY_PREFIX_ENTITY}{question_id}"
        try:
            self._redis.delete(key)
        except Exception as e:
            logger.error(f"Redis delete_question_cache failed: {e}")

    def get_all_active_candidates(self) -> Optional[List[Question]]:
        if not self._check_connection():
            return None

        key = f"{self.KEY_PREFIX_LIST}all_active"
        try:
            data_str = self._redis.get(key)
            if data_str:
                items = json.loads(data_str)
                questions = []
                for item_dict in items:
                    q = self._from_dict(item_dict)
                    if q:
                        # Stale Data Protection: Double check if active
                        if q.is_active():
                            questions.append(q)
                return questions
        except Exception as e:
             logger.error(f"Redis get_all_active_candidates failed: {e}")
             # Fallback to source
        return None

    def save_all_active_candidates(self, questions: List[Question]):
        if not self._check_connection():
            return

        key = f"{self.KEY_PREFIX_LIST}all_active"
        try:
            data_list = [self._to_dict(q) for q in questions]
            data_str = json.dumps(data_list, ensure_ascii=False)
            self._redis.setex(key, self.TTL_SECONDS, data_str)
        except Exception as e:
            logger.error(f"Redis save_all_active_candidates failed: {e}")

    def invalidate_all_active_candidates(self):
        if not self._check_connection():
            return

        key = f"{self.KEY_PREFIX_LIST}all_active"
        try:
            self._redis.delete(key)
        except Exception as e:
            logger.error(f"Redis invalidate_all_active_candidates failed: {e}")
