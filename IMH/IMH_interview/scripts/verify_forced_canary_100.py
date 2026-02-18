import sys
import os
import time
import logging
from typing import Dict, Any

# Add project root to path
sys.path.append(os.getcwd())

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("verify_forced_canary_100")

# Env setup: FORCE 100% BEFORE importing dependencies that might cache config
os.environ["CANARY_ROLLOUT_PERCENTAGE"] = "100"

from dotenv import load_dotenv
load_dotenv(override=True) 

if not os.getenv("POSTGRES_CONNECTION_STRING"):
    print("SKIPPING: POSTGRES_CONNECTION_STRING not found in env.")
    sys.exit(0)

# Import dependencies
try:
    from IMH.api.dependencies import get_session_service, get_session_state_repository, get_job_posting_repository, get_config, get_canary_manager
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
    print("=== Checkpoint 4.3: Forced Canary 100% Verification ===")
    
    # 1. Force Config Reload
    get_config.cache_clear()
    get_canary_manager.cache_clear()
    
    config = get_config()
    print(f"Configured Rollout Percentage: {config.CANARY_ROLLOUT_PERCENTAGE}%")
    
    if config.CANARY_ROLLOUT_PERCENTAGE != 100:
        print("FAIL: Failed to force 100% Rollout via Env.")
        # Attempt manual override if env fails
        print("Attempting manual CanaryManager override...")
        # We can't easily override internal dependency logic without patching
        # But let's see if env worked. env var strings are parsed by pydantic settings.
        # It should work if os.environ is set before load.
        sys.exit(1)

    service = get_session_service()
    repo = get_session_state_repository()
    primary = repo.primary # Memory
    
    # Setup Job
    job_repo = get_job_posting_repository()
    if not hasattr(job_repo, "find_by_id") or not job_repo.find_by_id("canary_100_job"):
        policy = JobPolicy(
            mode=InterviewMode.ACTUAL,
            total_question_limit=10,
            min_question_count=10,
            question_timeout_sec=60,
            silence_timeout_sec=10,
            description="Canary 100 Test",
            requirements=["Force"],
            preferences=["100"]
        )
        test_job = Job(
            job_id="canary_100_job",
            title="Canary 100 Job",
            status=JobStatus.PUBLISHED,
            created_at=datetime.now(),
            policy=policy
        )
        if hasattr(job_repo, "save"): job_repo.save(test_job)
        elif hasattr(job_repo, "_jobs"): job_repo._jobs["canary_100_job"] = test_job
        
        try:
             pg_repo = PostgreSQLJobRepository(conn_config={'dsn': os.getenv("POSTGRES_CONNECTION_STRING")})
             pg_repo.save(test_job)
        except Exception as e:
             print(f"Warning: Failed to save job to Postgres: {e}")

    ITERATIONS = 20
    fail_count = 0
    
    for i in range(ITERATIONS):
        uid = f"canary_force_user_{i}"
        
        try:
            # 1. Create Session
            dto = service.create_session_from_job("canary_100_job", uid)
            sid = dto.session_id
            
            # 2. Verify Canary Manager Decision
            if not service.canary_manager.check_canary_access(sid):
                print(f"[FAIL] Iter {i}: Canary Manager returned False for {sid}")
                fail_count += 1
                continue
                
            # 3. Read Source Verification (The "Acid Test")
            # We want to prove get_session(sid) comes from Postgres.
            # Strategy: Corrupt Memory, Leave Postgres Intact.
            # If get_session returns Intact data, it read from Postgres.
            
            # Corrupt Memory
            original_mem_ctx = primary.get_state(sid)
            primary.update_status(sid, SessionStatus.COMPLETED) # Fake corruption
            
            # Verify Corruption
            corrupted = primary.get_state(sid)
            if corrupted.status != SessionStatus.COMPLETED:
                 print(f"[FAIL] Iter {i}: Failed to corrupt memory for test.")
                 fail_count += 1
                 continue
                 
            # Call Service Get
            fetched_dto = service.get_session(sid)
            
            # Assert
            if fetched_dto.status == SessionStatus.IN_PROGRESS: # Original status
                # PASS: It ignored Memory (COMPLETED) and read Postgres (IN_PROGRESS)
                if i % 5 == 0: print(f"Iter {i}: PASS (Read from Postgres confirmed)")
            else:
                print(f"[FAIL] Iter {i}: Read from Memory! Status={fetched_dto.status}")
                fail_count += 1
                
            # Restore Memory (to be clean)
            primary.update_status(sid, SessionStatus.IN_PROGRESS)
            
        except Exception as e:
            print(f"[FAIL] Iter {i}: Exception: {e}")
            fail_count += 1
            
    print("\n--- Summary ---")
    print(f"Iterations: {ITERATIONS}")
    print(f"FAIL: {fail_count}")
    
    if fail_count == 0:
        print("RESULT: GO")
    else:
        print("RESULT: NO-GO")
        sys.exit(1)

if __name__ == "__main__":
    run_verification()
