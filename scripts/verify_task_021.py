import sys
import os
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../packages")))

from imh_job.models import Job, JobPolicy, JobStatus
from imh_session.dto import SessionConfig, SessionContext
from imh_session.engine import InterviewSessionEngine
from imh_session.state import SessionStatus, TerminationReason
from imh_session.policy import InterviewMode
from imh_session.repository import SessionStateRepository, SessionHistoryRepository

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("VERIFY_TASK_021")

# Mock Repositories
class InMemorySessionStateRepository(SessionStateRepository):
    def __init__(self):
        self.store = {}

    def get_state(self, session_id: str) -> SessionContext:
        return self.store.get(session_id)

    def save_state(self, session_id: str, context: SessionContext):
        self.store[session_id] = context
        logger.debug(f"[Repo] Saved Hot State for {session_id}: {context.status}")

    def update_status(self, session_id: str, status: SessionStatus):
        if session_id in self.store:
            self.store[session_id].status = status

    def find_by_job_id(self, job_id: str):
        return [ctx for ctx in self.store.values() if ctx.job_id == job_id]

class InMemorySessionHistoryRepository(SessionHistoryRepository):
    def __init__(self):
        self.store = {}

    def save_interview_result(self, session_id: str, result_data: dict):
        self.store[session_id] = result_data
        logger.debug(f"[Repo] Saved Cold Result for {session_id}: {result_data}")

    def update_interview_status(self, session_id: str, status: SessionStatus):
        # In real impl, this updates SQL DB
        pass

def verify_job_policy_freeze():
    logger.info(">>> TEST 1: Job Policy Freeze Contract")
    
    # 1. Create Draft Job
    policy = JobPolicy(
        mode=InterviewMode.ACTUAL,
        total_question_limit=10,
        min_question_count=10,
        description="Test Job Description for Validation",
        requirements=["Python"],
        result_exposure="AFTER_14_DAYS"
    )
    job = Job(job_id="JOB-001", title="AI Engineer", policy=policy)
    assert job.status == JobStatus.DRAFT
    
    # 2. Publish
    job.publish()
    assert job.status == JobStatus.PUBLISHED
    
    # 3. Try Update Policy (Must Fail)
    try:
        new_policy = JobPolicy(
            mode=InterviewMode.PRACTICE, # Change Mode
            total_question_limit=5,
            min_question_count=10,
            description="Modified Description",
            requirements=[],
            result_exposure="IMMEDIATE"
        )
        job.policy = new_policy
        logger.error("❌ Failed: Policy update allowed in PUBLISHED state!")
        return False
    except Exception as e:
        logger.info(f"✅ Success: Policy update blocked as expected. Error: {e}")
        
    return True

def verify_session_snapshot():
    logger.info(">>> TEST 2: Session Snapshot Double Lock Contract")
    
    # 1. Setup Job (Source of Truth)
    policy = JobPolicy(
        mode=InterviewMode.ACTUAL,
        total_question_limit=10,
        min_question_count=10,
        description="Snapshot Test Description for Validation",
        requirements=[],
        result_exposure="AFTER_14_DAYS"
    )
    job = Job(job_id="JOB-002", title="Snapshot Job", policy=policy)
    job.publish()
    
    # 2. Create Session Config (Snapshot)
    session_config = job.create_session_config()
    
    # 3. Verify Snapshot Content
    assert session_config.job_id == job.job_id
    assert session_config.total_question_limit == 10
    assert session_config.result_exposure == "AFTER_14_DAYS"
    assert session_config.mode == InterviewMode.ACTUAL
    
    logger.info("✅ Success: Session Config holds correct snapshot data.")
    return True

def verify_actual_mode_interruption():
    logger.info(">>> TEST 3: Actual Mode Interruption (Strict)")
    
    # 1. Setup Engine
    config = SessionConfig(
        total_question_limit=10,
        min_question_count=10,
        mode=InterviewMode.ACTUAL,
        job_id="JOB-ACTUAL",
        result_exposure="HIDDEN"
    )
    state_repo = InMemorySessionStateRepository()
    history_repo = InMemorySessionHistoryRepository()
    
    engine = InterviewSessionEngine(
        session_id="SESS-ACTUAL-01",
        config=config,
        state_repo=state_repo,
        history_repo=history_repo
    )
    
    # 2. Start Session
    engine.start_session()
    assert engine.context.status == SessionStatus.IN_PROGRESS
    
    # 3. Interrupt
    engine.interrupt_session(TerminationReason.INTERRUPTED_BY_USER)
    assert engine.context.status == SessionStatus.INTERRUPTED
    
    # 4. Try Resume (Must Fail)
    engine.resume_session()
    assert engine.context.status == SessionStatus.INTERRUPTED # Should stick
    
    logger.info("✅ Success: Actual Mode session interrupted and resume blocked.")
    return True

def verify_practice_mode_interruption():
    logger.info(">>> TEST 4: Practice Mode Interruption (Flexible)")
    
    # 1. Setup Engine
    config = SessionConfig(
        total_question_limit=10,
        min_question_count=10,
        mode=InterviewMode.PRACTICE,
        job_id="JOB-PRACTICE",
        result_exposure="FULL"
    )
    state_repo = InMemorySessionStateRepository()
    history_repo = InMemorySessionHistoryRepository()
    
    engine = InterviewSessionEngine(
        session_id="SESS-PRACTICE-01",
        config=config,
        state_repo=state_repo,
        history_repo=history_repo
    )
    
    # 2. Start Session
    engine.start_session()
    assert engine.context.status == SessionStatus.IN_PROGRESS
    
    # 3. Interrupt
    engine.interrupt_session(TerminationReason.INTERRUPTED_BY_USER)
    assert engine.context.status == SessionStatus.INTERRUPTED
    
    # 4. Try Resume (Must Success)
    engine.resume_session()
    assert engine.context.status == SessionStatus.IN_PROGRESS
    
    logger.info("✅ Success: Practice Mode session resumed successfully.")
    return True

def main():
    checks = [
        verify_job_policy_freeze(),
        verify_session_snapshot(),
        verify_actual_mode_interruption(),
        verify_practice_mode_interruption()
    ]
    
    if all(checks):
        logger.info("\n🎉 ALL TASK-021 INTEGRATION CHECKS PASSED!")
        sys.exit(0)
    else:
        logger.error("\n❌ SOME CHECKS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
