import sys
import os
import time
import logging
import asyncio
from typing import Dict, Any

# Add project root to path
sys.path.append(os.getcwd())

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("verify_state_transition")

# Env setup
from dotenv import load_dotenv
load_dotenv()

if not os.getenv("POSTGRES_CONNECTION_STRING"):
    print("SKIPPING: POSTGRES_CONNECTION_STRING not found in env.")
    sys.exit(0)

# Import dependencies
try:
    from app.api.dependencies import get_session_service, get_session_state_repository, get_job_posting_repository
    from packages.imh_session.infrastructure.dual_repo import DualSessionStateRepository
    from packages.imh_job.models import Job, JobPolicy
    from packages.imh_job.enums import JobStatus
    from packages.imh_job.postgresql_repository import PostgreSQLJobRepository
    from packages.imh_session.policy import InterviewMode
    from packages.imh_session.state import SessionStatus
    from datetime import datetime
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def run_verification():
    print("=== Checkpoint 4.3: State Transition Integrity Verification ===")
    
    service = get_session_service()
    repo = get_session_state_repository()
    secondary = repo.secondary
    
    # Setup Job (Reuse LoopJob or create new)
    job_repo = get_job_posting_repository()
    if not hasattr(job_repo, "find_by_id") or not job_repo.find_by_id("trans_job_1"):
        policy = JobPolicy(
            mode=InterviewMode.ACTUAL,
            total_question_limit=10,
            min_question_count=10,
            question_timeout_sec=60,
            silence_timeout_sec=10,
            description="Transition Test",
            requirements=["State"],
            preferences=["Debug"]
        )
        test_job = Job(
            job_id="trans_job_1",
            title="Transition Test Job",
            status=JobStatus.PUBLISHED,
            created_at=datetime.now(),
            policy=policy
        )
        if hasattr(job_repo, "save"): job_repo.save(test_job)
        elif hasattr(job_repo, "_jobs"): job_repo._jobs["trans_job_1"] = test_job
        
        try:
             pg_repo = PostgreSQLJobRepository(conn_config={'dsn': os.getenv("POSTGRES_CONNECTION_STRING")})
             pg_repo.save(test_job)
        except Exception as e:
             print(f"Warning: Failed to save job to Postgres: {e}")

    uid = "trans_user_1"
    
    try:
        # Step 1: Create -> IN_PROGRESS (Service Auto-Start)
        print("[Step 1] Creating Session...")
        dto = service.create_session_from_job("trans_job_1", uid)
        sid = dto.session_id
        
        ctx_s = secondary.get_state(sid)
        if ctx_s.status != SessionStatus.IN_PROGRESS:
            print(f"FAIL: Expected IN_PROGRESS, got {ctx_s.status}")
            sys.exit(1)
            
        if ctx_s.current_step != 1: 
             print(f"FAIL: Expected current_step 1, got {ctx_s.current_step}")
             sys.exit(1)
             
        if len(ctx_s.question_history) != 1:
             print(f"FAIL: Expected history len 1, got {len(ctx_s.question_history)}")
             sys.exit(1)
             
        print("PASS: Step 1 OK (IN_PROGRESS, Step 1)")

        # Step 2: Answer -> Step 2
        print("[Step 2] Answering Question...")
        from packages.imh_dto.session import AnswerSubmissionDTO
        service.submit_answer(sid, AnswerSubmissionDTO(
                question_id=ctx_s.current_question.id if ctx_s.current_question else "unknown",
                content="Test Answer",
                type="TEXT",
                duration_seconds=5.0
        ))
        
        ctx_s = secondary.get_state(sid)
        
        # Logic: complete_current_step increments completed (0->1) and current (1->2)
        if ctx_s.completed_questions_count != 1:
            print(f"FAIL: Expected completed 1, got {ctx_s.completed_questions_count}")
            sys.exit(1)
            
        if ctx_s.current_step != 2:
            print(f"FAIL: Expected current_step 2, got {ctx_s.current_step}")
            sys.exit(1)
            
        if len(ctx_s.question_history) != 2:
             print(f"FAIL: Expected history len 2, got {len(ctx_s.question_history)}")
             sys.exit(1)
             
        if len(ctx_s.answers_history) != 0: 
             print(f"FAIL: Expected answers history len 0, got {len(ctx_s.answers_history)}")
             sys.exit(1) 

        print("PASS: Step 2 OK (Answered, Step 2)")
        
        print("RESULT: GO")

    except Exception as e:
        print(f"FAIL: Exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_verification()
