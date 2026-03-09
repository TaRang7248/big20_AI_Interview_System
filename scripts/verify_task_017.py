import sys
import os
import unittest
from typing import Optional, Any

# Ensure project root is in path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_root)

from packages.imh_session.state import SessionStatus, SessionEvent
from packages.imh_session.dto import SessionConfig, SessionContext
from packages.imh_session.repository import SessionStateRepository, SessionHistoryRepository
from packages.imh_session.engine import InterviewSessionEngine

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

class TestInterviewSessionEngine(unittest.TestCase):
    def setUp(self):
        self.session_id = "test_session_123"
        self.config = SessionConfig(
            total_question_limit=12,
            min_question_count=10,
            question_timeout_sec=60,
            silence_timeout_sec=10,
            early_exit_enabled=True
        )
        self.state_repo = MockStateRepository()
        self.history_repo = MockHistoryRepository()
        self.engine = InterviewSessionEngine(
            self.session_id, self.config, self.state_repo, self.history_repo
        )

    def test_initial_state(self):
        """Verify initial state is APPLIED."""
        self.assertEqual(self.engine.context.status, SessionStatus.APPLIED)

    def test_start_session(self):
        """Verify transition to IN_PROGRESS."""
        self.engine.start_session()
        self.assertEqual(self.engine.context.status, SessionStatus.IN_PROGRESS)
        self.assertEqual(self.state_repo.get_state(self.session_id).status, SessionStatus.IN_PROGRESS)
        self.assertEqual(self.history_repo.statuses[self.session_id], SessionStatus.IN_PROGRESS)

    def test_min_question_policy(self):
        """Verify session does not terminate early before min questions."""
        self.engine.start_session()
        # Simulate 5 questions answered
        for _ in range(5):
            self.engine.process_answer(duration_sec=30)
        
        self.assertEqual(self.engine.context.completed_questions_count, 5)
        self.assertEqual(self.engine.context.status, SessionStatus.IN_PROGRESS)
        
        # Simulate early exit signal but still below min count
        self.engine.context.early_exit_signaled = True
        self.engine.process_answer(duration_sec=30)
        
        self.assertEqual(self.engine.context.completed_questions_count, 6)
        self.assertEqual(self.engine.context.status, SessionStatus.IN_PROGRESS)

    def test_early_exit_after_min_questions(self):
        """Verify early exit works AFTER min questions met."""
        self.engine.start_session()
        # Answer 9 questions
        for _ in range(9):
            self.engine.process_answer(duration_sec=30)
            
        # 10th question - meet min count
        self.engine.process_answer(duration_sec=30)
        self.assertEqual(self.engine.context.completed_questions_count, 10)
        self.assertEqual(self.engine.context.status, SessionStatus.IN_PROGRESS) # Signal not set
        
        # 11th question - Early Exit Signal Set
        self.engine.context.early_exit_signaled = True
        self.engine.process_answer(duration_sec=30)
        
        self.assertEqual(self.engine.context.status, SessionStatus.COMPLETED)
        self.assertEqual(self.history_repo.statuses[self.session_id], SessionStatus.COMPLETED)

    def test_max_questions_termination(self):
        """Verify termination at max questions."""
        self.engine.start_session()
        # Answer total questions (12)
        for _ in range(12):
            self.engine.process_answer(duration_sec=30)
            
        self.assertEqual(self.engine.context.completed_questions_count, 12)
        self.assertEqual(self.engine.context.status, SessionStatus.COMPLETED)

    def test_silence_timeout_handling(self):
        """Verify silence timeout triggers step completion."""
        self.engine.start_session()
        
        # Trigger silence timeout (No Answer)
        self.engine.handle_silence_timeout(is_no_answer=True)
        self.assertEqual(self.engine.context.completed_questions_count, 1)
        
        # Trigger silence timeout (Post-Answer)
        self.engine.handle_silence_timeout(is_no_answer=False)
        self.assertEqual(self.engine.context.completed_questions_count, 2)
        
        self.assertEqual(self.engine.context.status, SessionStatus.IN_PROGRESS)

    def test_interruption(self):
        """Verify interruption handling."""
        self.engine.start_session()
        self.engine.interrupt_session("USER_ABORT")
        self.assertEqual(self.engine.context.status, SessionStatus.INTERRUPTED)
        self.assertEqual(self.history_repo.statuses[self.session_id], SessionStatus.INTERRUPTED)

if __name__ == "__main__":
    unittest.main()
