"""
Type Verification Script

Verify that JSONB columns return Python dict (not str)
"""

import asyncio
import asyncpg
import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(r"C:\big20\big20_AI_Interview_simulation\.env")
load_dotenv(env_path)

async def verify_types():
    """Verify that *_data columns return dict type"""
    
    conn_str = os.getenv("POSTGRES_CONNECTION_STRING").replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(conn_str)
    
    # Configure JSONB codec
    await conn.set_type_codec(
        'jsonb',
        encoder=json.dumps,
        decoder=json.loads,
        schema='pg_catalog'
    )
    
    try:
        print("=" * 70)
        print("JSONB Type Verification")
        print("=" * 70)
        
        # Check Reports
        print("\n[Reports]")
        report = await conn.fetchrow("SELECT report_id, report_data FROM reports LIMIT 1")
        if report:
            print(f"  report_id: {report['report_id']}")
            print(f"  type(report_data): {type(report['report_data'])}")
            print(f"  Is dict: {isinstance(report['report_data'], dict)}")
            if isinstance(report['report_data'], dict):
                print(f"  ✓ PASSED: Returns Python dict")
                print(f"  Sample keys: {list(report['report_data'].keys())[:5]}")
            else:
                print(f"  ✗ FAILED: Returns {type(report['report_data']).__name__}")
        else:
            print("  No Reports in database")
        
        # Check if Jobs or Sessions exist
        jobs_count = await conn.fetchval("SELECT COUNT(*) FROM jobs")
        sessions_count = await conn.fetchval("SELECT COUNT(*) FROM sessions")
        
        print(f"\n[Jobs]: {jobs_count} rows")
        if jobs_count > 0:
            job = await conn.fetchrow("SELECT job_id, job_data FROM jobs LIMIT 1")
            print(f"  job_id: {job['job_id']}")
            print(f"  type(job_data): {type(job['job_data'])}")
            print(f"  Is dict: {isinstance(job['job_data'], dict)}")
        
        print(f"\n[Sessions]: {sessions_count} rows")
        if sessions_count > 0:
            session = await conn.fetchrow("SELECT session_id, session_data FROM sessions LIMIT 1")
            print(f"  session_id: {session['session_id']}")
            print(f"  type(session_data): {type(session['session_data'])}")
            print(f"  Is dict: {isinstance(session['session_data'], dict)}")
        
        print("\n" + "=" * 70)
        print("TYPE VERIFICATION COMPLETE")
        print("=" * 70)
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(verify_types())
