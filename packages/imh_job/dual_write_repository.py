"""
Dual Write Job Repository - Stage 1 Parallel Operation

This module implements the Dual Write Adapter for Job Posting persistence.
Writes to both Memory-based and PostgreSQL repositories simultaneously.

Scope: Checkpoint 2 - Stage 1 병행 운영
Contract: Maintains JobPostingRepository interface, no domain logic
"""

import logging
import json
from datetime import datetime
from typing import Optional, List
from packages.imh_job.models import Job
from packages.imh_job.repository import JobPostingRepository

logger = logging.getLogger("imh_job.dual_write")

class DualWriteJobRepository(JobPostingRepository):
    """
    Dual Write Adapter for Job Posting Persistence.
    
    Stage 1 Behavior:
    - Write: Both Memory + PostgreSQL
    - Read: Memory only (Primary)
    - Fail-Fast: Request fails if either write fails
    """
    
    def __init__(self, primary_repo: JobPostingRepository, secondary_repo: JobPostingRepository):
        """
        Initialize Dual Write Adapter.
        
        Args:
            primary_repo: MemoryJobPostingRepository (Runtime State, 읽기 우선)
            secondary_repo: PostgreSQLJobRepository (병행 검증 대상)
        """
        self.primary = primary_repo
        self.secondary = secondary_repo
        logger.info("DualWriteJobRepository initialized - Stage 1 Parallel Operation")
    
    def save(self, job: Job) -> None:
        """
        Dual Write: Save to both repositories.
        
        Storage Order Decision:
        - PostgreSQL first (UNIQUE 제약, Freeze Contract 영속성 우선)
        - Memory second (Runtime State)
        
        Rationale:
        - Job is FK reference target for Session/Report
        - UNIQUE(job_id) constraint validation important
        - Policy Snapshot immutability enforcement via DB
        - Memory is runtime cache (재시작 시 재로드)
        
        Fail-Fast:
        - Either side fails → Exception propagated
        - Partial success → Logged with ERROR level
        """
        primary_success = False
        secondary_success = False
        
        try:
            # Secondary first (PostgreSQL) - UNIQUE + FK target
            logger.info(f"DualWrite: Saving job to SECONDARY (PostgreSQL) - job_id={job.job_id}")
            self.secondary.save(job)
            secondary_success = True
            logger.info(f"DualWrite: SECONDARY save succeeded - job_id={job.job_id}")
            
            # Primary next (Memory)
            logger.info(f"DualWrite: Saving job to PRIMARY (Memory) - job_id={job.job_id}")
            self.primary.save(job)
            primary_success = True
            logger.info(f"DualWrite: PRIMARY save succeeded - job_id={job.job_id}")
            
            logger.info(f"DualWrite: BOTH repositories saved successfully - job_id={job.job_id}")
            
        except Exception as e:
            # Structured Partial Success Detection
            if secondary_success and not primary_success:
                self._log_partial_success(
                    case="SECONDARY_SUCCESS_PRIMARY_FAIL",
                    domain="Job",
                    identifier=job.job_id,
                    error=str(e)
                )
            elif not secondary_success:
                self._log_partial_success(
                    case="BOTH_FAIL",
                    domain="Job",
                    identifier=job.job_id,
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
    
    def find_by_id(self, job_id: str) -> Optional[Job]:
        """
        Read from PRIMARY only (Stage 1 policy).
        
        Memory is Primary read path.
        PostgreSQL is not queried by Service layer.
        """
        logger.debug(f"DualWrite: Reading from PRIMARY only - job_id={job_id}")
        return self.primary.find_by_id(job_id)
    
    def find_published(self) -> List[Job]:
        """
        Read from PRIMARY only (Stage 1 policy).
        """
        logger.debug("DualWrite: Reading from PRIMARY only - find_published()")
        return self.primary.find_published()
