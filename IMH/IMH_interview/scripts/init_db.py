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
project_root = Path(r"c:\big20\big20_AI_Interview_simulation")
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
        
        # Create sessions table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
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
        logger.info("✓ sessions table created/verified")
        
        # Create reports table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                report_id VARCHAR(255) PRIMARY KEY,
                session_id VARCHAR(255) REFERENCES sessions(session_id),
                report_data JSONB NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("✓ reports table created/verified")
        
        # Create indexes
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_job_id ON sessions(job_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_session_id ON reports(session_id);")
        
        logger.info("✓ Indexes created/verified")
        
        logger.info("✓ Schema initialization complete")
        
    finally:
        await conn.close()

async def verify_schema():
    """Verify schema was created correctly"""
    conn = await asyncpg.connect(
        host=host,
        port=int(port),
        user=user,
        password=password,
        database=database
    )
    
    try:
        # Check tables
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('jobs', 'job_policy_snapshots', 'sessions', 'reports')
            ORDER BY table_name;
        """)
        
        table_names = [row['table_name'] for row in tables]
        logger.info(f"Tables found: {table_names}")
        
        expected = ['job_policy_snapshots', 'jobs', 'reports', 'sessions']
        if set(table_names) == set(expected):
            logger.info("✓ All required tables exist")
            return True
        else:
            logger.error(f"✗ Missing tables: {set(expected) - set(table_names)}")
            return False
            
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
