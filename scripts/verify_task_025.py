import sys
import os
import unittest
import logging
import uuid
from typing import Dict, Any

# Adjust path for package imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from packages.imh_session.engine import InterviewSessionEngine
from packages.imh_session.dto import SessionConfig, SessionContext, SessionQuestionType
from packages.imh_session.repository import SessionStateRepository, SessionHistoryRepository
from packages.imh_qbank.service import QuestionBankService
from packages.imh_qbank.repository import JsonFileQuestionRepository
from packages.imh_providers.mock_question import MockQuestionGenerator
from packages.imh_job.models import InterviewMode

# Mock Repositories
class MockStateRepo(SessionStateRepository):
    def __init__(self):
        self.store = {}
    def get_state(self, session_id: str):
        return self.store.get(session_id)
    def save_state(self, session_id: str, context: SessionContext):
        self.store[session_id] = context
    def update_status(self, session_id: str, status: str):
        if session_id in self.store:
            self.store[session_id].status = status
    def find_by_job_id(self, job_id: str):
        return [ctx for ctx in self.store.values() if ctx.job_id == job_id]

class MockHistoryRepo(SessionHistoryRepository):
    def save_interview_result(self, session_id: str, result: Dict[str, Any]):
        pass
    def update_interview_status(self, session_id: str, status: str):
        pass

class TestTask025(unittest.TestCase):
    def setUp(self):
        self.state_repo = MockStateRepo()
        self.history_repo = MockHistoryRepo()
        
        # Temp QBank File
        self.qbank_file = f"temp_qbank_{uuid.uuid4()}.json"
        self.qbank_repo = JsonFileQuestionRepository(self.qbank_file)
        self.qbank_repo._save_all([]) # Clear
        self.qbank_service = QuestionBankService(self.qbank_repo)
        
        # Add a dummy static question
        self.qbank_service.add_static_question("Static Q1", ["BEHAVIORAL"])

        self.config = SessionConfig(
            total_question_limit=5,
            min_question_count=10, # Policy default
            question_timeout_sec=60,
            silence_timeout_sec=10,
            mode=InterviewMode.ACTUAL,
            job_id="job_123"
        )
        self.session_id = str(uuid.uuid4())

    def tearDown(self):
        if os.path.exists(self.qbank_file):
            os.remove(self.qbank_file)

    def test_01_normal_generation_success(self):
        """Scenario: RAG Generation Success -> Source is GENERATED"""
        generator = MockQuestionGenerator(should_fail=False)
        engine = InterviewSessionEngine(
            self.session_id, self.config, self.state_repo, self.history_repo,
            generator, self.qbank_service
        )
        
        engine.start_session()
        
        ctx = engine.context
        self.assertIsNotNone(ctx.current_question)
        self.assertEqual(ctx.current_question.source_type, SessionQuestionType.GENERATED)
        self.assertEqual(ctx.current_question.source_metadata['origin_type'], "GENERATED")
        print(f"[PASS] Normal Generation: {ctx.current_question.content}")

    def test_02_explicit_fallback(self):
        """Scenario: RAG Failure -> Fallback to STATIC"""
        generator = MockQuestionGenerator(should_fail=True) # Forces failure
        engine = InterviewSessionEngine(
            self.session_id, self.config, self.state_repo, self.history_repo,
            generator, self.qbank_service
        )
        
        engine.start_session()
        
        ctx = engine.context
        self.assertIsNotNone(ctx.current_question)
        self.assertEqual(ctx.current_question.source_type, SessionQuestionType.STATIC)
        self.assertIn("Static Q1", ctx.current_question.content)
        print(f"[PASS] Explicit Fallback: {ctx.current_question.content}")

    def test_03_critical_failure_safety(self):
        """Scenario: RAG Fail + QBank Empty -> Emergency Fallback"""
        # Empty QBank
        self.qbank_repo._save_all([])
        
        generator = MockQuestionGenerator(should_fail=True)
        engine = InterviewSessionEngine(
            self.session_id, self.config, self.state_repo, self.history_repo,
            generator, self.qbank_service
        )
        
        engine.start_session()
        
        ctx = engine.context
        self.assertIsNotNone(ctx.current_question)
        self.assertEqual(ctx.current_question.source_type, SessionQuestionType.STATIC) # Emergency is considered static
        self.assertEqual(ctx.current_question.id, "emergency-fallback")
        print(f"[PASS] Critical Safety: {ctx.current_question.content}")

    def test_04_snapshot_independence(self):
        """Scenario: Saved session data remains unchanged even if QBank/Gen changes"""
        # 1. Start session with generated question
        generator = MockQuestionGenerator(should_fail=False)
        engine = InterviewSessionEngine(
            self.session_id, self.config, self.state_repo, self.history_repo,
            generator, self.qbank_service
        )
        engine.start_session()
        original_q_content = engine.context.current_question.content
        
        # 2. Simulate generator change (not possible directly here as obj is same, but conceptually)
        # Verify stored context in repo
        stored_ctx = self.state_repo.get_state(self.session_id)
        self.assertEqual(stored_ctx.current_question.content, original_q_content)
        
        # 3. Even if we use a different engine/generator later, the 'current_question' in context is fixed value object
        # (Engine loads context)
        generator_fail = MockQuestionGenerator(should_fail=True)
        engine_reloaded = InterviewSessionEngine(
            self.session_id, self.config, self.state_repo, self.history_repo,
            generator_fail, self.qbank_service
        )
        # Context is loaded from state_repo
        self.assertEqual(engine_reloaded.context.current_question.content, original_q_content)
        print("[PASS] Snapshot Independence Verified")

if __name__ == "__main__":
    unittest.main()
