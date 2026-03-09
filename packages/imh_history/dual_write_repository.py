"""
Dual Write History Repository - Stage 1 Parallel Operation

This module implements the Dual Write Adapter for History/Report persistence.
Writes to both File-based and PostgreSQL repositories simultaneously.

Scope: Checkpoint 2 - Stage 1 병행 운영
Contract: Maintains HistoryRepository interface, no domain logic
"""

import logging
import uuid
import json
from datetime import datetime
from typing import List, Optional
from packages.imh_report.dto import InterviewReport
from packages.imh_history.dto import HistoryMetadata
from packages.imh_history.repository import HistoryRepository

logger = logging.getLogger("imh_history.dual_write")

class DualWriteHistoryRepository(HistoryRepository):
    """
    Dual Write Adapter for Report Persistence.
    
    Stage 1 Behavior:
    - Write: Both File + PostgreSQL
    - Read: File only (Primary)
    - Fail-Fast: Request fails if either write fails
    - ID Generation: Single UUID generated in Adapter, passed to both repos
    """
    
    def __init__(self, primary_repo: HistoryRepository, secondary_repo: HistoryRepository):
        """
        Initialize Dual Write Adapter.
        
        Args:
            primary_repo: FileHistoryRepository (기존 정답 저장소, 읽기 우선)
            secondary_repo: PostgreSQLHistoryRepository (병행 검증 대상)
        """
        self.primary = primary_repo
        self.secondary = secondary_repo
        logger.info("DualWriteHistoryRepository initialized - Stage 1 Parallel Operation")
    
    def save(self, report: InterviewReport) -> str:
        """
        Dual Write: Save to both repositories with SINGLE interview_id.
        
        ID Generation Principle (CRITICAL):
        - Adapter generates UUID once
        - Same UUID passed to both File and PostgreSQL
        - Uses raw_debug_info to inject _interview_id
        
        Storage Order Decision:
        - File first (기존 정답 저장소 우선)
        - PostgreSQL second (FK 제약 검증)
        
        Rationale:
        - File is Primary read path for Stage 1
        - File save succeeds → Service can continue
        - PostgreSQL failure → Detected via exception, logged as partial success
        
        Fail-Fast:
        - Either side fails → Exception propagated
        - Partial success → Structured logging for detection
        
        Returns:
            interview_id (single UUID for both repositories)
        """
        # CRITICAL: Generate interview_id ONCE in Adapter
        interview_id = str(uuid.uuid4())
        primary_success = False
        secondary_success = False
        
        # Inject interview_id into report via raw_debug_info
        if report.raw_debug_info is None:
            report.raw_debug_info = {}
        report.raw_debug_info["_interview_id"] = interview_id
        
        # Also inject session_id if available from test (for FK constraint)
        # In real usage, this would come from the report generation process
        # For now, leave it to be set by the test script
        
        try:
            # Primary first (File)
            logger.info(f"DualWrite: Saving report to PRIMARY (File)...")
            returned_id = self.primary.save(report)
            primary_success = True
            logger.info(f"DualWrite: PRIMARY save succeeded - interview_id={interview_id}")
            
            # Verify ID consistency
            if returned_id != interview_id:
                logger.warning(
                    f"DualWrite: ID mismatch detected - Adapter:{interview_id}, Primary:{returned_id}. "
                    f"Using Adapter ID."
                )
            
            # Secondary next (PostgreSQL)
            logger.info(f"DualWrite: Saving report to SECONDARY (PostgreSQL)...")
            self.secondary.save(report)
            secondary_success = True
            logger.info(f"DualWrite: SECONDARY save succeeded - interview_id={interview_id}")
            
            logger.info(f"DualWrite: BOTH repositories saved successfully - interview_id={interview_id}")
            return interview_id
            
        except Exception as e:
            # Structured Partial Success Detection
            if primary_success and not secondary_success:
                self._log_partial_success(
                    case="PRIMARY_SUCCESS_SECONDARY_FAIL",
                    domain="Report",
                    identifier=interview_id,
                    error=str(e)
                )
            elif not primary_success:
                self._log_partial_success(
                    case="BOTH_FAIL",
                    domain="Report",
                    identifier=interview_id if interview_id else "UNKNOWN",
                    error=str(e)
                )
            
            # Fail-Fast: Propagate exception
            raise
    
    def _log_partial_success(self, case: str, domain: str, identifier: str, error: str):
        """
        Structured logging for partial success detection.
        
        Format enables script parsing for recovery in Checkpoint 3.
        """
        log_entry = {
            "event": "DUAL_WRITE_PARTIAL_SUCCESS",
            "case": case,
            "domain": domain,
            "identifier": identifier,
            "timestamp": datetime.now().isoformat(),
            "error": error
        }
        logger.error(f"PARTIAL_SUCCESS_DETECTED: {json.dumps(log_entry)}")
    
    def find_by_id(self, interview_id: str) -> Optional[InterviewReport]:
        """
        Read from PRIMARY only (Stage 1 policy).
        
        PostgreSQL is not queried by Service layer.
        """
        logger.debug(f"DualWrite: Reading from PRIMARY only - interview_id={interview_id}")
        return self.primary.find_by_id(interview_id)
    
    def find_all(self) -> List[HistoryMetadata]:
        """
        Read from PRIMARY only (Stage 1 policy).
        """
        logger.debug("DualWrite: Reading from PRIMARY only - find_all()")
        return self.primary.find_all()
