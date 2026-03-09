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
    
    def _run_sync(self, coro_func, *args, **kwargs):
        """Safely execute a coroutine synchronously, even if an event loop is already running."""
        import concurrent.futures
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
            
        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(lambda: asyncio.run(coro_func(*args, **kwargs))).result()
        else:
            return asyncio.run(coro_func(*args, **kwargs))
    
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
        return self._run_sync(self._async_save, report)
    
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
                
            # TASK-032 Idempotency: True DB-Level atomic UPSERT
            # Use ON CONFLICT (session_id) DO UPDATE to guarantee idempotency under concurrent load
            if session_id:
                query = """
                    INSERT INTO evaluation_scores (report_id, session_id, report_data, created_at)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (session_id) DO UPDATE 
                    SET report_data = EXCLUDED.report_data
                    RETURNING report_id;
                """
                result_id = await conn.fetchval(
                    query,
                    interview_id,
                    session_id,
                    json.dumps(report_data),
                    datetime.now()
                )
                logger.info(f"Report saved (Upsert): {result_id}")
                return result_id
            else:
                # Fallback for reports without session_id (Playground etc)
                await conn.execute(
                    """
                    INSERT INTO evaluation_scores (report_id, session_id, report_data, created_at)
                    VALUES ($1, $2, $3, $4)
                    """,
                    interview_id,
                    None,
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
        return self._run_sync(self._async_find_by_id, interview_id)
    
    async def _async_find_by_id(self, interview_id: str) -> Optional[InterviewReport]:
        """Async implementation of find_by_id"""
        conn = await self._get_connection()
        try:
            row = await conn.fetchrow(
                "SELECT report_data FROM evaluation_scores WHERE report_id = $1",
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
        return self._run_sync(self._async_find_all)
    
    async def _async_find_all(self) -> List[HistoryMetadata]:
        """Async implementation of find_all"""
        conn = await self._get_connection()
        try:
            rows = await conn.fetch(
                """
                SELECT report_id, report_data, created_at
                FROM evaluation_scores
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
        Update interview status in PostgreSQL (Authority).

        Contract: Persists the given status to the interviews table.
        This is a real DB UPDATE that enforces the PostgreSQL Authority principle.
        """
        import asyncio
        # Convert Enum to string if needed
        status_value = status.value if hasattr(status, 'value') else str(status)
        self._run_sync(self._async_update_interview_status, session_id, status_value)

    async def _async_update_interview_status(self, session_id: str, status_value: str) -> None:
        """Async implementation of update_interview_status."""
        conn = await self._get_connection()
        try:
            await conn.execute(
                """
                UPDATE interviews
                SET status = $1::session_status, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = $2
                """,
                status_value,
                session_id
            )
            logger.info("[PostgreSQLHistoryRepo] Status persisted: %s -> %s", session_id, status_value)
        except Exception as e:
            logger.exception("[PostgreSQLHistoryRepo] Failed to update status %s: %s", session_id, e)
            raise
        finally:
            await conn.close()
    
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
