"""
DB Connection Test and Schema Initialization Script for TASK-026

This script:
1. Tests PostgreSQL connection using .env credentials
2. Initializes database schema (idempotent)
3. Validates schema creation

Usage:
    python scripts/init_db.py
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("init_db")

# Load environment variables
env_path = project_root / ".env"
if not env_path.exists():
    logger.error(f".env file not found at {env_path}")
    sys.exit(1)

load_dotenv(env_path)

# Import after env loaded
import asyncpg  # type: ignore
import asyncio

# Parse connection string
conn_string = os.getenv("POSTGRES_CONNECTION_STRING")
if not conn_string:
    logger.error("POSTGRES_CONNECTION_STRING not found in .env")
    sys.exit(1)

# Parse asyncpg connection string
# Format: postgresql+asyncpg://user:password@host:port/database
# Extract components
import re
pattern = r"postgresql\+asyncpg://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)"
match = re.match(pattern, conn_string)
if not match:
    logger.error(f"Invalid connection string format: {conn_string}")
    sys.exit(1)

user, password, host, port, database = match.groups()

logger.info(f"Connecting to PostgreSQL at {host}:{port}/{database}")

async def test_connection():
    """Test database connection"""
    try:
        conn = await asyncpg.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database
        )
        version = await conn.fetchval('SELECT version()')
        logger.info(f"✓ Connection successful")
        logger.info(f"PostgreSQL version: {version}")
        await conn.close()
        return True
    except Exception as e:
        logger.error(f"✗ Connection failed: {e}")
        return False

async def init_schema():
    """Initialize database schema (idempotent)"""
    conn = await asyncpg.connect(
        host=host,
        port=int(port),
        user=user,
        password=password,
        database=database
    )
    
    try:
        logger.info("Initializing database schema...")
        
        # Create ENUM types if not exist
        await conn.execute("""
            DO $$ BEGIN
                CREATE TYPE job_status AS ENUM ('DRAFT', 'PUBLISHED', 'CLOSED');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        await conn.execute("""
            DO $$ BEGIN
                CREATE TYPE session_status AS ENUM ('APPLIED', 'IN_PROGRESS', 'COMPLETED', 'INTERRUPTED', 'EVALUATED');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        await conn.execute("""
            DO $$ BEGIN
                CREATE TYPE interview_mode AS ENUM ('ACTUAL', 'PRACTICE');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        logger.info("✓ ENUM types created/verified")
        
        # Create jobs table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id VARCHAR(255) PRIMARY KEY,
                title TEXT NOT NULL,
                company TEXT,
                status job_status NOT NULL DEFAULT 'DRAFT',
                published_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                immutable_snapshot JSONB,
                mutable_data JSONB
            );
        """)
        logger.info("✓ jobs table created/verified")
        
        # Create job_policy_snapshots table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS job_policy_snapshots (
                snapshot_id SERIAL PRIMARY KEY,
                job_id VARCHAR(255) NOT NULL REFERENCES jobs(job_id),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                snapshot_data JSONB NOT NULL
            );
        """)
        logger.info("✓ job_policy_snapshots table created/verified")
        
        # Create interviews table (Playbook/ERD 기준: sessions -> interviews)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS interviews (
                session_id VARCHAR(255) PRIMARY KEY,
                user_id VARCHAR(255),
                job_id VARCHAR(255) REFERENCES jobs(job_id),
                status session_status NOT NULL DEFAULT 'APPLIED',
                mode interview_mode NOT NULL DEFAULT 'ACTUAL',
                job_policy_snapshot JSONB,
                session_config_snapshot JSONB,
                questions_history JSONB,
                answers_history JSONB,
                applied_at TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                evaluated_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("\u2713 interviews table created/verified")
        
        # Create evaluation_scores table (Playbook/ERD 기준: reports -> evaluation_scores)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_scores (
                report_id VARCHAR(255) PRIMARY KEY,
                session_id VARCHAR(255) UNIQUE REFERENCES interviews(session_id),
                report_data JSONB NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("\u2713 evaluation_scores table created/verified")
        
        # Create indexes
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_interviews_job_id ON interviews(job_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_interviews_status ON interviews(status);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_interviews_user_id ON interviews(user_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_evaluation_scores_session_id ON evaluation_scores(session_id);")
        
        logger.info("✓ Indexes created/verified")
        
        logger.info("✓ Schema initialization complete")
        
    finally:
        await conn.close()

async def verify_schema():
    """
    Verify schema was created correctly.
    Fail-Fast: 테이블 존재뿐 아니라 필수 컬럼 존재까지 검증한다.
    테이블이 존재하더라도 컬럼이 기대와 다르면 즉시 FAIL을 반환한다.
    """
    conn = await asyncpg.connect(
        host=host,
        port=int(port),
        user=user,
        password=password,
        database=database
    )
    
    try:
        # 1. 테이블 존재 확인
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('jobs', 'job_policy_snapshots', 'interviews', 'evaluation_scores')
            ORDER BY table_name;
        """)
        
        table_names = [row['table_name'] for row in tables]
        logger.info(f"Tables found: {table_names}")
        
        expected = ['evaluation_scores', 'job_policy_snapshots', 'jobs', 'interviews']
        if set(table_names) != set(expected):
            logger.error(f"✗ Missing tables: {set(expected) - set(table_names)}")
            return False
        logger.info("✓ All required tables exist")

        # 2. Fail-Fast: 필수 컬럼 존재 검증
        REQUIRED_COLUMNS = {
            'interviews': {'session_id', 'user_id', 'job_id', 'status', 'mode', 'created_at', 'updated_at'},
            'evaluation_scores': {'report_id', 'session_id', 'report_data', 'created_at'},
        }
        for tbl, required_cols in REQUIRED_COLUMNS.items():
            col_rows = await conn.fetch("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema='public' AND table_name=$1
            """, tbl)
            actual_cols = {r['column_name'] for r in col_rows}
            missing = required_cols - actual_cols
            if missing:
                logger.error(f"✗ Fail-Fast: [{tbl}] 필수 컬럼 누락 - {missing}")
                logger.error("  init_db.py를 재실행하거나 DB 스키마를 수동 확인하십시오.")
                return False
            logger.info(f"✓ [{tbl}] 필수 컬럼 확인 완료")

        logger.info("✓ Schema verification complete (tables + columns)")
        return True
            
    finally:
        await conn.close()


async def main():
    logger.info("=== PostgreSQL Schema Initialization ===")
    
    # Test connection
    if not await test_connection():
        sys.exit(1)
    
    # Initialize schema
    await init_schema()
    
    # Verify schema
    if await verify_schema():
        logger.info("=== Success ===")
        return 0
    else:
        logger.error("=== Verification failed ===")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
