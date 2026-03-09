"""
PostgreSQL implementation of JobPostingRepository for TASK-026.

This module provides PostgreSQL-based persistence for Job Postings,
replacing the in-memory MemoryJobPostingRepository while maintaining the same interface.

TASK-026 Contract Compliance:
- Maintains existing JobPostingRepository interface
- Does NOT modify Engine/Service/API boundaries
- Does NOT contain Freeze/Snapshot/State Contract logic (storage only)
- Preserves DTO/Mapper separation
- Stores Immutable Snapshot separately (TASK-019 Freeze at Publish contract)
"""

import asyncio
import json
import logging
from typing import List, Optional
from datetime import datetime

import asyncpg  # type: ignore

from packages.imh_job.models import Job, JobStatus
from packages.imh_job.repository import JobPostingRepository

logger = logging.getLogger("imh_job.postgresql")


class PostgreSQLJobRepository(JobPostingRepository):
    """
    PostgreSQL-based implementation of JobPostingRepository.
    
    Stores jobs in the 'jobs' table with separate immutable_snapshot field
    to support TASK-019 Freeze at Publish contract.
    """
    
    def __init__(self, conn_config: dict):
        """
        Initialize with PostgreSQL connection configuration.
        
        Args:
            conn_config: Dict with keys: host, port, user, password, database
        """
        self.conn_config = conn_config
    
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
        # Sanitize DSN for asyncpg compatibility if it's passed as 'dsn' in conn_config
        if 'dsn' in self.conn_config:
            self.conn_config['dsn'] = self.conn_config['dsn'].replace("postgresql+asyncpg://", "postgresql://")
        # Ensure we handle dict-based config too if needed, but for now assuming dsn usage or valid dict
        return await asyncpg.connect(**self.conn_config)
    
    def save(self, job: Job) -> None:
        """
        Save or update job to PostgreSQL.
        
        Contract: Stores complete Job (including immutable snapshot if PUBLISHED).
        Does NOT enforce Freeze logic (that's Engine's responsibility).
        
        Args:
            job: Job domain object
        """
        self._run_sync(self._async_save, job)
    
    async def _async_save(self, job: Job) -> None:
        """Async implementation of save"""
        conn = await self._get_connection()
        try:
            # Use Pydantic model_dump for proper datetime serialization
            job_dict = job.model_dump(mode='json') if hasattr(job, 'model_dump') else job.dict()
            
            # Extract status value
            status_value = job.status.value if hasattr(job.status, 'value') else str(job.status)
            
            # Prepare immutable snapshot (if job is PUBLISHED)
            immutable_snapshot = None
            if job.status == JobStatus.PUBLISHED and hasattr(job, '_policy'):
                # Serialize policy snapshot
                policy_dict = job._policy.model_dump(mode='json') if hasattr(job._policy, 'model_dump') else job._policy.dict()
                immutable_snapshot = json.dumps(policy_dict)
            
            # Prepare mutable data (metadata only, exclude structured DB columns)
            mutable_dict = job_dict.get('metadata', {})
            mutable_data = json.dumps(mutable_dict)
            
            # Upsert job
            await conn.execute(
                """
                INSERT INTO jobs (
                    job_id, title, company, status, published_at,
                    immutable_snapshot, mutable_data, created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4::job_status, $5, $6, $7, $8, $9
                )
                ON CONFLICT (job_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    status = EXCLUDED.status,
                    published_at = EXCLUDED.published_at,
                    immutable_snapshot = EXCLUDED.immutable_snapshot,
                    mutable_data = EXCLUDED.mutable_data,
                    updated_at = CURRENT_TIMESTAMP
                """,
                job.job_id,
                getattr(job, 'title', ''),
                getattr(job, 'company', None),
                status_value,
                getattr(job, 'published_at', None),
                immutable_snapshot,
                mutable_data,
                getattr(job, 'created_at', datetime.now()),
                datetime.now()
            )
            
            logger.info(f"Job saved: {job.job_id} (status: {status_value})")
            
        except Exception as e:
            logger.exception(f"Failed to save job {job.job_id}: {e}")
            raise
        finally:
            await conn.close()
    
    def find_by_id(self, job_id: str) -> Optional[Job]:
        """
        Find job by ID.
        
        Contract: Returns Job if exists, None otherwise.
        Does NOT apply any filtering or business logic.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job if found, None otherwise
        """
        return self._run_sync(self._async_find_by_id, job_id)
    
    async def _async_find_by_id(self, job_id: str) -> Optional[Job]:
        """Async implementation of find_by_id"""
        conn = await self._get_connection()
        try:
            row = await conn.fetchrow(
                """
                SELECT job_id, title, company, status, published_at,
                       immutable_snapshot, mutable_data, created_at
                FROM jobs
                WHERE job_id = $1
                """,
                job_id
            )
            
            if not row:
                return None
            
            # Reconstruct Job object
            job_data = {
                'job_id': row['job_id'],
                'title': row['title'],
                'company': row['company'],
                'status': JobStatus(row['status']),
                'published_at': row['published_at'],
                'created_at': row['created_at'],
            }
            
            # Merge mutable data
            if row['mutable_data']:
                mutable = json.loads(row['mutable_data'])
                job_data.update(mutable)
            
            # CRITICAL: Restore policy from immutable_snapshot
            if row['immutable_snapshot']:
                from packages.imh_job.models import JobPolicy
                policy_dict = json.loads(row['immutable_snapshot'])
                policy = JobPolicy(**policy_dict)
                job_data['policy'] = policy
            
            return Job(**job_data)
            
        except Exception as e:
            logger.exception(f"Failed to retrieve job {job_id}: {e}")
            return None
        finally:
            await conn.close()
    
    def find_published(self) -> List[Job]:
        """
        Find all published jobs.
        
        Contract: Returns list of Jobs with status=PUBLISHED.
        Does NOT apply any other filtering.
        
        Returns:
            List of published Jobs
        """
        return self._run_sync(self._async_find_published)
    
    async def _async_find_published(self) -> List[Job]:
        """Async implementation of find_published"""
        conn = await self._get_connection()
        try:
            rows = await conn.fetch(
                """
                SELECT job_id, title, company, status, published_at,
                       immutable_snapshot, mutable_data, created_at
                FROM jobs
                WHERE status = 'PUBLISHED'
                ORDER BY published_at DESC
                """
            )
            
            results = []
            for row in rows:
                try:
                    job_data = {
                        'job_id': row['job_id'],
                        'title': row['title'],
                        'company': row['company'],
                        'status': JobStatus(row['status']),
                        'published_at': row['published_at'],
                        'created_at': row['created_at'],
                    }
                    
                    if row['mutable_data']:
                        mutable = json.loads(row['mutable_data'])
                        job_data.update(mutable)
                    
                    # CRITICAL: Restore policy from immutable_snapshot
                    if row['immutable_snapshot']:
                        from packages.imh_job.models import JobPolicy
                        policy_dict = json.loads(row['immutable_snapshot'])
                        policy = JobPolicy(**policy_dict)
                        job_data['policy'] = policy
                    
                    results.append(Job(**job_data))
                except Exception as e:
                    logger.warning(f"Failed to parse job {row['job_id']}: {e}")
                    continue
            
            return results
            
        finally:
            await conn.close()
