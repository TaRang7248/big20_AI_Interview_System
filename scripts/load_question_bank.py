import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("load_question_bank")

# Add the project root to sys.path so we can import internal modules
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncpg
from packages.imh_core.config import IMHConfig

def _get_conn_params() -> dict:
    import re
    cfg = IMHConfig.load()
    cs = cfg.POSTGRES_CONNECTION_STRING or ""
    m = re.match(r"postgresql(?:\+asyncpg)?://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", cs)
    if m:
        u, p, h, port, db = m.groups()
        return dict(host=h, port=int(port), user=u, password=p, database=db)
    # fallback to localhost if not properly structured or for parsing failure
    return dict(host="localhost", port=5432, user="imh_user", password="imh_password", database="interview_db")

async def create_table_if_not_exists(conn):
    logger.info("Creating question_bank table if it does not exist...")
    query = """
    CREATE TABLE IF NOT EXISTS question_bank (
        question_id VARCHAR(255) PRIMARY KEY,
        text TEXT NOT NULL,
        sample_answer TEXT,
        category VARCHAR(255) DEFAULT 'general',
        tags TEXT[] DEFAULT '{}',
        difficulty VARCHAR(50) DEFAULT 'medium',
        source VARCHAR(255) DEFAULT 'data.json',
        metadata JSONB DEFAULT '{}'::jsonb,
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """
    await conn.execute(query)
    logger.info("Table verification complete.")

async def load_data(conn, data_path: Path):
    if not data_path.exists():
        logger.error(f"Data file not found at: {data_path}")
        return

    logger.info(f"Loading data from {data_path}")
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    logger.info(f"Found {len(data)} questions in the JSON file. Starting Upsert...")
    
    upsert_query = """
    INSERT INTO question_bank (
        question_id, text, sample_answer, category, tags, source, metadata
    ) VALUES (
        $1, $2, $3, $4, $5, $6, $7
    )
    ON CONFLICT (question_id) DO UPDATE SET
        text = EXCLUDED.text,
        sample_answer = EXCLUDED.sample_answer,
        category = EXCLUDED.category,
        tags = EXCLUDED.tags,
        metadata = EXCLUDED.metadata,
        updated_at = CURRENT_TIMESTAMP;
    """

    inserted_or_updated = 0
    for item in data:
        q_id_raw = item.get("id")
        if q_id_raw is None:
            continue
            
        question_id = f"data_json_{q_id_raw}"
        text = item.get("question", "")
        sample_answer = item.get("answer", "")
        # Assuming all of these are general since category isn't in original json schema
        category = "general"
        tags = []
        source = "data.json"
        metadata = json.dumps({"original_id": q_id_raw})

        await conn.execute(upsert_query, question_id, text, sample_answer, category, tags, source, metadata)
        inserted_or_updated += 1

    logger.info(f"Successfully upserted {inserted_or_updated} questions.")
    
    # Verify count
    count = await conn.fetchval("SELECT COUNT(*) FROM question_bank")
    logger.info(f"Total rows in question_bank table: {count}")

async def main():
    logger.info("Starting Question Bank data load process...")
    conn_params = _get_conn_params()
    try:
        conn = await asyncpg.connect(**conn_params)
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return

    try:
        await create_table_if_not_exists(conn)
        
        # Determine path to data.json
        # Project root is AI_Interview_System's parent
        data_json_path = ROOT_DIR.parent.parent / "data" / "data.json"
        
        await load_data(conn, data_json_path)
    finally:
        await conn.close()
        logger.info("Database connection closed.")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
