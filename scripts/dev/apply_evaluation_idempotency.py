import asyncio
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
import asyncpg

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("apply_idempotency")

load_dotenv(project_root / ".env")

async def main():
    conn_str = os.getenv("POSTGRES_CONNECTION_STRING")
    if not conn_str:
        logger.error("POSTGRES_CONNECTION_STRING not found.")
        sys.exit(1)
        
    dsn = conn_str.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        # Add UNIQUE constraint to session_id in evaluation_scores
        logger.info("Adding UNIQUE constraint to evaluation_scores(session_id)...")
        await conn.execute("""
            ALTER TABLE evaluation_scores 
            ADD CONSTRAINT unique_session_id UNIQUE (session_id);
        """)
        logger.info("Successfully added UNIQUE constraint.")
    except asyncpg.exceptions.DuplicateObjectError:
        logger.info("UNIQUE constraint already exists.")
    except Exception as e:
        logger.error(f"Failed to apply UNIQUE constraint: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
