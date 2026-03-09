import sys
import os
import unittest
from unittest.mock import MagicMock
from datetime import datetime

# Adjust path to import packages
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from packages.imh_service.session_service import SessionService
from packages.imh_service.admin_query import AdminQueryService
from packages.imh_service.concurrency import ConcurrencyManager
from packages.imh_dto.session import AnswerSubmissionDTO
from packages.imh_session.dto import SessionContext
from packages.imh_session.state import SessionStatus


class TestTask022(unittest.TestCase):

    def setUp(self):
        self.mock_state_repo = MagicMock()
        self.mock_history_repo = MagicMock()
        self.service = SessionService(self.mock_state_repo, self.mock_history_repo)
        self.query_service = AdminQueryService(self.mock_state_repo)

    def test_service_submit_answer_fail_fast_lock(self):
        # Setup
        session_id = "test_session_1"
        mock_context = MagicMock(spec=SessionContext)
        mock_context.session_id = session_id
        mock_context.status = SessionStatus.IN_PROGRESS
        
        self.mock_state_repo.get_state.return_value = mock_context
        
        # Test Lock Acquisition
        cm = self.service.concurrency_manager
        
        # Manually acquire lock to simulate another process
        with cm.acquire_lock(session_id):
            # Try to submit answer while locked -> Should Fail Fast
            with self.assertRaises(BlockingIOError):
                self.service.submit_answer(session_id, AnswerSubmissionDTO(content="path/to/file", type="AUDIO"))

    def test_service_create_session(self):
        # Setup
        job_policy = {
            "mode": "PRACTICE", 
            "total_question_limit": 5,
            "min_question_count": 3
        } # Must match SessionConfig fields
        user_id = "user123"

        
        # Mock Session Engine creation
        # We need to ensure SessionService uses InterviewSessionEngine correctly.
        # Since InterviewSessionEngine instantiates and calls internal methods, we test that service calls start_session.
        
        # We can't easily mock the internal `engine = InterviewSessionEngine(...)` inside `create_session` without patching.
        with unittest.mock.patch('packages.imh_service.session_service.InterviewSessionEngine') as MockEngineClass:
            mock_engine_instance = MockEngineClass.return_value
            mock_engine_instance.context = SessionContext(session_id="new_session", job_id="job1", status=SessionStatus.IN_PROGRESS)
            
            # Execute
            dto = self.service.create_session(job_policy, user_id)
            
            # Verify
            MockEngineClass.assert_called_once()
            mock_engine_instance.start_session.assert_called_once()
            self.assertEqual(dto.session_id, "new_session")


    def test_admin_query_bypasses_lock(self):
        # Setup
        session_id = "test_session_2"
        mock_context = MagicMock(spec=SessionContext)
        mock_context.session_id = session_id
        mock_context.status = SessionStatus.IN_PROGRESS
        
        self.mock_state_repo.get_state.return_value = mock_context
        
        # Manually lock
        cm = self.service.concurrency_manager
        with cm.acquire_lock(session_id):
            # Query Service should succeed even if locked
            dto = self.query_service.get_session_detail(session_id)
            self.assertIsNotNone(dto)
            self.assertEqual(dto.session_id, session_id)

    def test_dto_separation(self):
        # Ensure DTOs are used in return types, not Domain objects
        session_id = "test_session_3"
        mock_context = MagicMock(spec=SessionContext)
        mock_context.session_id = session_id
        mock_context.status = SessionStatus.IN_PROGRESS
        
        self.mock_state_repo.get_state.return_value = mock_context
        
        dto = self.query_service.get_session_detail(session_id)
        
        # Check type name to ensure it's a DTO
        self.assertEqual(type(dto).__name__, "SessionResponseDTO")
        # Ensure primitive types in DTO
        self.assertIsInstance(dto.session_id, str)

if __name__ == '__main__':
    unittest.main()
