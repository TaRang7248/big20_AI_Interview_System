"""
Test script for PostgreSQL Repositories (Checkpoint 1)

This script verifies that the 3 PostgreSQL repository implementations:
1. Connect to the database successfully
2. Support basic save/retrieve operations
3. Maintain interface compatibility
4. Do NOT violate any existing contracts

Usage:
    python scripts/test_repositories.py
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
logger = logging.getLogger("test_repositories")

# Import after paths set
from packages.imh_history.postgresql_repository import PostgreSQLHistoryRepository
from packages.imh_session.infrastructure.postgresql_repo import PostgreSQLSessionRepository
from packages.imh_job.postgresql_repository import PostgreSQLJobRepository

from packages.imh_report.dto import InterviewReport, ReportHeader, ReportDetail, ReportFooter
from packages.imh_session.dto import SessionContext
from packages.imh_session.state import SessionStatus
from packages.imh_job.models import Job, JobStatus

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

def test_history_repository():
    """Test PostgreSQLHistoryRepository"""
    logger.info("=== Testing PostgreSQLHistoryRepository ===")
    
    repo = PostgreSQLHistoryRepository(conn_config)
    
    # Test save
    test_report = InterviewReport(
        header=ReportHeader(
            job_id="test-job-1",
            job_category="Software Engineer",
            total_score=85.5,
            grade="A"
        ),
        details=[],
        footer=ReportFooter(
            strengths=["Good communication"],
            weaknesses=[],
            actionable_insights=[]
        )
    )
    
    report_id = repo.save(test_report)
    logger.info(f"✓ Report saved with ID: {report_id}")
    
    # Test find_by_id
    retrieved = repo.find_by_id(report_id)
    assert retrieved is not None, "Report not found"
    assert retrieved.header.total_score == 85.5, "Score mismatch"
    logger.info(f"✓ Report retrieved successfully")
    
    # Test find_all
    all_reports = repo.find_all()
    assert len(all_reports) > 0, "No reports found"
    logger.info(f"✓ Found {len(all_reports)} total reports")
    
    logger.info("✓ PostgreSQLHistoryRepository: ALL TESTS PASSED\n")
    return True

def test_session_repository():
    """Test PostgreSQLSessionRepository"""
    logger.info("=== Testing PostgreSQLSessionRepository ===")
    
    repo = PostgreSQLSessionRepository(conn_config)
    
    # Test save_state
    test_session = SessionContext(
        session_id="test-session-1",
        job_id="test-job-1",
        status="APPLIED"
    )
    
    repo.save_state("test-session-1", test_session)
    logger.info(f"✓ Session saved")
    
    # Test get_state
    retrieved = repo.get_state("test-session-1")
    assert retrieved is not None, "Session not found"
    assert retrieved.job_id == "test-job-1", "Job ID mismatch"
    logger.info(f"✓ Session retrieved successfully")
    
    # Test update_status
    from packages.imh_session.state import SessionStatus
    repo.update_status("test-session-1", SessionStatus.IN_PROGRESS)
    updated = repo.get_state("test-session-1")
    assert updated.status == SessionStatus.IN_PROGRESS or updated.status == "IN_PROGRESS", "Status not updated"
    logger.info(f"✓ Session status updated")
    
    # Test find_by_job_id
    sessions = repo.find_by_job_id("test-job-1")
    assert len(sessions) > 0, "No sessions found for job"
    logger.info(f"✓ Found {len(sessions)} sessions for job")
    
    logger.info("✓ PostgreSQLSessionRepository: ALL TESTS PASSED\n")
    return True

def test_job_repository():
    """Test PostgreSQLJobRepository"""
    logger.info("=== Testing PostgreSQL JobRepository ===")
    
    repo = PostgreSQLJobRepository(conn_config)
    
    # Need to import JobPolicy
    from packages.imh_job.models import JobPolicy
    from packages.imh_session.policy import InterviewMode
    
    # Create policy first
    test_policy = JobPolicy(
        mode=InterviewMode.ACTUAL,
        total_question_limit=5,
        min_question_count=10,
        description="Test job for software engineers"
    )
    
    # Test save (DRAFT job)
    test_job = Job(
        job_id="test-job-1",
        title="Senior Software Engineer",
        status=JobStatus.DRAFT,
        policy=test_policy,
        created_at=datetime.now()
    )
    
    repo.save(test_job)
    logger.info(f"✓ Job saved (DRAFT)")
    
    # Test find_by_id
    retrieved = repo.find_by_id("test-job-1")
    assert retrieved is not None, "Job not found"
    assert retrieved.title == "Senior Software Engineer", "Title mismatch"
    logger.info(f"✓ Job retrieved successfully")
    
    # Test save (PUBLISHED job - use publish() method)
    test_job.publish()  # This changes status to PUBLISHED and sets published_at
    repo.save(test_job)
    logger.info(f"✓ Job updated to PUBLISHED with policy frozen")
    
    # Test find_published
    published = repo.find_published()
    assert len(published) > 0, "No published jobs found"
    logger.info(f"✓ Found {len(published)} published jobs")
    
    logger.info("✓ PostgreSQLJobRepository: ALL TESTS PASSED\n")
    return True

def verify_contracts():
    """Verify that implementation does NOT violate contracts"""
    logger.info("=== Verifying Contract Compliance ===")
    
    # Check 1: Interface compatibility
    from packages.imh_history.repository import HistoryRepository
    from packages.imh_session.repository import SessionStateRepository
    from packages.imh_job.repository import JobPostingRepository
    
    assert issubclass(PostgreSQLHistoryRepository, HistoryRepository), \
        "PostgreSQLHistoryRepository does not implement HistoryRepository interface"
    assert issubclass(PostgreSQLSessionRepository, SessionStateRepository), \
        "PostgreSQLSessionRepository does not implement SessionStateRepository interface"
    assert issubclass(PostgreSQLJobRepository, JobPostingRepository), \
        "PostgreSQLJobRepository does not implement JobPostingRepository interface"
    
    logger.info("✓ All repositories implement correct interfaces")
    
    # Check 2: No Engine logic in repositories
    # (This would require code analysis, but we can check imports)
    import inspect
    
    for repo_class in [PostgreSQLHistoryRepository, PostgreSQLSessionRepository, PostgreSQLJobRepository]:
        source = inspect.getsource(repo_class)
        assert 'InterviewEngine' not in source, f"{repo_class.__name__} imports Engine"
        assert 'PolicyEngine' not in source, f"{repo_class.__name__} imports PolicyEngine"
        logger.info(f"✓ {repo_class.__name__} does NOT contain Engine logic")
    
    logger.info("✓ Contract Compliance: VERIFIED\n")
    return True

def main():
    logger.info("=" * 60)
    logger.info("PostgreSQL Repositories Test (Checkpoint 1)")
    logger.info("=" * 60)
    
    try:
        # Test in order of FK dependencies: Job -> Session -> History
        test_job_repository()
        test_session_repository()
        test_history_repository()
        
        # Verify contracts
        verify_contracts()
        
        logger.info("=" * 60)
        logger.info("✓✓✓ ALL TESTS PASSED ✓✓✓")
        logger.info("=" * 60)
        return 0
        
    except Exception as e:
        logger.exception(f"Test failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
