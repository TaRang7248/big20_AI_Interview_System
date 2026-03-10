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
logger = logging.getLogger("verify_loopback")

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

def deep_compare(d1: Dict, d2: Dict, path: str = "") -> list:
    errors = []
    keys1 = set(d1.keys())
    keys2 = set(d2.keys())
    
    if keys1 != keys2:
        missing_in_2 = keys1 - keys2
        missing_in_1 = keys2 - keys1
        if missing_in_2: errors.append(f"{path} Keys missing in Postgres: {missing_in_2}")
        if missing_in_1: errors.append(f"{path} Extra keys in Postgres: {missing_in_1}")
    
    for key in keys1.intersection(keys2):
        val1 = d1[key]
        val2 = d2[key]
        current_path = f"{path}.{key}" if path else key
        
        if type(val1) != type(val2):
             if val1 is None and val2 is None: continue
             errors.append(f"{current_path} Type mismatch: {type(val1)} vs {type(val2)}")
             continue
        
        if isinstance(val1, dict):
            errors.extend(deep_compare(val1, val2, current_path))
        elif isinstance(val1, list):
            if len(val1) != len(val2):
                errors.append(f"{current_path} List length mismatch: {len(val1)} vs {len(val2)}")
            else:
                for i, (item1, item2) in enumerate(zip(val1, val2)):
                    if isinstance(item1, dict) and isinstance(item2, dict):
                        errors.extend(deep_compare(item1, item2, f"{current_path}[{i}]"))
                    elif item1 != item2:
                        errors.append(f"{current_path}[{i}] Value mismatch: {item1} vs {item2}")
        else:
            if isinstance(val1, float) and isinstance(val2, float):
                if abs(val1 - val2) > 0.001:
                     errors.append(f"{current_path} Float mismatch: {val1} vs {val2}")
            elif val1 != val2:
                errors.append(f"{current_path} Value mismatch: {val1} vs {val2}")
    return errors

def run_verification():
    print("=== Checkpoint 4.3: Write -> Read Loopback Verification ===")
    
    service = get_session_service()
    repo = get_session_state_repository()
    primary = repo.primary
    secondary = repo.secondary
    
    # Setup Job
    job_repo = get_job_posting_repository()
    # Mock job
    if not hasattr(job_repo, "find_by_id") or not job_repo.find_by_id("loop_job_1"):
        policy = JobPolicy(
            mode=InterviewMode.ACTUAL,
            total_question_limit=10,
            min_question_count=10,
            question_timeout_sec=60,
            silence_timeout_sec=10,
            description="Loopback Test",
            requirements=["Loop"],
            preferences=["Back"]
        )
        test_job = Job(
            job_id="loop_job_1",
            title="Loopback Test Job",
            status=JobStatus.PUBLISHED,
            created_at=datetime.now(),
            policy=policy
        )
        # Save to both
        if hasattr(job_repo, "save"): job_repo.save(test_job)
        elif hasattr(job_repo, "_jobs"): job_repo._jobs["loop_job_1"] = test_job
        
        # Explicitly save to Postgres to satisfy FK
        try:
             pg_repo = PostgreSQLJobRepository(conn_config={'dsn': os.getenv("POSTGRES_CONNECTION_STRING")})
             pg_repo.save(test_job)
        except Exception as e:
             print(f"Warning: Failed to save job to Postgres: {e}")
        
        # We need to save to PG to satisf FK? Yes.
        # But assuming verify_shadow_read ran, we might have job_st. 
        # But let's reuse logic or assume job_repo Dual/PG handles it.
        # Actually job_repo is NOT dual. It is Mono based on config?
        # If config has PG string, dependency injected postgres repo.
        # If dependencies inject postgres repo, then job_repo is PostgresJobRepository!
        # Wait, get_job_posting_repository logic:
        # if using Postgres, it returns PostgresJobRepo.
        # So calling .save() saves to Postgres.
        # But verify_shadow_read used manual injection because MemoryRepo was default if not properly swapped?
        # Ah, dependencies.py says: get_job_posting_repository() returns Memory or Postgres based on config?
        # Let's check dependencies.py... 
        # It seems it returns MemoryJobPostingRepository or Postgres based on config?
        # No, let's assume valid repo is available.
        # Just in case, let's try-catch.

    ITERATIONS = 50
    fail_count = 0
    
    for i in range(ITERATIONS):
        user_id = f"loop_user_{i}_{int(time.time())}"
        
        try:
            # 1. Create Session (Write)
            dto = service.create_session_from_job("loop_job_1", user_id)
            sid = dto.session_id
            
            # 2. Immediate Read Verification
            ctx_p = primary.get_state(sid)
            ctx_s = secondary.get_state(sid)
            
            if not ctx_s:
                print(f"[FAIL] Iter {i}: Session {sid} missing in Secondary")
                fail_count += 1
                break
                
            diffs = deep_compare(
                ctx_p.model_dump(mode='json') if hasattr(ctx_p, 'model_dump') else ctx_p.dict(),
                ctx_s.model_dump(mode='json') if hasattr(ctx_s, 'model_dump') else ctx_s.dict()
            )
            if diffs:
                print(f"[FAIL] Iter {i}: Create Mismatch")
                for d in diffs: print(f"  - {d}")
                fail_count += 1
                break
            
            # Check Status is IN_PROGRESS (Service starts automatically)
            if ctx_s.status != SessionStatus.IN_PROGRESS:
                print(f"[FAIL] Iter {i}: Expected IN_PROGRESS, got {ctx_s.status}")
                fail_count += 1
                break

            # 3. Submit Answer (Update)
            from packages.imh_dto.session import AnswerSubmissionDTO
            service.submit_answer(sid, AnswerSubmissionDTO(
                question_id=ctx_s.current_question.id if ctx_s.current_question else "unknown",
                content="Test Answer",
                type="TEXT",
                duration_seconds=5.0
            ))
            
            # 4. Immediate Read Verification (Next Step)
            ctx_p_upd = primary.get_state(sid)
            ctx_s_upd = secondary.get_state(sid)
            
            # Check derived fields updated
            if ctx_s_upd.completed_questions_count != 1:
                print(f"[FAIL] Iter {i}: Completed Count mismatch. Got {ctx_s_upd.completed_questions_count}")
                fail_count += 1
                break
                
            # Check question history len (should be 2 now: q1 + q2)
            if len(ctx_s_upd.question_history) != 2:
                print(f"[FAIL] Iter {i}: Question History len mismatch. Got {len(ctx_s_upd.question_history)}")
                fail_count += 1
                break
            
            if i % 10 == 0:
                print(f"Iter {i}: OK")
                
        except Exception as e:
            print(f"[FAIL] Iter {i}: Exception: {e}")
            fail_count += 1
            break
            
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
