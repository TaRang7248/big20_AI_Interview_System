"""
TASK-M Sprint 1: DB migration for multimodal_observations table.

Run (from project root, with interview_env active):
    python scripts/migrate_task_m_sprint1.py

Design rules (plan §3.1):
  - 1 Row = 1 Metric. signal_id UNIQUE guarantees Exactly-once.
  - Append-only. No UPDATE or DELETE paths.
  - FK to interviews(session_id) validated after Sprint 1 realtest.
  - chunk_seq starts at 1 (not 0).
  - timestamp_offset is seconds from session start (float), metadata only.
  - payload JSONB holds the single normalised metric value.

Signal-ID contract (plan §3.2):
  UUIDv5(namespace, f"{session_id}:{turn_index}:{modality}:{chunk_seq}:{metric_key}")

This script is idempotent — safe to re-run.
"""

import os
import sys
import logging
import asyncio
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("migrate_task_m_sprint1")

env_path = project_root / ".env"
if not env_path.exists():
    logger.error(f".env file not found at {env_path}")
    sys.exit(1)
load_dotenv(env_path)

import asyncpg  # type: ignore
import re

conn_string = os.getenv("POSTGRES_CONNECTION_STRING")
if not conn_string:
    logger.error("POSTGRES_CONNECTION_STRING not found in .env")
    sys.exit(1)

pattern = r"postgresql\+asyncpg://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)"
match = re.match(pattern, conn_string)
if not match:
    logger.error(f"Invalid connection string format: {conn_string}")
    sys.exit(1)
user, password, host, port, database = match.groups()

logger.info(f"Connecting to PostgreSQL at {host}:{port}/{database}")


async def migrate():
    conn = await asyncpg.connect(
        host=host, port=int(port), user=user, password=password, database=database
    )
    try:
        logger.info("=== TASK-M Sprint 1: DB Migration ===")

        # ------------------------------------------------------------------ #
        # 1. Create multimodal_observations table                              #
        #    Append-only. No UPDATE path exists.                               #
        # ------------------------------------------------------------------ #
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS multimodal_observations (
                id           BIGSERIAL PRIMARY KEY,
                session_id   UUID NOT NULL,
                turn_index   INTEGER NOT NULL,
                chunk_seq    INTEGER NOT NULL DEFAULT 1,
                signal_id    UUID NOT NULL,
                modality     VARCHAR(20) NOT NULL,
                metric_key   VARCHAR(50) NOT NULL,
                timestamp_offset FLOAT NOT NULL,
                payload      JSONB NOT NULL,
                created_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

                CONSTRAINT uq_multimodal_signal_id UNIQUE (signal_id),
                CONSTRAINT chk_modality CHECK (
                    modality IN ('STT', 'VISION', 'EMOTION', 'AUDIO')
                ),
                CONSTRAINT chk_chunk_seq CHECK (chunk_seq >= 1)
            );
        """)
        logger.info("PASS: multimodal_observations table created/verified")

        # ------------------------------------------------------------------ #
        # 2. Indexes (plan §3.1 — query performance)                           #
        # ------------------------------------------------------------------ #
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_mm_obs_session_turn
            ON multimodal_observations (session_id, turn_index);
        """)
        logger.info("PASS: idx_mm_obs_session_turn created/verified")

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_mm_obs_session_modality
            ON multimodal_observations (session_id, modality);
        """)
        logger.info("PASS: idx_mm_obs_session_modality created/verified")

        # ------------------------------------------------------------------ #
        # 3. Note: FK to interviews(session_id) is intentionally deferred.    #
        #    The interviews.session_id column is VARCHAR(255), not UUID.       #
        #    Sprint 1 verifies FK compatibility in realtest before adding it.  #
        # ------------------------------------------------------------------ #
        logger.info(
            "NOTE: FK to interviews(session_id) deferred pending Sprint 1 realtest "
            "(type compatibility: VARCHAR vs UUID)."
        )

        logger.info("=== Migration complete ===")

    finally:
        await conn.close()


async def verify():
    conn = await asyncpg.connect(
        host=host, port=int(port), user=user, password=password, database=database
    )
    try:
        logger.info("=== Verifying migration ===")

        # Table exists
        row = await conn.fetchrow("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'multimodal_observations'
        """)
        if not row:
            logger.error("FAIL: multimodal_observations table not found")
            return False
        logger.info("PASS: multimodal_observations table exists")

        # Required columns
        required_cols = {
            "id", "session_id", "turn_index", "chunk_seq", "signal_id",
            "modality", "metric_key", "timestamp_offset", "payload", "created_at",
        }
        col_rows = await conn.fetch("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'multimodal_observations'
        """)
        actual_cols = {r["column_name"] for r in col_rows}
        missing = required_cols - actual_cols
        if missing:
            logger.error(f"FAIL: missing columns: {missing}")
            return False
        logger.info("PASS: all required columns present")

        # UNIQUE constraint on signal_id
        constraint_row = await conn.fetchrow("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_schema = 'public'
              AND table_name = 'multimodal_observations'
              AND constraint_type = 'UNIQUE'
              AND constraint_name = 'uq_multimodal_signal_id'
        """)
        if not constraint_row:
            logger.error("FAIL: UNIQUE constraint uq_multimodal_signal_id not found")
            return False
        logger.info("PASS: UNIQUE constraint on signal_id verified")

        # Indexes
        for idx_name in ("idx_mm_obs_session_turn", "idx_mm_obs_session_modality"):
            idx_row = await conn.fetchrow("""
                SELECT indexname FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'multimodal_observations'
                  AND indexname = $1
            """, idx_name)
            if not idx_row:
                logger.error(f"FAIL: index {idx_name} not found")
                return False
            logger.info(f"PASS: index {idx_name} exists")

        logger.info("=== Verification complete — all checks passed ===")
        return True

    finally:
        await conn.close()


async def main():
    await migrate()
    ok = await verify()
    if ok:
        logger.info("Sprint 1 DB migration: SUCCESS")
        return 0
    else:
        logger.error("Sprint 1 DB migration: FAILED")
        return 1


if __name__ == "__main__":
    code = asyncio.run(main())
    sys.exit(code)
