import sys
import os
import logging
from abc import abstractproperty
from datetime import datetime

# Adjust sys.path to include project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from IMH.main import app
from packages.imh_report.dto import InterviewReport, ReportHeader, ReportDetail, ReportFooter
from packages.imh_history.repository import FileHistoryRepository

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_task_014")

def create_dummy_report() -> InterviewReport:
    header = ReportHeader(
        total_score=95.0,
        grade="S",
        job_category="DEV",
        keywords=["Python", "System Design", "Leadership"]
    )
    
    details = [
        ReportDetail(
            category="Job Competency",
            score=5.0,
            level_description="Excellent",
            feedback="Great depth of knowledge.",
            key_evidence=["Correctly answered questions about GIL"],
            tag_code="job.knowledge"
        )
    ]
    
    footer = ReportFooter(
        strengths=["Technical Depth"],
        weaknesses=[],
        actionable_insights=["Keep up the good work"]
    )
    
    return InterviewReport(
        version="1.0",
        header=header,
        details=details,
        footer=footer
    )

def verify_report_api():
    logger.info("Starting TASK-014 Verification...")
    
    client = TestClient(app)
    repo = FileHistoryRepository()
    
    # 1. Create and Save Dummy Report
    report = create_dummy_report()
    try:
        interview_id = repo.save(report)
        logger.info(f"Saved dummy report with ID: {interview_id}")
    except Exception as e:
        logger.error(f"Failed to save dummy report: {e}")
        sys.exit(1)
        
    try:
        # 2. Verify List API
        logger.info("Verifying GET /api/v1/reports (List)...")
        resp = client.get("/api/v1/reports")
        if resp.status_code != 200:
            logger.error(f"List API failed: {resp.status_code} {resp.text}")
            sys.exit(1)
            
        data = resp.json()
        if not isinstance(data, list):
            logger.error("List API response is not a list")
            sys.exit(1)
            
        # Check if our report is in the list
        found = False
        for item in data:
            if item['interview_id'] == interview_id:
                found = True
                # Check summary fields
                if item['total_score'] != 95.0 or item['grade'] != 'S':
                    logger.error(f"Metadata mismatch: {item}")
                    sys.exit(1)
                break
        
        if not found:
            logger.error(f"Newly created report {interview_id} not found in list")
            sys.exit(1)
        logger.info("[PASS] List API Verified.")
        
        # 3. Verify Detail API
        logger.info(f"Verifying GET /api/v1/reports/{interview_id} (Detail)...")
        resp = client.get(f"/api/v1/reports/{interview_id}")
        if resp.status_code != 200:
            logger.error(f"Detail API failed: {resp.status_code} {resp.text}")
            sys.exit(1)
            
        detail_data = resp.json()
        if detail_data['header']['total_score'] != 95.0:
             logger.error(f"Detail content mismatch: {detail_data}")
             sys.exit(1)
        logger.info("[PASS] Detail API Verified.")
        
        # 4. Verify 404
        logger.info("Verifying 404 for non-existent ID...")
        resp = client.get("/api/v1/reports/non-existent-uuid-12345")
        if resp.status_code != 404:
            logger.error(f"Expected 404 but got {resp.status_code}")
            sys.exit(1)
        logger.info("[PASS] 404 Verified.")

    finally:
        # Cleanup
        logger.info("Cleaning up...")
        # Since specific filename is timestamped, we find it via repo or pattern
        # repo.find_by_id doesn't give filename directly easily without private method or assumption
        # But we know repo base dir.
        import glob
        pattern = os.path.join(repo.base_dir, f"*_{interview_id}.json")
        for f in glob.glob(pattern):
            try:
                os.remove(f)
                logger.info(f"Deleted test file: {f}")
            except Exception as e:
                logger.warning(f"Failed to delete test file {f}: {e}")

    logger.info("ALL TESTS PASSED")

if __name__ == "__main__":
    verify_report_api()
