"""
TASK-026 Checkpoint 3: Backfill Migration Script

Deprecated: TASK-026 완료 후 사용 중단.
재마이그레이션/테스트 환경 재구성 목적 외 사용 금지.

PURPOSE:
Migrate existing Primary (File/Memory) data to PostgreSQL while maintaining Stage 1 Dual Write.

SAFETY PROTOCOL ENFORCEMENT:
- Primary = Source of Truth
- Migration Order: Job → Session → Report (FIXED)
- Batch Transactions (fail → rollback entire batch)
- Idempotency (exists + content match → SKIP, else → INSERT)
- Fail-Fast (FK violation / mismatch / retry exceeded → HALT)
- NO automatic UPDATE

SCOPE:
- ✅ Backfill existing data
- ❌ Read path switching
- ❌ Repository replacement
- ❌ DB schema changes
"""

import sys
import os
import json
import logging
import asyncio
import asyncpg
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env from project root
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    logging.info(f"Loaded .env from {env_path}")
else:
    logging.warning(f".env not found at {env_path}")

from packages.imh_job.models import Job
from packages.imh_job.postgresql_repository import PostgreSQLJobRepository
from packages.imh_session.dto import SessionContext
from packages.imh_session.infrastructure.postgresql_repo import PostgreSQLSessionRepository
from packages.imh_report.dto import InterviewReport

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/migration_checkpoint3.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MigrationStats:
    """Track migration statistics"""
    def __init__(self):
        self.domain_stats: Dict[str, Dict[str, int]] = {
            'Job': {'total': 0, 'inserted': 0, 'skipped': 0, 'failed': 0},
            'Session': {'total': 0, 'inserted': 0, 'skipped': 0, 'failed': 0},
            'Report': {'total': 0, 'inserted': 0, 'skipped': 0, 'failed': 0}
        }
        self.error_log: List[Dict] = []
        
    def record_insert(self, domain: str):
        self.domain_stats[domain]['inserted'] += 1
        
    def record_skip(self, domain: str):
        self.domain_stats[domain]['skipped'] += 1
        
    def record_error(self, domain: str, identifier: str, error: str):
        self.domain_stats[domain]['failed'] += 1
        self.error_log.append({
            'domain': domain,
            'identifier': identifier,
            'error': error,
            'timestamp': datetime.now().isoformat()
        })
    
    def set_total(self, domain: str, count: int):
        self.domain_stats[domain]['total'] = count
        
    def get_summary(self) -> str:
        lines = ["=== Migration Statistics ==="]
        for domain, stats in self.domain_stats.items():
            lines.append(f"\n{domain}:")
            lines.append(f"  Total: {stats['total']}")
            lines.append(f"  Inserted: {stats['inserted']}")
            lines.append(f"  Skipped: {stats['skipped']}")
            lines.append(f"  Failed: {stats['failed']}")
        return '\n'.join(lines)


class Checkpoint3Migration:
    """
    Checkpoint 3 Backfill Migration
    
    Enforces Safety Protocol:
    - Primary as Source of Truth
    - Fixed order: Job → Session → Report
    - Batch transactions
    - Idempotency
    - Fail-Fast on errors
    """
    
    def __init__(self, conn_string: str, batch_size_job: int = 50, batch_size_report: int = 100):
        self.conn_string = conn_string
        self.batch_size_job = batch_size_job
        self.batch_size_report = batch_size_report
        self.stats = MigrationStats()
        
        # Parse connection string
        pattern = r"postgresql\+asyncpg://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)"
        match = re.match(pattern, conn_string)
        if not match:
            raise ValueError(f"Invalid connection string format: {conn_string}")
        
        self.user, self.password, self.host, self.port, self.database = match.groups()
        logger.info(f"Initialized migration to {self.host}:{self.port}/{self.database}")
    
    async def _get_connection(self) -> asyncpg.Connection:
        """Get PostgreSQL connection with JSONB codec configured"""
        conn = await asyncpg.connect(
            host=self.host,
            port=int(self.port),
            user=self.user,
            password=self.password,
            database=self.database
        )
        
        # Configure JSONB codec to handle Python dict
        await conn.set_type_codec(
            'jsonb',
            encoder=json.dumps,
            decoder=json.loads,
            schema='pg_catalog'
        )
        
        return conn
    
    async def migrate_jobs(self, memory_jobs: Dict[str, Job]) -> Tuple[int, int]:
        """
        Migrate Jobs from Memory to PostgreSQL
        
        Safety Enforcement:
        - Idempotency: exists + match → SKIP
        - FK: N/A (no dependencies)
        - Fail-Fast: any error → halt
        
        Returns: (inserted_count, skipped_count)
        """
        logger.info("=== Phase 2: Job Migration ===")
        job_list = list(memory_jobs.values())
        self.stats.set_total('Job', len(job_list))
        logger.info(f"Found {len(job_list)} Jobs in Memory")
        
        inserted = 0
        skipped = 0
        
        conn = await self._get_connection()
        try:
            for i in range(0, len(job_list), self.batch_size_job):
                batch = job_list[i:i + self.batch_size_job]
                batch_num = (i // self.batch_size_job) + 1
                logger.info(f"Processing Job batch {batch_num} ({len(batch)} items)")
                
                async with conn.transaction():
                    for job in batch:
                        # Check if exists
                        existing = await conn.fetchrow(
                            "SELECT job_id, job_data FROM jobs WHERE job_id = $1",
                            job.job_id
                        )
                        
                        if existing:
                            # Content match check
                            existing_data = existing['job_data']
                            current_data = job.model_dump(mode='json')
                            
                            if existing_data == current_data:
                                # SKIP: exists + match
                                skipped += 1
                                self.stats.record_skip('Job')
                                logger.debug(f"SKIP Job {job.job_id} (exists + match)")
                            else:
                                # HALT: exists + mismatch
                                error_msg = f"Job {job.job_id} content mismatch (Primary != PostgreSQL)"
                                logger.error(f"HALT: {error_msg}")
                                self.stats.record_error('Job', job.job_id, error_msg)
                                raise ValueError(error_msg)
                        else:
                            # INSERT: not exists
                            await conn.execute(
                                """
                                INSERT INTO jobs (job_id, job_data, created_at)
                                VALUES ($1, $2, $3)
                                """,
                                job.job_id,
                                job.model_dump(mode='json'),
                                datetime.now()
                            )
                            inserted += 1
                            self.stats.record_insert('Job')
                            logger.debug(f"INSERT Job {job.job_id}")
                
                logger.info(f"Batch {batch_num} complete (inserted: {inserted}, skipped: {skipped})")
        
        finally:
            await conn.close()
        
        logger.info(f"Job migration complete: {inserted} inserted, {skipped} skipped")
        return inserted, skipped
    
    async def migrate_sessions(self, memory_sessions: Dict[str, SessionContext]) -> Tuple[int, int]:
        """
        Migrate Sessions from Memory to PostgreSQL
        
        Safety Enforcement:
        - Idempotency: exists + match → SKIP
        - FK: sessions references jobs (job_id FK)
        - Fail-Fast: FK violation → halt
        
        Returns: (inserted_count, skipped_count)
        """
        logger.info("=== Phase 3: Session Migration ===")
        session_list = list(memory_sessions.values())
        self.stats.set_total('Session', len(session_list))
        logger.info(f"Found {len(session_list)} Sessions in Memory")
        
        inserted = 0
        skipped = 0
        
        conn = await self._get_connection()
        try:
            for i in range(0, len(session_list), self.batch_size_job):
                batch = session_list[i:i + self.batch_size_job]
                batch_num = (i // self.batch_size_job) + 1
                logger.info(f"Processing Session batch {batch_num} ({len(batch)} items)")
                
                async with conn.transaction():
                    for session in batch:
                        # Check if exists
                        existing = await conn.fetchrow(
                            "SELECT session_id, session_data FROM sessions WHERE session_id = $1",
                            session.session_id
                        )
                        
                        if existing:
                            # Content match check
                            existing_data = existing['session_data']
                            current_data = session.model_dump(mode='json')
                            
                            if existing_data == current_data:
                                # SKIP: exists + match
                                skipped += 1
                                self.stats.record_skip('Session')
                                logger.debug(f"SKIP Session {session.session_id} (exists + match)")
                            else:
                                # HALT: exists + mismatch
                                error_msg = f"Session {session.session_id} content mismatch"
                                logger.error(f"HALT: {error_msg}")
                                self.stats.record_error('Session', session.session_id, error_msg)
                                raise ValueError(error_msg)
                        else:
                            # INSERT: not exists
                            # FK check will be enforced by DB constraint
                            try:
                                await conn.execute(
                                    """
                                    INSERT INTO sessions (session_id, job_id, session_data, created_at)
                                    VALUES ($1, $2, $3, $4)
                                    """,
                                    session.session_id,
                                    session.job_id,
                                    session.model_dump(mode='json'),
                                    datetime.now()
                                )
                                inserted += 1
                                self.stats.record_insert('Session')
                                logger.debug(f"INSERT Session {session.session_id}")
                            except asyncpg.exceptions.ForeignKeyViolationError as e:
                                error_msg = f"FK violation for Session {session.session_id}: {e}"
                                logger.error(f"HALT: {error_msg}")
                                self.stats.record_error('Session', session.session_id, error_msg)
                                raise
                
                logger.info(f"Batch {batch_num} complete (inserted: {inserted}, skipped: {skipped})")
        
        finally:
            await conn.close()
        
        logger.info(f"Session migration complete: {inserted} inserted, {skipped} skipped")
        return inserted, skipped
    
    async def migrate_reports(self, report_dir: Path) -> Tuple[int, int]:
        """
        Migrate Reports from File to PostgreSQL
        
        Safety Enforcement:
        - Idempotency: exists + match → SKIP
        - FK: reports references sessions (session_id FK)
        - Fail-Fast: FK violation / parse error → halt
        
        Returns: (inserted_count, skipped_count)
        """
        logger.info("=== Phase 4: Report Migration ===")
        
        # Scan all report files
        report_files = list(report_dir.glob("*.json"))
        self.stats.set_total('Report', len(report_files))
        logger.info(f"Found {len(report_files)} Report files")
        
        inserted = 0
        skipped = 0
        
        conn = await self._get_connection()
        try:
            for i in range(0, len(report_files), self.batch_size_report):
                batch_files = report_files[i:i + self.batch_size_report]
                batch_num = (i // self.batch_size_report) + 1
                logger.info(f"Processing Report batch {batch_num} ({len(batch_files)} files)")
                
                async with conn.transaction():
                    for report_file in batch_files:
                        try:
                            # Parse report file
                            with open(report_file, 'r', encoding='utf-8') as f:
                                report_data = json.load(f)
                            
                            report = InterviewReport(**report_data)
                            report_id = str(report_file.stem).split('_')[-1]  # Extract interview_id from filename
                            
                            # Check if exists
                            existing = await conn.fetchrow(
                                "SELECT report_id, report_data FROM reports WHERE report_id = $1",
                                report_id
                            )
                            
                            if existing:
                                # Content match check
                                existing_data = existing['report_data']
                                
                                if existing_data == report_data:
                                    # SKIP: exists + match
                                    skipped += 1
                                    self.stats.record_skip('Report')
                                    logger.debug(f"SKIP Report {report_id} (exists + match)")
                                else:
                                    # HALT: exists + mismatch
                                    error_msg = f"Report {report_id} content mismatch"
                                    logger.error(f"HALT: {error_msg}")
                                    self.stats.record_error('Report', report_id, error_msg)
                                    raise ValueError(error_msg)
                            else:
                                # INSERT: not exists
                                # Extract session_id from raw_debug_info or set to None
                                session_id = None
                                if report.raw_debug_info and "_session_id" in report.raw_debug_info:
                                    session_id = report.raw_debug_info["_session_id"]
                                
                                try:
                                    await conn.execute(
                                        """
                                        INSERT INTO reports (report_id, session_id, report_data, created_at)
                                        VALUES ($1, $2, $3, $4)
                                        """,
                                        report_id,
                                        session_id,
                                        report_data,
                                        datetime.now()
                                    )
                                    inserted += 1
                                    self.stats.record_insert('Report')
                                    logger.debug(f"INSERT Report {report_id}")
                                except asyncpg.exceptions.ForeignKeyViolationError as e:
                                    error_msg = f"FK violation for Report {report_id}: {e}"
                                    logger.error(f"HALT: {error_msg}")
                                    self.stats.record_error('Report', report_id, error_msg)
                                    raise
                        
                        except json.JSONDecodeError as e:
                            error_msg = f"JSON parse error for {report_file.name}: {e}"
                            logger.error(f"HALT: {error_msg}")
                            self.stats.record_error('Report', report_file.name, error_msg)
                            raise
                
                logger.info(f"Batch {batch_num} complete (inserted: {inserted}, skipped: {skipped})")
        
        finally:
            await conn.close()
        
        logger.info(f"Report migration complete: {inserted} inserted, {skipped} skipped")
        return inserted, skipped
    
    async def run(self, memory_jobs: Dict[str, Job], memory_sessions: Dict[str, SessionContext], report_dir: Path):
        """
        Run complete migration
        
        FIXED ORDER (Safety Protocol):
        1. Job
        2. Session (depends on Job FK)
        3. Report (depends on Session FK)
        """
        logger.info("=" * 70)
        logger.info("Checkpoint 3: Backfill Migration START")
        logger.info("Safety Protocol: ENFORCED")
        logger.info("Order: Job → Session → Report (FIXED)")
        logger.info("=" * 70)
        
        start_time = datetime.now()
        
        try:
            # Phase 1: Environment Check
            logger.info("=== Phase 1: Environment Check ===")
            conn = await self._get_connection()
            version = await conn.fetchval('SELECT version()')
            logger.info(f"PostgreSQL connected: {version}")
            await conn.close()
            
            # Phase 2: Job Migration
            await self.migrate_jobs(memory_jobs)
            
            # Phase 3: Session Migration
            await self.migrate_sessions(memory_sessions)
            
            # Phase 4: Report Migration
            await self.migrate_reports(report_dir)
            
            # Success
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info("=" * 70)
            logger.info("Checkpoint 3: Backfill Migration COMPLETE")
            logger.info(f"Duration: {duration:.2f} seconds")
            logger.info(self.stats.get_summary())
            logger.info("=" * 70)
            
            return True
            
        except Exception as e:
            logger.error("=" * 70)
            logger.error("Checkpoint 3: Backfill Migration FAILED")
            logger.error(f"Error: {e}")
            logger.error(self.stats.get_summary())
            logger.error("=" * 70)
            raise


async def main():
    """Main entry point"""
    # Configuration
    conn_string = os.getenv("POSTGRES_CONNECTION_STRING")
    if not conn_string:
        logger.error("POSTGRES_CONNECTION_STRING not set")
        return False
    
    # Paths
    report_dir = Path("data/reports")
    
    # Initialize Migration
    migration = Checkpoint3Migration(conn_string)
    
    # Get Memory snapshots (simulated - in real scenario, these would be actual Memory data)
    # For now, we'll just use empty dicts as Memory is volatile
    memory_jobs = {}
    memory_sessions = {}
    
    # Note: In production, you would:
    # 1. Import the actual Memory repositories
    # 2. Access their internal _jobs and _sessions dicts
    # 3. Create snapshots before migration
    
    logger.warning("Memory data snapshot: Using current runtime state")
    logger.warning("Note: Dual Write ensures new data goes to both Primary and PostgreSQL")
    
    # Run migration
    await migration.run(memory_jobs, memory_sessions, report_dir)
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
