import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Adjust path to find packages
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from packages.imh_core.errors import RedisConnectionError, LockAcquisitionError
from packages.imh_service.concurrency import ConcurrencyManager
from packages.imh_service.session_service import SessionService
from packages.imh_dto.session import AnswerSubmissionDTO, SessionResponseDTO

from packages.imh_session.policy import InterviewMode

class TestTask027CP0(unittest.TestCase):
    
    def setUp(self):
        # Mock Redis Client
        self.mock_redis = MagicMock()
        self.patcher = patch('packages.imh_core.infra.redis.RedisClient.get_instance', return_value=self.mock_redis)
        self.patcher.start()
        
    def tearDown(self):
        self.patcher.stop()

    def test_fail_fast_on_redis_down(self):
        """
        CP0 Contract: If Redis is down, Write Operations must FAIL FAST (Reject).
        """
        # Simulate Redis Down
        with patch('packages.imh_core.infra.redis.RedisClient.get_instance', side_effect=RedisConnectionError("Redis Down")):
            cm = ConcurrencyManager()
            # Expect cm.redis to be None or init fail handled?
            # Current impl catches error and sets redis=None + logs critical.
            
            with self.assertRaises(RedisConnectionError):
                with cm.acquire_lock("test_session"):
                    pass

    def test_write_order_enforcement(self):
        """
        CP0 Contract: PG Commit -> Redis Mirror Update.
        """
        # Setup Service with Mocks
        state_repo = MagicMock()
        history_repo = MagicMock()
        job_repo = MagicMock()
        
        service = SessionService(
            state_repo=state_repo,
            history_repo=history_repo,
            job_repo=job_repo,
            question_generator=MagicMock(),
            qbank_service=MagicMock()
        )
        
        # Mock Context Loading
        mock_context = MagicMock()
        mock_context.job_id = "job_123"
        mock_context.config.total_question_limit = 10
        mock_context.completed_questions_count = 1
        
        # Mock Question for Mapper
        mock_q = MagicMock()  
        mock_q.id = "q1"
        mock_q.content = "Question Content"
        mock_q.type = "TEXT"
        mock_q.time_limit = 60
        mock_context.current_question = mock_q
        
        # Mock to return context
        service._load_session_context = MagicMock(return_value=mock_context)
        
        # Mock Job
        mock_job = MagicMock()
        mock_config = MagicMock()
        mock_config.mode = InterviewMode.ACTUAL # Set valid enum
        mock_job.create_session_config.return_value = mock_config
        job_repo.find_by_id.return_value = mock_job
        mock_job = MagicMock()
        job_repo.find_by_id.return_value = mock_job
        
        # Mock Engine execution
        with patch('packages.imh_service.session_service.InterviewSessionEngine') as MockEngine:
            engine_instance = MockEngine.return_value
            # Engine context after processing
            engine_instance.context = mock_context 
            
            # Mock Mirror Store
            service.runtime_store = MagicMock()
            
            # Execute Submit Answer
            dto = AnswerSubmissionDTO(content="answer", type="TEXT")
            service.submit_answer("sess_1", dto)
            
            # Verification 1: Engine Process (PG Commit) called BEFORE Mirror
            engine_instance.process_answer.assert_called_once()
            
            # Verification 2: Mirror Save called
            service.runtime_store.save_mirror.assert_called_once()
            
            # Order Logic is implicit in code flow, but we verified both called.
            # Failure test: If Engine failed, Mirror should not be called.
            service.runtime_store.save_mirror.reset_mock()
            engine_instance.process_answer.side_effect = Exception("PG Fail")
            
            with self.assertRaises(Exception):
                service.submit_answer("sess_1", dto)
                
            service.runtime_store.save_mirror.assert_not_called()

    def test_idempotency_check(self):
        """
        CP0 Contract: Idempotency returns cached result.
        """
        cm = ConcurrencyManager()
        cm.idempotency = MagicMock()
        cm.acquire_lock = MagicMock()
        
        service = SessionService(
            state_repo=MagicMock(),
            history_repo=MagicMock(),
            job_repo=MagicMock(),
            question_generator=MagicMock(),
            qbank_service=MagicMock()
        )
        service.concurrency_manager = cm
        
        # FIX: Set constants on Mock so comparison works
        cm.idempotency.STATUS_DONE = 2
        cm.idempotency.STATUS_IN_PROGRESS = 1
        cm.idempotency.STATUS_NEW = 0
        
        # Scenario: Idempotency Hit (DONE)
        cm.idempotency.check_request.return_value = (2, '{"session_id": "s1", "status": "IN_PROGRESS", "created_at": "2023-01-01T00:00:00", "total_questions": 10, "progress_percentage": 0}')
        
        # Mock Job (Safety if Idempotency falls through)
        mock_job = MagicMock()
        mock_config = MagicMock()
        mock_config.mode = InterviewMode.ACTUAL
        mock_job.create_session_config.return_value = mock_config
        service.job_repo.find_by_id.return_value = mock_job
        
        # Execute
        result = service.submit_answer("s1", AnswerSubmissionDTO(content="a", type="T"), request_id="req_1")
        
        # Should return result without engine interaction
        self.assertEqual(result.session_id, "s1")
        cm.acquire_lock.assert_not_called()

    def test_hydration_logic(self):
        """
        CP0 Contract: Hydration reads PG -> writes Redis.
        """
        service = SessionService(
            state_repo=MagicMock(),
            history_repo=MagicMock(),
            job_repo=MagicMock(),
            question_generator=MagicMock(),
            qbank_service=MagicMock()
        )
        
        # Mock Data
        mock_context = MagicMock()
        mock_context.dict.return_value = {"step": 1}
        service._load_session_context = MagicMock(return_value=mock_context)
        service.runtime_store = MagicMock()
        
        # Run Hydration
        success = service.hydrate_session("sess_1")
        
        self.assertTrue(success)
        service.runtime_store.save_mirror.assert_called_with("sess_1", {"step": 1})

if __name__ == '__main__':
    unittest.main()
