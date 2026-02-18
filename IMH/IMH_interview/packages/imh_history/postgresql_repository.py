"""
PostgreSQL implementation of HistoryRepository for TASK-026.

This module provides PostgreSQL-based persistence for Interview Reports,
replacing the file-based FileHistoryRepository while maintaining the same interface.

TASK-026 Contract Compliance:
- Maintains existing HistoryRepository interface (save, find_by_id, find_all)
- Does NOT modify Engine/Service/API boundaries
- Does NOT contain Freeze/Snapshot/State Contract logic (storage only)
- Preserves DTO/Mapper separation
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import List, Optional, Any
from pathlib import Path

import asyncpg  # type: ignore

from packages.imh_report.dto import InterviewReport
from packages.imh_history.dto import HistoryMetadata
from packages.imh_history.repository import HistoryRepository

logger = logging.getLogger("imh_history.postgresql")


class PostgreSQLHistoryRepository(HistoryRepository):
    """
    PostgreSQL-based implementation of HistoryRepository.
    
    Stores interview reports in the 'reports' table with JSONB format.
    Maintains compatibility with FileHistoryRepository interface.
    """
    
    def __init__(self, conn_config: dict):
        """
        Initialize with PostgreSQL connection configuration.
        
        Args:
            conn_config: Dict with keys: host, port, user, password, database
        """
        self.conn_config = conn_config
        self._loop = None  # Lazy initialization for event loop
    
    def _get_event_loop(self):
        """Get or create event loop for async operations"""
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
    
    async def _get_connection(self):
        """Create database connection"""
        return await asyncpg.connect(**self.conn_config)
    
    def save(self, report: InterviewReport) -> str:
        """
        Save interview report to PostgreSQL.
        
        Contract: Stores report data, returns generated interview_id.
        Does NOT modify state or apply any business logic.
        
        Args:
            report: InterviewReport DTO
            
        Returns:
            interview_id: UUID string
        """
        loop = self._get_event_loop()
        return loop.run_until_complete(self._async_save(report))
    
    async def _async_save(self, report: InterviewReport) -> str:
        """Async implementation of save"""
        # Check if interview_id is provided via raw_debug_info (from Dual Write Adapter)
        # This enables single ID generation principle
        if report.raw_debug_info and "_interview_id" in report.raw_debug_info:
            interview_id = report.raw_debug_info["_interview_id"]
            logger.debug(f"Using provided interview_id from Adapter: {interview_id}")
        else:
            # Fallback: Generate ID if not provided (standalone usage)
            interview_id = str(uuid.uuid4())
            logger.debug(f"Generated new interview_id: {interview_id}")
        
        conn = await self._get_connection()
        try:
            # Convert report to JSON
            report_data = report.model_dump(mode='json')
            
            # Extract session_id from raw_debug_info (for FK constraint)
            session_id = None
            if report.raw_debug_info and "_session_id" in report.raw_debug_info:
                session_id = report.raw_debug_info["_session_id"]
            
            # Insert into reports table
            await conn.execute(
                """
                INSERT INTO reports (report_id, session_id, report_data, created_at)
                VALUES ($1, $2, $3, $4)
                """,
                interview_id,
                session_id,  # Can be None if not provided
                json.dumps(report_data),
                datetime.now()
            )
            
            logger.info(f"Report saved: {interview_id}")
            return interview_id
            
        except Exception as e:
            logger.exception(f"Failed to save report: {e}")
            raise
        finally:
            await conn.close()
    
    def find_by_id(self, interview_id: str) -> Optional[InterviewReport]:
        """
        Find report by interview_id.
        
        Contract: Retrieves report if exists, returns None otherwise.
        Does NOT apply any filtering or business logic.
        
        Args:
            interview_id: UUID string
            
        Returns:
            InterviewReport if found, None otherwise
        """
        loop = self._get_event_loop()
        return loop.run_until_complete(self._async_find_by_id(interview_id))
    
    async def _async_find_by_id(self, interview_id: str) -> Optional[InterviewReport]:
        """Async implementation of find_by_id"""
        conn = await self._get_connection()
        try:
            row = await conn.fetchrow(
                "SELECT report_data FROM reports WHERE report_id = $1",
                interview_id
            )
            
            if not row:
                return None
            
            # Parse JSON and reconstruct InterviewReport
            data = json.loads(row['report_data'])
            return InterviewReport(**data)
            
        except Exception as e:
            logger.exception(f"Failed to retrieve report {interview_id}: {e}")
            return None
        finally:
            await conn.close()
    
    def find_all(self) -> List[HistoryMetadata]:
        """
        Retrieve all report metadata, sorted by newest first.
        
        Contract: Returns list of HistoryMetadata DTOs.
        Does NOT filter by status or apply business logic.
        
        Returns:
            List of HistoryMetadata (sorted by created_at DESC)
        """
        loop = self._get_event_loop()
        return loop.run_until_complete(self._async_find_all())
    
    async def _async_find_all(self) -> List[HistoryMetadata]:
        """Async implementation of find_all"""
        conn = await self._get_connection()
        try:
            rows = await conn.fetch(
                """
                SELECT report_id, report_data, created_at
                FROM reports
                ORDER BY created_at DESC
                """
            )
            
            results = []
            for row in rows:
                try:
                    data = json.loads(row['report_data'])
                    header = data.get('header', {})
                    
                    meta = HistoryMetadata(
                        interview_id=row['report_id'],
                        timestamp=row['created_at'],
                        total_score=header.get('total_score', 0.0),
                        grade=header.get('grade', 'N/A'),
                        job_category=header.get('job_category', 'Unknown'),
                        job_id=header.get('job_id'),
                        status="EVALUATED",  # Reports in DB are evaluated
                        started_at=row['created_at'],  # Proxy
                        file_path=f"postgresql://{row['report_id']}"  # Indicate DB storage
                    )
                    results.append(meta)
                except Exception as e:
                    logger.warning(f"Failed to parse report {row['report_id']}: {e}")
                    continue
            
            return results
            
        finally:
            await conn.close()
    
    def update_interview_status(self, session_id: str, status: Any) -> None:
        """
        Implementation of SessionHistoryRepository.update_interview_status.
        
        Contract: Logs status transitions but does NOT persist intermediate states.
        This maintains compatibility with FileHistoryRepository behavior.
        """
        logger.info(f"[PostgreSQLHistoryRepo] Status update: {session_id} -> {status}")
    
    def save_interview_result(self, session_id: str, result_data: Any) -> None:
        """
        Implementation of SessionHistoryRepository.save_interview_result.
        
        Contract: Saves final InterviewReport.
        """
        if isinstance(result_data, InterviewReport):
            self.save(result_data)
        else:
            logger.warning(
                f"[PostgreSQLHistoryRepo] save_interview_result called with {type(result_data)}. "
                f"Expected InterviewReport."
            )
