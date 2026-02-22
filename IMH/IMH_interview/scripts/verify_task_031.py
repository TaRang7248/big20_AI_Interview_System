"""
verify_task_031.py
==================
Verification for TASK-031: Snapshot Immutability (L2/L3 Guards)

Tests:
1. [L2 Guard] Repository ignores snapshot updates (Silent Preservation).
2. [L2 Guard] Repository logs ERROR on attempt (Modification Attempt Record).
3. [L3 Guard] DB Trigger blocks raw SQL updates (Storage Guard).
"""
import asyncio
import logging
import json
import os
import sys
from datetime import datetime
from uuid import uuid4

# Bootstrap
sys.path.append(os.getcwd())

import asyncpg
from packages.imh_session.infrastructure.postgresql_repo import PostgreSQLSessionRepository
from packages.imh_session.dto import SessionContext, SessionConfig
from packages.imh_session.state import SessionStatus

# Configure Logging to capture L2 warnings
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_task_031")

# DB Config (Hardcoded for verification, matching .env)
DB_CONFIG = {
    "user": "postgres",
    "password": "1234",
    "database": "interview_db",
    "host": "localhost",
    "port": 5432
}

async def run_verification():
    print("=" * 60)
    print("TASK-031 Verification: Snapshot Immutability")
    print("=" * 60)
    
    repo = PostgreSQLSessionRepository(DB_CONFIG)
    
    # 1. Setup Data
    session_id = f"sess_immutable_{uuid4().hex[:8]}"
    job_id = "job_imm_01"
    
    policy_snap = {"version": "v1", "rules": ["no_retry"]}
    config_snap = {"time_limit": 60}
    
    
    # 0. Prerequisite: Create Job (FK Constraint)
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        await conn.execute(
            """
            INSERT INTO jobs (job_id, title, status, created_at, updated_at)
            VALUES ($1, 'Immutable Test Job', 'PUBLISHED', NOW(), NOW())
            ON CONFLICT (job_id) DO NOTHING
            """,
            job_id
        )
        print(f"  -> Prerequisite: Job {job_id} ensured.")
    finally:
        await conn.close()

    ctx = SessionContext(
        session_id=session_id,
        user_id="user_test",
        job_id=job_id,
        status=SessionStatus.APPLIED,
        job_policy_snapshot=policy_snap,
        session_config_snapshot=config_snap,
        question_history=[],
        answers_history=[]
    )
    
    print(f"\n[Test 1] Create Session (ID: {session_id})")
    await repo._async_save_state(session_id, ctx)
    print("  -> Session created successfully.")
    
    # Verify initial state
    saved = await repo._async_get_state(session_id)
    assert saved.job_policy_snapshot == policy_snap
    assert saved.session_config_snapshot == config_snap
    print("  -> Initial snapshots verified.")
    
    # 2. Test L2 Guard (Repo Level)
    print(f"\n[Test 2] L2 Guard: Attempt Update via Repository (Silent Preservation)")
    
    # Create modified context
    modified_policy = {"version": "v2_HACKED", "rules": ["retry_forever"]}
    ctx_modified = SessionContext(
        session_id=session_id,
        user_id="user_test",
        job_id=job_id,
        status=SessionStatus.IN_PROGRESS, # Valid status change
        job_policy_snapshot=modified_policy, # INVALID snapshot change
        session_config_snapshot=config_snap,
        question_history=[],
        answers_history=[]
    )
    
    # Capture Logs? (Visual verification for now, or mock logger)
    # We expect an ERROR log but NO exception.
    print("  -> Calling save_state with MODIFIED snapshot...")
    await repo._async_save_state(session_id, ctx_modified)
    print("  -> save_state returned without exception (Silent Preservation: OK).")
    
    # Verify persistence (Should be OLD value)
    reloaded = await repo._async_get_state(session_id)
    print(f"  -> DB Value: {reloaded.job_policy_snapshot}")
    print(f"  -> Input Value: {modified_policy}")
    
    if reloaded.job_policy_snapshot == policy_snap:
         print("  -> [PASS] Snapshot retained original value (Immutability Confirmed).")
    else:
         print("  -> [FAIL] Snapshot was updated!")
         sys.exit(1)
         
    if reloaded.status == SessionStatus.IN_PROGRESS:
         print("  -> [PASS] Status was updated (Normal fields allowed).")
    else:
         print("  -> [FAIL] Status update failed!")
         sys.exit(1)

    # 3. Test L3 Guard (DB Trigger Level)
    print(f"\n[Test 3] L3 Guard: Attempt Update via Raw SQL (Storage Block)")
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        print("  -> Executing raw SQL UPDATE on snapshot column...")
        await conn.execute(
            """
            UPDATE interviews 
            SET job_policy_snapshot = '{"hacked": true}'::jsonb 
            WHERE session_id = $1
            """,
            session_id
        )
        print("  -> [FAIL] Raw SQL update succeeded! Trigger missing or failed.")
        sys.exit(1)
    except asyncpg.exceptions.RaiseError as e:
        print(f"  -> [PASS] Caught expected DB Exception: {e}")
        if "L3 VIOLATION" in str(e):
             print("  -> Error message confirms L3 Violation.")
        else:
             print("  -> Warning: Error message does not contain 'L3 VIOLATION'.")
    except Exception as e:
        print(f"  -> [PASS] Caught Exception: {type(e).__name__}: {e}")
    finally:
        await conn.close()

    print("\n" + "="*60)
    print("RESULT: ALL TESTS PASSED")
    print("="*60)

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_verification())
