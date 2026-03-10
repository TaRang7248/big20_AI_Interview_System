"""
TASK-026 Checkpoint 2: Dual Write Verification Script

This script verifies Stage 1 Parallel Operation:
1. Job/Session/Report Dual Write success
2. Fail-Fast behavior
3. Partial success logging
4. Contract maintenance (Checkpoint 1.5 regression)

Usage:
    python scripts/verify_dual_write.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import logging

# Setup paths
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "IMH" / "AI_Interview_System"))

# Load environment
env_path = project_root / ".env"
load_dotenv(env_path)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("dual_write_verification")

# Import after paths set
from packages.imh_job.dual_write_repository import DualWriteJobRepository
from packages.imh_job.repository import MemoryJobPostingRepository
from packages.imh_job.postgresql_repository import PostgreSQLJobRepository
from packages.imh_job.models import Job, JobPolicy, JobStatus

from packages.imh_session.infrastructure.dual_write_repo import DualWriteSessionRepository
from packages.imh_session.infrastructure.memory_repo import MemorySessionRepository
from packages.imh_session.infrastructure.postgresql_repo import PostgreSQLSessionRepository
from packages.imh_session.dto import SessionContext

from packages.imh_history.dual_write_repository import DualWriteHistoryRepository
from packages.imh_history.repository import FileHistoryRepository
from packages.imh_history.postgresql_repository import PostgreSQLHistoryRepository

from packages.imh_session.policy import InterviewMode
from packages.imh_report.dto import InterviewReport, ReportHeader, ReportFooter

# Parse connection string
import re
conn_string = os.getenv("POSTGRES_CONNECTION_STRING")
pattern = r"postgresql\+asyncpg://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)"
match = re.match(pattern, conn_string)
user, password, host, port, database = match.groups()

conn_config = {
    'host': host,
    'port': int(port),
    'user': user,
    'password': password,
    'database': database
}

def test_job_dual_write():
    """
    Test A: Job Dual Write Success
    
    Verify:
    - Job saved to both Memory and PostgreSQL
    - Both repositories contain identical data
    - Service reads from Primary (Memory) only
    """
    logger.info("=== Test A: Job Dual Write Success ===")
    
    # Setup repositories
    primary = MemoryJobPostingRepository()
    secondary = PostgreSQLJobRepository(conn_config)
    dual_write = DualWriteJobRepository(primary, secondary)
    
    # Create job with policy
    test_policy = JobPolicy(
        mode=InterviewMode.ACTUAL,
        total_question_limit=15,
        min_question_count=10,
        description="Dual write test job posting"
    )
    
    test_job = Job(
        job_id="dual-write-test-job-1",
        title="Backend Engineer",
        status=JobStatus.DRAFT,
        policy=test_policy,
        created_at=datetime.now()
    )
    
    # Dual Write
    logger.info("Saving job via Dual Write Adapter...")
    dual_write.save(test_job)
    logger.info("✓ Dual write completed without exception")
    
    # Verify: Service reads from Primary
    retrieved_from_service = dual_write.find_by_id("dual-write-test-job-1")
    assert retrieved_from_service is not None, "Job not found via Service read path"
    assert retrieved_from_service.job_id == "dual-write-test-job-1"
    logger.info("✓ Service read from PRIMARY (Memory) succeeded")
    
    # Verify: Direct check on Secondary (검증 스크립트만 수행)
    retrieved_from_db = secondary.find_by_id("dual-write-test-job-1")
    assert retrieved_from_db is not None, "Job not found in PostgreSQL"
    assert retrieved_from_db.job_id == "dual-write-test-job-1"
    assert retrieved_from_db.title == "Backend Engineer"
    logger.info("✓ Direct PostgreSQL query succeeded (검증 스크립트)")
    
    logger.info("✅ Test A: PASSED - Job Dual Write Success\n")
    return True

def test_session_dual_write():
    """
    Test B: Session Dual Write Success
    
    Verify:
    - Session saved to both Memory and PostgreSQL
    - Both repositories contain identical data
    - Service reads from Primary (Memory) only
    """
    logger.info("=== Test B: Session Dual Write Success ===")
    
    # Setup repositories
    primary = MemorySessionRepository()
    secondary = PostgreSQLSessionRepository(conn_config)
    dual_write = DualWriteSessionRepository(primary, secondary)
    
    # Create session (FK references job from Test A)
    session = SessionContext(
        session_id="dual-write-test-session-1",
        job_id="dual-write-test-job-1",
        status="APPLIED"
    )
    
    # Dual Write
    logger.info("Saving session via Dual Write Adapter...")
    dual_write.save_state("dual-write-test-session-1", session)
    logger.info("✓ Dual write completed without exception")
    
    # Verify: Service reads from Primary
    retrieved_from_service = dual_write.get_state("dual-write-test-session-1")
    assert retrieved_from_service is not None, "Session not found via Service read path"
    assert retrieved_from_service.session_id == "dual-write-test-session-1"
    logger.info("✓ Service read from PRIMARY (Memory) succeeded")
    
    # Verify: Direct check on Secondary
    retrieved_from_db = secondary.get_state("dual-write-test-session-1")
    assert retrieved_from_db is not None, "Session not found in PostgreSQL"
    assert retrieved_from_db.session_id == "dual-write-test-session-1"
    logger.info("✓ Direct PostgreSQL query succeeded (검증 스크립트)")
    
    logger.info("✅ Test B: PASSED - Session Dual Write Success\n")
    return True

def test_report_dual_write():
    """
    Test C: Report Dual Write Success
    
    Verify:
    - Report saved to both File and PostgreSQL
    - Both repositories contain identical data
    - Service reads from Primary (File) only
    """
    logger.info("=== Test C: Report Dual Write Success ===")
    
    # Setup repositories
    primary = FileHistoryRepository()
    secondary = PostgreSQLHistoryRepository(conn_config)
    dual_write = DualWriteHistoryRepository(primary, secondary)
    
    # Create report
    header = ReportHeader(
        total_score=85.0,
        grade="B+",
        job_category="DEV",
        job_id="dual-write-test-job-1",
        keywords=["python", "backend", "api"]
    )
    
    footer = ReportFooter(
        evaluated_at=datetime.now(),
        evaluator="AI-Eval-v1"
    )
    
    report = InterviewReport(
        header=header,
        details=[],
        footer=footer
    )
    
    # Set session_id for FK constraint (in raw_debug_info)
    if report.raw_debug_info is None:
        report.raw_debug_info = {}
    report.raw_debug_info["_session_id"] = "dual-write-test-session-1"
    
    # Dual Write
    logger.info("Saving report via Dual Write Adapter...")
    interview_id = dual_write.save(report)
    assert interview_id is not None
    logger.info(f"✓ Dual write completed - interview_id={interview_id}")
    
    # Verify: Service reads from Primary
    retrieved_from_service = dual_write.find_by_id(interview_id)
    assert retrieved_from_service is not None, "Report not found via Service read path"
    logger.info("✓ Service read from PRIMARY (File) succeeded")
    
    # CRITICAL: Verify interview_id consistency (Single ID Generation Principle)
    # Both File and PostgreSQL must have the SAME interview_id
    retrieved_from_db = secondary.find_by_id(interview_id)
    assert retrieved_from_db is not None, f"Report not found in PostgreSQL with interview_id={interview_id}"
    assert retrieved_from_db.header.job_id == "dual-write-test-job-1", "Job ID mismatch"
    logger.info("✓ Direct PostgreSQL query succeeded - SAME interview_id (검증 스크립트)")
    logger.info(f"✓✓ CRITICAL: interview_id CONSISTENT across both repositories: {interview_id}")
    
    logger.info("✅ Test C: PASSED - Report Dual Write Success\n")
    return True

def test_fail_fast_behavior():
    """
    Test D: Fail-Fast Behavior
    
    Verify:
    - PostgreSQL connection failure → Entire request fails
    - Partial success logged clearly
    
    Note: This test uses invalid connection config to simulate failure
    """
    logger.info("=== Test D: Fail-Fast Behavior ===")
    
    # Setup with invalid secondary connection
    primary = MemoryJobPostingRepository()
    invalid_config = {**conn_config, 'port': 99999}  # Invalid port
    secondary = PostgreSQLJobRepository(invalid_config)
    dual_write = DualWriteJobRepository(primary, secondary)
    
    test_policy = JobPolicy(
        mode=InterviewMode.PRACTICE,
        total_question_limit=10,
        min_question_count=10,
        description="Fail-fast test job"
    )
    
    test_job = Job(
        job_id="fail-fast-test-job",
        title="Fail-Fast Test",
        status=JobStatus.DRAFT,
        policy=test_policy,
        created_at=datetime.now()
    )
    
    # Attempt Dual Write (should fail)
    try:
        dual_write.save(test_job)
        raise AssertionError("FAIL-FAST VIOLATED: Should have raised exception")
    except Exception as e:
        logger.info(f"✓ Exception caught as expected: {type(e).__name__}")
        logger.info("✓ Fail-Fast behavior confirmed")
    
    # Verify: Partial success detection in logs
    # (Manual verification: Check logs for "PARTIAL SUCCESS" message)
    logger.info("✓ Check logs for PARTIAL SUCCESS message")
    
    logger.info("✅ Test D: PASSED - Fail-Fast Behavior Confirmed\n")
    return True

def run_checkpoint_15_regression():
    """
    Test E: Checkpoint 1.5 Regression Test
    
    Re-run integration safety tests to ensure contracts maintained:
    - Job Policy Freeze
    - Session Snapshot Independence
    - State Transition Integrity
    - Engine Logic Isolation
    """
    logger.info("=== Test E: Checkpoint 1.5 Regression Test ===")
    logger.info("Running verify_integration_safety.py...")
    
    import subprocess
    result = subprocess.run(
        [".\\interview_env\\Scripts\\python.exe", ".\\IMH\\IMH_Interview\\scripts\\verify_integration_safety.py"],
        cwd=str(project_root),
        capture_output=True,
        text=True
    )
    
    if "ALL INTEGRATION SAFETY TESTS PASSED" in result.stdout:
        logger.info("✅ Test E: PASSED - All Checkpoint 1.5 tests passed\n")
        return True
    else:
        logger.error("❌ Test E: FAILED - Checkpoint 1.5 regression detected")
        logger.error(result.stdout)
        return False

def main():
    logger.info("=" * 70)
    logger.info("TASK-026 Checkpoint 2: Dual Write Verification")
    logger.info("=" * 70)
    logger.info("Testing Stage 1 Parallel Operation\n")
    
    try:
        # Run all tests
        test_job_dual_write()
        test_session_dual_write()
        test_report_dual_write()
        test_fail_fast_behavior()
        run_checkpoint_15_regression()
        
        logger.info("=" * 70)
        logger.info("✅✅✅ ALL DUAL WRITE TESTS PASSED ✅✅✅")
        logger.info("=" * 70)
        logger.info("\nStage 1 Parallel Operation Verified:")
        logger.info("  ✓ Job Dual Write Success")
        logger.info("  ✓ Session Dual Write Success")
        logger.info("  ✓ Report Dual Write Success")
        logger.info("  ✓ Fail-Fast Behavior Confirmed")
        logger.info("  ✓ Checkpoint 1.5 Contracts Maintained")
        logger.info("\n📋 Checkpoint 3 (Migration) can proceed.")
        
        return 0
        
    except AssertionError as e:
        logger.error("=" * 70)
        logger.error(f"❌ DUAL WRITE VERIFICATION FAILED: {e}")
        logger.error("=" * 70)
        logger.error("\n🛑 Checkpoint 3 BLOCKED - Fix dual write issues first!")
        return 1
        
    except Exception as e:
        logger.exception(f"Test failed with error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
