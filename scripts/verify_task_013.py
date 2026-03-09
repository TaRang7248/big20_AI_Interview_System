import sys
import os
import shutil
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from packages.imh_report.dto import InterviewReport, ReportHeader, ReportDetail, ReportFooter
from packages.imh_history.repository import FileHistoryRepository

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_task_013")

def test_history_persistence():
    # 1. Setup Repo with temporary test dir
    test_dir = os.path.join("IMH", "IMH_Interview", "data", "reports_test")
    
    # Cleanup previous runs
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    
    logger.info(f"Initializing repository at {test_dir}")
    repo = FileHistoryRepository(base_dir=test_dir)
    
    # 2. Create Mock Report
    mock_report = InterviewReport(
        header=ReportHeader(
            total_score=85.5,
            grade="B",
            job_category="DEV",
            keywords=["Python", "FastAPI"]
        ),
        details=[
            ReportDetail(
                category="Job",
                score=80.0,
                level_description="Good",
                feedback="Solid knowledge",
                key_evidence=["Mentioned DI", "Used Pydantic"],
                tag_code="job.knowledge"
            )
        ],
        footer=ReportFooter(
            strengths=["Coding"],
            weaknesses=["System Design"],
            actionable_insights=["Study patterns"]
        )
    )
    
    # 3. Test Save (Create)
    logger.info("Testing Save...")
    interview_id = repo.save(mock_report)
    assert interview_id, "Save failed to return ID"
    logger.info(f"Saved Report ID: {interview_id}")
    
    # Verify file exists
    expected_files = os.listdir(test_dir)
    assert len(expected_files) == 1, "File not actually created in directory"
    logger.info(f"Verified file creation: {expected_files[0]}")
    
    # 4. Test Find By ID (Read)
    logger.info("Testing Find By ID...")
    loaded_report = repo.find_by_id(interview_id)
    assert loaded_report, "Find By ID returned None"
    assert loaded_report.header.total_score == 85.5
    assert loaded_report.header.grade == "B"
    assert loaded_report.details[0].tag_code == "job.knowledge"
    logger.info("Find By ID passed (Data consistency check OK)")
    
    # 5. Test Find All (Read List)
    logger.info("Testing Find All (Metadata)...")
    all_meta = repo.find_all()
    assert len(all_meta) == 1, "Find All should return 1 record"
    meta = all_meta[0]
    
    assert meta.interview_id == interview_id
    assert meta.total_score == 85.5
    assert meta.grade == "B"
    assert meta.job_category == "DEV"
    
    # Check timestamp validity (within 5 seconds)
    time_diff = (datetime.now() - meta.timestamp).total_seconds()
    assert abs(time_diff) < 10, f"Timestamp too divergent: {time_diff}s"
    
    logger.info("Find All passed (Metadata extraction check OK)")
    
    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    logger.info("Cleanup complete")

if __name__ == "__main__":
    try:
        test_history_persistence()
        print("SUCCESS")
    except Exception as e:
        logger.exception("Verification Failed")
        print("FAILURE")
        sys.exit(1)
