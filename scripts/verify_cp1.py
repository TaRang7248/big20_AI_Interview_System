import unittest
from unittest.mock import MagicMock, patch
import sys
import os
from datetime import datetime

# Adjust path to find packages
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from packages.imh_service.session_service import SessionService
from packages.imh_dto.session import AnswerSubmissionDTO
from packages.imh_dto.projection import SessionProjectionDTO
from packages.imh_session.dto import SessionContext, SessionConfig
from packages.imh_session.policy import InterviewMode

class TestCP1SessionProjection(unittest.TestCase):
    
    def setUp(self):
        # Mock Dependencies
        self.state_repo = MagicMock()
        self.history_repo = MagicMock()
        self.job_repo = MagicMock()
        self.q_gen = MagicMock()
        self.q_bank = MagicMock()
        
        # Initialize Service
        # We need to patch RedisClient inside RedisRuntimeStore and RedisProjectionRepository init
        with patch('packages.imh_core.infra.redis.RedisClient.get_instance', return_value=MagicMock()):
            self.service = SessionService(
                state_repo=self.state_repo,
                history_repo=self.history_repo,
                job_repo=self.job_repo,
                question_generator=self.q_gen,
                qbank_service=self.q_bank
            )
            
        # Mock Projection Repo specifically for testing
        self.service.projection_repo = MagicMock()

    def test_read_through_cache_miss(self):
        """
        Scenario: Cache Miss -> Load from PG -> Save to Redis -> Return DTO.
        """
        session_id = "sess_001"
        
        # 1. Mock Redis Miss
        self.service.projection_repo.get.return_value = None
        
        # 2. Mock PG Hit
        mock_context = MagicMock()
        mock_context.session_id = session_id
        mock_context.status = "IN_PROGRESS"
        mock_context.config.mode = InterviewMode.ACTUAL
        mock_context.completed_questions_count = 5
        mock_context.config.total_question_limit = 10
        mock_context.current_question.id = "q1"
        mock_context.current_question.type.value = "TEXT" # Enum value access simulation
        
        self.service._load_session_context = MagicMock(return_value=mock_context)
        
        # 3. Execute
        result = self.service.get_session_projection(session_id)
        
        # 4. Verify
        # - PG Loaded
        self.service._load_session_context.assert_called_with(session_id)
        # - Saved to Redis
        self.service.projection_repo.save.assert_called_once()
        saved_dto = self.service.projection_repo.save.call_args[0][0]
        self.assertEqual(saved_dto.session_id, session_id)
        # - Result is correct
        self.assertIsInstance(result, SessionProjectionDTO)
        self.assertEqual(result.session_id, session_id)

    def test_cache_hit_bypasses_pg(self):
        """
        Scenario: Cache Hit -> Return DTO directly (PG not called).
        """
        session_id = "sess_002"
        
        # 1. Mock Cache Hit
        cached_dto = SessionProjectionDTO(
            session_id=session_id,
            status="COMPLETED",
            progress={'answered': 10, 'total': 10},
            mode="ACTUAL",
            updated_at=datetime.utcnow()
        )
        self.service.projection_repo.get.return_value = cached_dto
        
        self.service._load_session_context = MagicMock()
        
        # 2. Execute
        result = self.service.get_session_projection(session_id)
        
        # 3. Verify
        self.assertEqual(result, cached_dto)
        self.service._load_session_context.assert_not_called() # Crucial: Authority Load Bypassed

    def test_invalidation_on_write(self):
        """
        Scenario: Submit Answer (Write) -> Invalidate Projection.
        """
        session_id = "sess_write_001"
        
        # Mock Context Loading for Write
        mock_context = MagicMock()
        mock_context.job_id = "job_1"
        mock_context.config.total_question_limit = 10
        mock_context.completed_questions_count = 0
        mock_context.current_question.id = "q1"
        mock_context.current_question.content = "Content"
        mock_context.current_question.type = "TEXT" # SessionMapper handles str(type) or type.value
        mock_context.status.value = "IN_PROGRESS" # For status map

        self.service._load_session_context = MagicMock(return_value=mock_context)
        
        mock_job = MagicMock()
        mock_job.create_session_config.return_value = MagicMock()
        self.service.job_repo.find_by_id.return_value = mock_job
        
        # Mock Engine
        with patch('packages.imh_service.session_service.InterviewSessionEngine') as MockEngine:
            engine_instance = MockEngine.return_value
            engine_instance.context = mock_context
            
            # Execute Write
            self.service.submit_answer(session_id, AnswerSubmissionDTO(content="A", type="TEXT"))
            
            # Verify Invalidation
            self.service.projection_repo.delete.assert_called_with(session_id)

    def test_redis_down_graceful_degradation(self):
        """
        Scenario: Redis Error on Get -> Log Warn -> Return from PG.
        """
        session_id = "sess_down"
        
        # Reset init to use real Repo logic class (but patched client inside)
        # We need to verify RedisProjectionRepository internal exception handling
        # So we won't mock projection_repo, but patch the RedisClient inside it?
        # Actually, here we test Service's handling of Repo returning None/Error.
        
        # Case A: Repo returns None (because it caught error internally)
        self.service.projection_repo.get.return_value = None
        
        # Mock PG
        mock_context = MagicMock()
        mock_context.session_id = session_id
        self.service._load_session_context = MagicMock(return_value=mock_context)
        
        # Execute
        result = self.service.get_session_projection(session_id)
        
        # Verify Fallback
        self.assertIsNotNone(result)
        self.service._load_session_context.assert_called()

        # Case B: Repo raises Exception (unexpected) -> Service should probably catch?
        # Current impl doesn't wrap get_session_projection in try-except for the PG part?
        # Wait, get_session_projection:
        # proj = repo.get() -> If raise, it propagates?
        # RedisProjectionRepository swallows errors and returns None.
        # So we rely on Repo contract.

if __name__ == '__main__':
    unittest.main()
