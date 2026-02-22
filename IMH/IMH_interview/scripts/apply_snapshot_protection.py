"""
Script: apply_snapshot_protection.py
Purpose: Apply L3 Storage Guard (Postgres Trigger) to enforce Snapshot Immutability.
Scope: TASK-031 Implementation
"""
import asyncio
import logging
import os
import sys

# Ensure package path is available
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from packages.imh_session.infrastructure.postgresql_repo import PostgreSQLSessionRepository

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("apply_snapshot_protection")

DB_CONFIG = {
    "user": "postgres",
    "password": "1234",
    "database": "interview_db",
    "host": "localhost",
    "port": 5432
}

async def apply_trigger():
    logger.info("Connecting to Database for L3 Guard Application...")
    
    # We use basic asyncpg directly for DDL, but reusing repo's config structure if logical
    import asyncpg
    
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        logger.info("Connected.")

        # 1. Create Function
        logger.info("Creating Immutability Function...")
        func_ddl = """
        CREATE OR REPLACE FUNCTION check_snapshot_immutability() RETURNS TRIGGER AS $$
        BEGIN
            -- Check Level 1 Template
            IF OLD.job_policy_snapshot IS DISTINCT FROM NEW.job_policy_snapshot THEN
                RAISE EXCEPTION 'L3 VIOLATION: job_policy_snapshot is immutable. (Session: %)', NEW.session_id
                    USING ERRCODE = '20801'; -- Custom Error Code
            END IF;
            
            -- Check Level 2 Instance
            IF OLD.session_config_snapshot IS DISTINCT FROM NEW.session_config_snapshot THEN
                RAISE EXCEPTION 'L3 VIOLATION: session_config_snapshot is immutable. (Session: %)', NEW.session_id
                    USING ERRCODE = '20802'; -- Custom Error Code
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
        await conn.execute(func_ddl)
        
        # 2. Apply Trigger
        logger.info("Applying Trigger to 'interviews' table...")
        trigger_ddl = """
        DROP TRIGGER IF EXISTS enforce_snapshot_immutability ON interviews;
        
        CREATE TRIGGER enforce_snapshot_immutability
        BEFORE UPDATE ON interviews
        FOR EACH ROW
        EXECUTE FUNCTION check_snapshot_immutability();
        """
        await conn.execute(trigger_ddl)
        
        logger.info("L3 Storage Guard Applied Successfully.")
        
    except Exception as e:
        logger.error(f"Failed to apply L3 Guard: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    try:
        asyncio.run(apply_trigger())
    except Exception as e:
        logger.critical(f"Execution Failed: {e}")
        sys.exit(1)
