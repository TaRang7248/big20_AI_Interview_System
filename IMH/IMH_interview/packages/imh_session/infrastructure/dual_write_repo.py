"""
Dual Write Session Repository - Stage 1 Parallel Operation

This module implements the Dual Write Adapter for Session State persistence.
Writes to both Memory-based and PostgreSQL repositories simultaneously.

Scope: Checkpoint 2 - Stage 1 병행 운영
Contract: Maintains SessionStateRepository interface, no domain logic
"""

import logging
import json
from datetime import datetime
from typing import Optional
from packages.imh_session.dto import SessionContext
from packages.imh_session.state import SessionStatus
from packages.imh_session.repository import SessionStateRepository

logger = logging.getLogger("imh_session.dual_write")

class DualWriteSessionRepository(SessionStateRepository):
    """
    Dual Write Adapter for Session State Persistence.
    
    Stage 1 Behavior:
    - Write: Both Memory + PostgreSQL
    - Read: Memory only (Primary)
    - Fail-Fast: Request fails if either write fails
    """
    
    def __init__(self, primary_repo: SessionStateRepository, secondary_repo: SessionStateRepository):
        """
        Initialize Dual Write Adapter.
        
        Args:
            primary_repo: MemorySessionRepository (Runtime State, 읽기 우선)
            secondary_repo: PostgreSQLSessionRepository (병행 검증 대상)
        """
        self.primary = primary_repo
        self.secondary = secondary_repo
        logger.info("DualWriteSessionRepository initialized - Stage 1 Parallel Operation")
    
    def save_state(self, session_id: str, context: SessionContext) -> None:
        """
        Dual Write: Save to both repositories.
        
        Storage Order Decision:
        - PostgreSQL first (FK 제약 검증 조기 실행)
        - Memory second (Runtime State)
        
        Rationale:
        - Session references Job (FK constraint) → DB validation important
        - Early failure detection via PostgreSQL FK check
        - Memory is Runtime State (재시작 시 재구성 가능)
        
        Fail-Fast:
        - Either side fails → Exception propagated
        - Partial success → Logged with ERROR level
        """
        primary_success = False
        secondary_success = False
        
        try:
            # Secondary first (PostgreSQL) - FK constraint validation
            logger.info(f"DualWrite: Saving session to SECONDARY (PostgreSQL) - session_id={session_id}")
            self.secondary.save_state(session_id, context)
            secondary_success = True
            logger.info(f"DualWrite: SECONDARY save succeeded - session_id={session_id}")
            
            # Primary next (Memory)
            logger.info(f"DualWrite: Saving session to PRIMARY (Memory) - session_id={session_id}")
            self.primary.save_state(session_id, context)
            primary_success = True
            logger.info(f"DualWrite: PRIMARY save succeeded - session_id={session_id}")
            
            logger.info(f"DualWrite: BOTH repositories saved successfully - session_id={session_id}")
            
        except Exception as e:
            # Structured Partial Success Detection
            if secondary_success and not primary_success:
                self._log_partial_success(
                    case="SECONDARY_SUCCESS_PRIMARY_FAIL",
                    domain="Session",
                    identifier=session_id,
                    error=str(e)
                )
            elif not secondary_success:
                self._log_partial_success(
                    case="BOTH_FAIL",
                    domain="Session",
                    identifier=session_id,
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
    
    def get_state(self, session_id: str) -> Optional[SessionContext]:
        """
        Read from PRIMARY only (Stage 1 policy).
        
        Memory is Primary read path.
        PostgreSQL is not queried by Service layer.
        """
        logger.debug(f"DualWrite: Reading from PRIMARY only - session_id={session_id}")
        return self.primary.get_state(session_id)
    
    def update_status(self, session_id: str, status: SessionStatus) -> None:
        """
        Dual Write: Update status in both repositories.
        
        Same ordering as save_state (PostgreSQL first).
        """
        secondary_success = False
        primary_success = False
        
        try:
            # Secondary first
            logger.info(f"DualWrite: Updating status in SECONDARY - session_id={session_id}, status={status}")
            self.secondary.update_status(session_id, status)
            secondary_success = True
            
            # Primary next
            logger.info(f"DualWrite: Updating status in PRIMARY - session_id={session_id}, status={status}")
            self.primary.update_status(session_id, status)
            primary_success = True
            
            logger.info(f"DualWrite: BOTH status updates succeeded - session_id={session_id}")
            
        except Exception as e:
            # Structured Partial Success Detection
            if secondary_success and not primary_success:
                self._log_partial_success(
                    case="SECONDARY_SUCCESS_PRIMARY_FAIL",
                    domain="Session.update_status",
                    identifier=session_id,
                    error=str(e)
                )
            elif not secondary_success:
                self._log_partial_success(
                    case="BOTH_FAIL",
                    domain="Session.update_status",
                    identifier=session_id,
                    error=str(e)
                )
            
            raise
    
    def find_by_job_id(self, job_id: str) -> list[SessionContext]:
        """
        Read from PRIMARY only (Stage 1 policy).
        """
        logger.debug(f"DualWrite: Reading from PRIMARY only - find_by_job_id={job_id}")
        return self.primary.find_by_job_id(job_id)
