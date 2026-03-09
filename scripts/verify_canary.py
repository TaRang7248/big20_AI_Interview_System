import sys
import os
import time
import logging
import hashlib
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

# Custom log handler
class VerifyLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []
    
    def emit(self, record):
        self.records.append(record)

def setup_logging():
    logger = logging.getLogger("imh.session_service")
    logger.setLevel(logging.INFO)
    handler = VerifyLogHandler()
    logger.addHandler(handler)
    return handler

# Env setup
from dotenv import load_dotenv
load_dotenv()

if not os.getenv("POSTGRES_CONNECTION_STRING"):
    print("SKIPPING: POSTGRES_CONNECTION_STRING not found in env.")
    sys.exit(0)

# Import dependencies
try:
    from IMH.api.dependencies import get_session_service, get_job_posting_repository, get_config
    from packages.imh_job.models import Job, JobPolicy
    from packages.imh_job.enums import JobStatus
    from packages.imh_session.policy import InterviewMode
    from packages.imh_job.postgresql_repository import PostgreSQLJobRepository
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def find_canary_users():
    # Find user_id that hashes to 0 (Canary) and 50 (Non-Canary)
    canary_user = None
    normal_user = None
    
    i = 0
    while not (canary_user and normal_user):
        uid = f"user_{i}"
        hash_val = int(hashlib.md5(uid.encode('utf-8')).hexdigest(), 16) % 100
        if hash_val == 0 and not canary_user:
            canary_user = uid
        if hash_val == 50 and not normal_user:
            normal_user = uid
        i += 1
    return canary_user, normal_user

def run_verification():
    print("=== Checkpoint 4.2: Canary Rollout Verification ===")
    
    handler = setup_logging()
    
    config = get_config()
    print(f"Configured Rollout Percentage: {config.CANARY_ROLLOUT_PERCENTAGE}%")
    if config.CANARY_ROLLOUT_PERCENTAGE != 1:
        print("WARNING: Config is not 1%. Verification assumes 1%.")

    canary_user, normal_user = find_canary_users()
    print(f"Canary User (Hash 0%): {canary_user}")
    print(f"Normal User (Hash 50%): {normal_user}")

    # 1. Setup Test Job (needed for session creation)
    # We reuse logic from shadow read verify
    pg_conn_str = config.POSTGRES_CONNECTION_STRING
    job_repo_pg = PostgreSQLJobRepository(conn_config={'dsn': pg_conn_str})
    job_repo_mem = get_job_posting_repository()
    
    policy = JobPolicy(
        mode=InterviewMode.ACTUAL,
        total_question_limit=10,
        min_question_count=10,
        question_timeout_sec=120,
        silence_timeout_sec=15,
        description="Canary Test Job",
        requirements=["Canary"],
        preferences=["Testing"]
    )
    test_job = Job(
        job_id="job_canary",
        title="Canary Test",
        status=JobStatus.PUBLISHED,
        created_at=datetime.now(),
        policy=policy
    )
    
    # Save to both (Dual Write Simulation for Job)
    if hasattr(job_repo_mem, "save"):
        job_repo_mem.save(test_job)
    elif hasattr(job_repo_mem, "_jobs"):
        job_repo_mem._jobs["job_canary"] = test_job
        
    try:
        job_repo_pg.save(test_job)
    except Exception as e:
        print(f"Warning: Job save to PG failed (might exist): {e}")

    service = get_session_service()
    canary_mgr = service.canary_manager

    # Helper to find session with specific canary status
    def create_session_with_canary_status(target_is_canary: bool):
        attempts = 0
        while attempts < 1000:
            # randomized user_id
            uid = f"user_test_{attempts}"
            dto = service.create_session_from_job("job_canary", uid)
            sid = dto.session_id
            
            is_canary = canary_mgr.check_canary_access(sid)
            if is_canary == target_is_canary:
                return dto
            attempts += 1
        return None

    # 2. Verify Canary Session
    print("\n--- Test 1: Canary Session (Should Read from Postgres) ---")
    dto_c = create_session_with_canary_status(target_is_canary=True)
    if not dto_c:
        print("FAIL: Could not generate a Canary Session ID after 1000 attempts.")
        sys.exit(1)
        
    print(f"Created Canary Session: {dto_c.session_id}")
    
    # Read Session
    handler.records = []
    service.get_session(dto_c.session_id)
    time.sleep(0.5)
    
    # Check logs
    messages = [r.getMessage() for r in handler.records]
    is_canary_log = any("is in canary group" in m for m in messages)
    
    if is_canary_log:
        print("[Pass] Canary Session routed to Postgres Primary.")
    else:
        print(f"[FAIL] Canary Session NOT routed to Postgres. Logs: {messages}")

    # 3. Verify Normal Session
    print("\n--- Test 2: Normal Session (Should Read from Memory) ---")
    dto_n = create_session_with_canary_status(target_is_canary=False)
    print(f"Created Normal Session: {dto_n.session_id}")
    
    handler.records = []
    service.get_session(dto_n.session_id)
    time.sleep(0.5)
    
    messages = [r.getMessage() for r in handler.records]
    is_canary_log = any("is in canary group" in m for m in messages)
    
    if not is_canary_log:
        print("[Pass] Normal Session routed to Memory Primary (Default).")
    else:
        print(f"[FAIL] Normal Session incorrectly routed to Postgres. Logs: {messages}")

    print("\n=== Verification Complete ===")

if __name__ == "__main__":
    run_verification()
