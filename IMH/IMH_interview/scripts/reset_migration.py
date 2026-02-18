"""
Checkpoint 3 Migration Recovery Script

WARNING: TEST ENV ONLY.
This script deletes all data.

PURPOSE: Clean PostgreSQL and re-run migration safely

SITUATION:
- 4 Reports inserted successfully
- 1 Report content mismatch detected → HALTED (Fail-Fast)
- Need to clear PostgreSQL and retry

RECOVERY STRATEGY:
1. DELETE all data from PostgreSQL (reports, sessions, jobs)
2. Re-run migration from scratch
3. Verify 100% success
"""

import asyncio
import asyncpg
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(r"C:\big20\big20_AI_Interview_simulation\.env")
load_dotenv(env_path)

if os.getenv("ENV") != "TEST":
    print("CRITICAL ERROR: This script can only be run when ENV=TEST.")
    sys.exit(1)

async def clear_and_reset():
    """Clear all migrated data from PostgreSQL"""
    conn_str = os.getenv("POSTGRES_CONNECTION_STRING").replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(conn_str)
    
    try:
        print("=== Clearing PostgreSQL for Fresh Migration ===")
        
        # Delete in reverse FK dependency order
        await conn.execute("DELETE FROM reports")
        reports_count = await conn.fetchval("SELECT COUNT(*) FROM reports")
        print(f"✓ Reports cleared (remaining: {reports_count})")
        
        await conn.execute("DELETE FROM sessions")
        sessions_count = await conn.fetchval("SELECT COUNT(*) FROM sessions")
        print(f"✓ Sessions cleared (remaining: {sessions_count})")
        
        await conn.execute("DELETE FROM jobs")
        jobs_count = await conn.fetchval("SELECT COUNT(*) FROM jobs")
        print(f"✓ Jobs cleared (remaining: {jobs_count})")
        
        print("\n=== PostgreSQL Reset Complete ===")
        print("Ready for fresh migration run")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(clear_and_reset())
