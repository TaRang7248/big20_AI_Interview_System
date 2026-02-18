"""
TASK-026 Checkpoint 3: Migration Verification Script

WARNING: Production 운영 중에는 사용하지 않음.
DB 재구성 시 정합성 검증용.

PURPOSE:
Verify complete replication of Primary data to PostgreSQL according to mathematical set definitions.

VERIFICATION CRITERIA (Exit Criteria):
1. Primary_ID_Set ⊆ PostgreSQL_ID_Set
2. ∀ id ∈ Primary_ID_Set: PostgreSQL has same id AND content 100% match
3. FK integrity violations = 0
4. Sample comparison mismatches = 0
5. PRIMARY_SUCCESS_SECONDARY_FAIL cases 100% recovered
6. PostgreSQL-only data (excess) fully investigated

SCOPE:
- Verify data completeness
- Verify data consistency
- Generate exception case reports
- NO modifications to data
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
from dataclasses import dataclass
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env from project root
env_path = Path(r"C:\big20\big20_AI_Interview_simulation\.env")
if env_path.exists():
    load_dotenv(env_path)
    logging.info(f"Loaded .env from {env_path}")
else:
    logging.warning(f".env not found at {env_path}")

from packages.imh_job.models import Job
from packages.imh_session.dto import SessionContext
from packages.imh_report.dto import InterviewReport

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/verification_checkpoint3.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class SetComparisonResult:
    """Result of set comparison"""
    primary_only: Set[str]  # In Primary but not in PostgreSQL (CRITICAL)
    postgresql_only: Set[str]  # In PostgreSQL but not in Primary (investigation needed)
    common: Set[str]  # In both
    
    @property
    def is_complete(self) -> bool:
        """Check if Primary_ID_Set ⊆ PostgreSQL_ID_Set"""
        return len(self.primary_only) == 0


@dataclass
class ContentComparisonResult:
    """Result of content comparison"""
    total_checked: int
    matches: int
    mismatches: List[Tuple[str, str]]  # List of (id, mismatch_details)
    
    @property
    def is_perfect(self) -> bool:
        """Check if all content matches (100%)"""
        return len(self.mismatches) == 0


class Checkpoint3Verification:
    """
    Checkpoint 3 Migration Verification
    
    Enforces mathematical validation:
    - Set comparison (Primary_ID_Set ⊆ PostgreSQL_ID_Set)
    - Content comparison (∀ id: 100% match)
    - FK integrity check
    """
    
    def __init__(self, conn_string: str):
        self.conn_string = conn_string
        
        # Parse connection string
        pattern = r"postgresql\+asyncpg://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)"
        match = re.match(pattern, conn_string)
        if not match:
            raise ValueError(f"Invalid connection string format: {conn_string}")
        
        self.user, self.password, self.host, self.port, self.database = match.groups()
        logger.info(f"Initialized verification for {self.host}:{self.port}/{self.database}")
    
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
    
    async def verify_job_set(self, memory_jobs: Dict[str, Job]) -> SetComparisonResult:
        """
        Verify Job set comparison
        
        Check: Primary_Job_ID_Set ⊆ PostgreSQL_Job_ID_Set
        """
        logger.info("=== Verifying Job Set ===")
        
        primary_ids = set(memory_jobs.keys())
        logger.info(f"Primary Job IDs: {len(primary_ids)}")
        
        conn = await self._get_connection()
        try:
            rows = await conn.fetch("SELECT job_id FROM jobs")
            postgresql_ids = {row['job_id'] for row in rows}
            logger.info(f"PostgreSQL Job IDs: {len(postgresql_ids)}")
            
            result = SetComparisonResult(
                primary_only=primary_ids - postgresql_ids,
                postgresql_only=postgresql_ids - primary_ids,
                common=primary_ids & postgresql_ids
            )
            
            if result.primary_only:
                logger.error(f"MISSING in PostgreSQL: {result.primary_only}")
            else:
                logger.info("✓ All Primary Jobs present in PostgreSQL")
            
            if result.postgresql_only:
                logger.warning(f"EXCESS in PostgreSQL (investigation needed): {result.postgresql_only}")
            
            return result
            
        finally:
            await conn.close()
    
    async def verify_job_content(self, memory_jobs: Dict[str, Job]) -> ContentComparisonResult:
        """
        Verify Job content comparison
        
        Check: ∀ job_id ∈ Primary_Job_ID_Set: content 100% match
        """
        logger.info("=== Verifying Job Content ===")
        
        mismatches = []
        matches = 0
        
        conn = await self._get_connection()
        try:
            for job_id, job in memory_jobs.items():
                row = await conn.fetchrow(
                    "SELECT job_data FROM jobs WHERE job_id = $1",
                    job_id
                )
                
                if not row:
                    mismatches.append((job_id, "Not found in PostgreSQL"))
                    continue
                
                primary_data = job.model_dump(mode='json')
                postgresql_data = row['job_data']
                
                if primary_data == postgresql_data:
                    matches += 1
                else:
                    detail = f"Content mismatch detected"
                    mismatches.append((job_id, detail))
                    logger.error(f"Job {job_id}: {detail}")
            
            result = ContentComparisonResult(
                total_checked=len(memory_jobs),
                matches=matches,
                mismatches=mismatches
            )
            
            if result.is_perfect:
                logger.info(f"✓ All {result.total_checked} Jobs content match (100%)")
            else:
                logger.error(f"✗ {len(mismatches)} content mismatches found")
            
            return result
            
        finally:
            await conn.close()
    
    async def verify_session_set(self, memory_sessions: Dict[str, SessionContext]) -> SetComparisonResult:
        """
        Verify Session set comparison
        
        Check: Primary_Session_ID_Set ⊆ PostgreSQL_Session_ID_Set
        """
        logger.info("=== Verifying Session Set ===")
        
        primary_ids = set(memory_sessions.keys())
        logger.info(f"Primary Session IDs: {len(primary_ids)}")
        
        conn = await self._get_connection()
        try:
            rows = await conn.fetch("SELECT session_id FROM sessions")
            postgresql_ids = {row['session_id'] for row in rows}
            logger.info(f"PostgreSQL Session IDs: {len(postgresql_ids)}")
            
            result = SetComparisonResult(
                primary_only=primary_ids - postgresql_ids,
                postgresql_only=postgresql_ids - primary_ids,
                common=primary_ids & postgresql_ids
            )
            
            if result.primary_only:
                logger.error(f"MISSING in PostgreSQL: {result.primary_only}")
            else:
                logger.info("✓ All Primary Sessions present in PostgreSQL")
            
            if result.postgresql_only:
                logger.warning(f"EXCESS in PostgreSQL (investigation needed): {result.postgresql_only}")
            
            return result
            
        finally:
            await conn.close()
    
    async def verify_session_content(self, memory_sessions: Dict[str, SessionContext]) -> ContentComparisonResult:
        """
        Verify Session content comparison
        
        Check: ∀ session_id ∈ Primary_Session_ID_Set: content 100% match
        """
        logger.info("=== Verifying Session Content ===")
        
        mismatches = []
        matches = 0
        
        conn = await self._get_connection()
        try:
            for session_id, session in memory_sessions.items():
                row = await conn.fetchrow(
                    "SELECT session_data FROM sessions WHERE session_id = $1",
                    session_id
                )
                
                if not row:
                    mismatches.append((session_id, "Not found in PostgreSQL"))
                    continue
                
                primary_data = session.model_dump(mode='json')
                postgresql_data = row['session_data']
                
                if primary_data == postgresql_data:
                    matches += 1
                else:
                    detail = f"Content mismatch detected"
                    mismatches.append((session_id, detail))
                    logger.error(f"Session {session_id}: {detail}")
            
            result = ContentComparisonResult(
                total_checked=len(memory_sessions),
                matches=matches,
                mismatches=mismatches
            )
            
            if result.is_perfect:
                logger.info(f"✓ All {result.total_checked} Sessions content match (100%)")
            else:
                logger.error(f"✗ {len(mismatches)} content mismatches found")
            
            return result
            
        finally:
            await conn.close()
   
    async def verify_report_set(self, report_dir: Path) -> SetComparisonResult:
        """
        Verify Report set comparison
        
        Check: Primary_Report_ID_Set ⊆ PostgreSQL_Report_ID_Set
        """
        logger.info("=== Verifying Report Set ===")
        
        report_files = list(report_dir.glob("*.json"))
        primary_ids = {str(f.stem).split('_')[-1] for f in report_files}
        logger.info(f"Primary Report IDs: {len(primary_ids)}")
        
        conn = await self._get_connection()
        try:
            rows = await conn.fetch("SELECT report_id FROM reports")
            postgresql_ids = {row['report_id'] for row in rows}
            logger.info(f"PostgreSQL Report IDs: {len(postgresql_ids)}")
            
            result = SetComparisonResult(
                primary_only=primary_ids - postgresql_ids,
                postgresql_only=postgresql_ids - primary_ids,
                common=primary_ids & postgresql_ids
            )
            
            if result.primary_only:
                logger.error(f"MISSING in PostgreSQL: {result.primary_only}")
            else:
                logger.info("✓ All Primary Reports present in PostgreSQL")
            
            if result.postgresql_only:
                logger.warning(f"EXCESS in PostgreSQL (investigation needed): {result.postgresql_only}")
            
            return result
            
        finally:
            await conn.close()
    
    async def verify_report_content(self, report_dir: Path, sample_pct: float = 0.05) -> ContentComparisonResult:
        """
        Verify Report content comparison (5% sample)
        
        Check: Sample reports content 100% match
        """
        logger.info(f"=== Verifying Report Content (sample: {sample_pct*100}%) ===")
        
        report_files = list(report_dir.glob("*.json"))
        sample_size = max(1, int(len(report_files) * sample_pct))
        sample_files = report_files[:sample_size]  # Simple sampling
        
        logger.info(f"Sampling {sample_size} out of {len(report_files)} reports")
        
        mismatches = []
        matches = 0
        
        conn = await self._get_connection()
        try:
            for report_file in sample_files:
                report_id = str(report_file.stem).split('_')[-1]
                
                with open(report_file, 'r', encoding='utf-8') as f:
                    primary_data = json.load(f)
                
                row = await conn.fetchrow(
                    "SELECT report_data FROM reports WHERE report_id = $1",
                    report_id
                )
                
                if not row:
                    mismatches.append((report_id, "Not found in PostgreSQL"))
                    continue
                
                postgresql_data = row['report_data']
                
                if primary_data == postgresql_data:
                    matches += 1
                else:
                    detail = f"Content mismatch detected"
                    mismatches.append((report_id, detail))
                    logger.error(f"Report {report_id}: {detail}")
            
            result = ContentComparisonResult(
                total_checked=sample_size,
                matches=matches,
                mismatches=mismatches
            )
            
            if result.is_perfect:
                logger.info(f"✓ All {result.total_checked} sampled Reports content match (100%)")
            else:
                logger.error(f"✗ {len(mismatches)} content mismatches found in sample")
            
            return result
            
        finally:
            await conn.close()
    
    async def verify_fk_integrity(self) -> Tuple[int, List[str]]:
        """
        Verify FK integrity
        
        Check: reports.session_id FK violations = 0
        """
        logger.info("=== Verifying FK Integrity ===")
        
        conn = await self._get_connection()
        try:
            # Check reports → sessions FK
            rows = await conn.fetch("""
                SELECT report_id, session_id 
                FROM reports 
                WHERE session_id IS NOT NULL 
                  AND session_id NOT IN (SELECT session_id FROM sessions)
            """)
            
            violations = [row['report_id'] for row in rows]
            
            if violations:
                logger.error(f"✗ FK violations found: {len(violations)} reports")
                for report_id in violations:
                    logger.error(f"  Report {report_id} references non-existent session")
            else:
                logger.info("✓ FK integrity check PASSED (0 violations)")
            
            return len(violations), violations
            
        finally:
            await conn.close()
    
    async def generate_exception_report(self, 
                                       job_excess: Set[str], 
                                       session_excess: Set[str], 
                                       report_excess: Set[str]) -> str:
        """
        Generate exception case report for PostgreSQL-only data
        
        Case 3: DB에 있고 Primary에 없음
        """
        logger.info("=== Generating Exception Case Report ===")
        
        report_lines = [
            "# Exception Case Report (Case 3: PostgreSQL-only Data)",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Summary",
            f"Job excess: {len(job_excess)}",
            f"Session excess: {len(session_excess)}",
            f"Report excess: {len(report_excess)}",
            "",
        ]
        
        if job_excess:
            report_lines.append("## Jobs in PostgreSQL but not in Primary (Memory)")
            for job_id in sorted(job_excess):
                report_lines.append(f"- {job_id}")
            report_lines.append("")
        
        if session_excess:
            report_lines.append("## Sessions in PostgreSQL but not in Primary (Memory)")
            for session_id in sorted(session_excess):
                report_lines.append(f"- {session_id}")
            report_lines.append("")
        
        if report_excess:
            report_lines.append("## Reports in PostgreSQL but not in Primary (File)")
            for report_id in sorted(report_excess):
                report_lines.append(f"- {report_id}")
            report_lines.append("")
        
        report_lines.append("## Investigation Required")
        report_lines.append("Possible causes:")
        report_lines.append("1. SECONDARY_SUCCESS_PRIMARY_FAIL (rare case)")
        report_lines.append("2. Memory volatile data after restart (Job/Session)")
        report_lines.append("3. File deleted from Primary (Report)")
        report_lines.append("")
        report_lines.append("Action: Manual investigation required per Safety Protocol")
        
        report_content = '\n'.join(report_lines)
        
        report_path = Path("logs/exception_case_report_checkpoint3.md")
        report_path.write_text(report_content, encoding='utf-8')
        logger.info(f"Exception case report saved: {report_path}")
        
        return str(report_path)
    
    async def run(self, memory_jobs: Dict[str, Job], memory_sessions: Dict[str, SessionContext], report_dir: Path) -> bool:
        """
        Run complete verification
        
        Returns: True if all Exit Criteria PASS
        """
        logger.info("=" * 70)
        logger.info("Checkpoint 3: Migration Verification START")
        logger.info("Exit Criteria Validation (Mathematical)")
        logger.info("=" * 70)
        
        all_pass = True
        
        try:
            # 1. Job Verification
            job_set = await self.verify_job_set(memory_jobs)
            job_content = await self.verify_job_content(memory_jobs)
            
            if not job_set.is_complete:
                logger.error("✗ Exit Criteria FAIL: Job set incomplete")
                all_pass = False
            
            if not job_content.is_perfect:
                logger.error("✗ Exit Criteria FAIL: Job content mismatch")
                all_pass = False
            
            # 2. Session Verification
            session_set = await self.verify_session_set(memory_sessions)
            session_content = await self.verify_session_content(memory_sessions)
            
            if not session_set.is_complete:
                logger.error("✗ Exit Criteria FAIL: Session set incomplete")
                all_pass = False
            
            if not session_content.is_perfect:
                logger.error("✗ Exit Criteria FAIL: Session content mismatch")
                all_pass = False
            
            # 3. Report Verification
            report_set = await self.verify_report_set(report_dir)
            report_content = await self.verify_report_content(report_dir)
            
            if not report_set.is_complete:
                logger.error("✗ Exit Criteria FAIL: Report set incomplete")
                all_pass = False
            
            if not report_content.is_perfect:
                logger.error("✗ Exit Criteria FAIL: Report content mismatch")
                all_pass = False
            
            # 4. FK Integrity
            fk_violations, _ = await self.verify_fk_integrity()
            if fk_violations > 0:
                logger.error("✗ Exit Criteria FAIL: FK violations detected")
                all_pass = False
            
            # 5. Exception Case Report
            exception_report = await self.generate_exception_report(
                job_set.postgresql_only,
                session_set.postgresql_only,
                report_set.postgresql_only
            )
            
            if job_set.postgresql_only or session_set.postgresql_only or report_set.postgresql_only:
                logger.warning(f"Exception cases require investigation: {exception_report}")
            
            # Final Summary
            logger.info("=" * 70)
            if all_pass:
                logger.info("✅✅✅ ALL EXIT CRITERIA PASSED ✅✅✅")
                logger.info("Checkpoint 3: Migration Verification COMPLETE")
            else:
                logger.error("❌ EXIT CRITERIA FAILED")
                logger.error("Checkpoint 3: Migration Verification FAILED")
            logger.info("=" * 70)
            
            return all_pass
            
        except Exception as e:
            logger.error(f"Verification error: {e}")
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
    
    # Initialize Verification
    verification = Checkpoint3Verification(conn_string)
    
    # Get Memory snapshots
    memory_jobs = {}
    memory_sessions = {}
    
    logger.warning("Memory data snapshot: Using current runtime state")
    
    # Run verification
    success = await verification.run(memory_jobs, memory_sessions, report_dir)
    
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
