import sys
import os
import unittest
import logging
from typing import Optional, Any

# Ensure project root is in path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_root)

from packages.imh_session.state import SessionStatus, SessionEvent, TerminationReason
from packages.imh_session.dto import SessionConfig, SessionContext
from packages.imh_session.policy import InterviewMode, get_policy
from packages.imh_session.repository import SessionStateRepository, SessionHistoryRepository
from packages.imh_session.engine import InterviewSessionEngine

# Configure logging to capture output during tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("imh.session")

# Mock Implementations
class MockStateRepository(SessionStateRepository):
    def __init__(self):
        self.store = {}

    def save_state(self, session_id: str, context: SessionContext) -> None:
        self.store[session_id] = context

    def get_state(self, session_id: str) -> Optional[SessionContext]:
        return self.store.get(session_id)

    def update_status(self, session_id: str, status: SessionStatus) -> None:
        if session_id in self.store:
            self.store[session_id].status = status

class MockHistoryRepository(SessionHistoryRepository):
    def __init__(self):
        self.results = {}
        self.statuses = {}

    def save_interview_result(self, session_id: str, result_data: Any) -> None:
        self.results[session_id] = result_data

    def update_interview_status(self, session_id: str, status: SessionStatus) -> None:
        self.statuses[session_id] = status

class TestInterviewModePolicies(unittest.TestCase):
    def setUp(self):
        self.state_repo = MockStateRepository()
        self.history_repo = MockHistoryRepository()

    def test_actual_mode_strict_policy(self):
        """
        Verify Actual Mode Policies:
        1. Resume forbidden.
        2. Min questions mandatory for early exit.
        """
        session_id = "actual_session_001"
        config = SessionConfig(
            total_question_limit=10,
            min_question_count=5, # Min 5
            mode=InterviewMode.ACTUAL
        )
        engine = InterviewSessionEngine(session_id, config, self.state_repo, self.history_repo)
        engine.start_session()
        
        # 1. Interruption & Resume Check
        engine.interrupt_session(TerminationReason.INTERRUPTED_BY_USER)
        self.assertEqual(engine.context.status, SessionStatus.INTERRUPTED)
        
        # Helper to capture logs would be ideal, but for now we check state
        engine.resume_session()
        # Should fail -> Stay INTERRUPTED
        self.assertEqual(engine.context.status, SessionStatus.INTERRUPTED)
        
        # 2. Min Question Policy Check
        # Reset session for next check (Mocking fresh start logic by creating new engine/context)
        session_id = "actual_session_early_exit"
        engine = InterviewSessionEngine(session_id, config, self.state_repo, self.history_repo)
        engine.start_session()
        
        # Answer 3 questions (Less than min 5)
        for _ in range(3):
            engine.process_answer(duration_sec=10)
            
        # Set Early Exit Signal
        engine.context.early_exit_signaled = True
        
        # Process 4th question
        engine.process_answer(duration_sec=10)
        # Should still be IN_PROGRESS because 4 < 5
        self.assertEqual(engine.context.status, SessionStatus.IN_PROGRESS)
        self.assertEqual(engine.context.completed_questions_count, 4)
        
        # Process 5th question (Meet min count)
        engine.process_answer(duration_sec=10)
        # Now should terminate because min count met + signal exists
        self.assertEqual(engine.context.completed_questions_count, 5)
        self.assertEqual(engine.context.status, SessionStatus.COMPLETED)

    def test_practice_mode_flexible_policy(self):
        """
        Verify Practice Mode Policies:
        1. Resume allowed.
        2. Early exit allowed anytime (Min question check skipped).
        """
        session_id = "practice_session_001"
        config = SessionConfig(
            total_question_limit=10,
            min_question_count=5,
            mode=InterviewMode.PRACTICE
        )
        engine = InterviewSessionEngine(session_id, config, self.state_repo, self.history_repo)
        engine.start_session()
        
        # 1. Interruption & Resume Check
        engine.interrupt_session(TerminationReason.INTERRUPTED_BY_USER)
        self.assertEqual(engine.context.status, SessionStatus.INTERRUPTED)
        
        engine.resume_session()
        # Should succeed -> Go back to IN_PROGRESS
        self.assertEqual(engine.context.status, SessionStatus.IN_PROGRESS)
        
        # 2. Early Exit Policy Check
        # Reset/New session
        session_id = "practice_session_early_exit"
        engine = InterviewSessionEngine(session_id, config, self.state_repo, self.history_repo)
        engine.start_session()
        
        # Answer 1 question (Less than min 5)
        engine.process_answer(duration_sec=10)
        
        # Set Early Exit Signal
        engine.context.early_exit_signaled = True
        
        # Process 2nd question
        engine.process_answer(duration_sec=10)
        # Should terminate immediately because Practice mode allows early exit anytime
        # (requires_min_questions_for_early_exit returns False)
        self.assertEqual(engine.context.status, SessionStatus.COMPLETED)

if __name__ == "__main__":
    unittest.main()
