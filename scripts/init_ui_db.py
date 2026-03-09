"""
UI 지원 DB 스키마 확장 스크립트 (TASK-UI) - 최종 버전

partial-state 처리: 기존에 잘못 생성된 테이블은 DROP CASCADE 후 재생성.

Usage:
    python scripts/init_ui_db.py
"""

import os
import sys
import re
import logging
import asyncio
from pathlib import Path
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("init_ui_db")

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import asyncpg  # type: ignore

conn_string = os.getenv("POSTGRES_CONNECTION_STRING", "")
pattern = r"postgresql(?:\+asyncpg)?://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)"
match = re.match(pattern, conn_string)
if match:
    user_, password, host, port, database = match.groups()
    CONN_PARAMS = dict(host=host, port=int(port), user=user_, password=password, database=database)
else:
    CONN_PARAMS = dict(
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
        database=os.getenv("PGDATABASE", "imh_interview"),
    )


async def col_exists(conn, table: str, col: str) -> bool:
    row = await conn.fetchrow(
        "SELECT 1 FROM information_schema.columns WHERE table_name=$1 AND column_name=$2",
        table, col
    )
    return row is not None


async def table_exists(conn, table: str) -> bool:
    row = await conn.fetchrow(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=$1",
        table
    )
    return row is not None


async def run():
    logger.info("Connecting to PostgreSQL ...")
    conn = await asyncpg.connect(**CONN_PARAMS)
    try:
        # -------------------------
        # 1. user_info
        # -------------------------
        if not await table_exists(conn, "user_info"):
            await conn.execute("""
                CREATE TABLE user_info (
                    user_id     VARCHAR(255) PRIMARY KEY,
                    username    VARCHAR(255) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    name        TEXT NOT NULL,
                    birth_date  DATE,
                    gender      VARCHAR(10),
                    email       TEXT,
                    address     TEXT,
                    phone       TEXT,
                    user_type   VARCHAR(20) NOT NULL DEFAULT 'CANDIDATE',
                    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("✓ Created user_info")
        else:
            logger.info("✓ user_info exists, checking columns...")
            for col, definition in [
                ("username", "VARCHAR(255)"),
                ("password_hash", "TEXT"),
                ("name", "TEXT"),
                ("birth_date", "DATE"),
                ("gender", "VARCHAR(10)"),
                ("email", "TEXT"),
                ("address", "TEXT"),
                ("phone", "TEXT"),
                ("user_type", "VARCHAR(20) DEFAULT 'CANDIDATE'"),
            ]:
                if not await col_exists(conn, "user_info", col):
                    # For NOT NULL constraints, we'll omit them when altering an existing populated table
                    # but since this is dev db, we just let it add nullable or default columns.
                    alter_def = definition
                    if col == "username":
                        alter_def = "VARCHAR(255) UNIQUE"
                    await conn.execute(f"ALTER TABLE user_info ADD COLUMN {col} {alter_def}")
                    logger.info(f"✓ Added user_info.{col}")

        # -------------------------
        # 2. resumes
        # -------------------------
        if not await table_exists(conn, "resumes"):
            await conn.execute("""
                CREATE TABLE resumes (
                    resume_id   SERIAL PRIMARY KEY,
                    user_id     VARCHAR(255) NOT NULL REFERENCES user_info(user_id),
                    file_name   TEXT NOT NULL,
                    file_path   TEXT NOT NULL,
                    file_size   BIGINT,
                    uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("✓ Created resumes")
        else:
            logger.info("✓ resumes already exists")

        # -------------------------
        # 3. chat_history (no FK to interviews for flexibility)
        # -------------------------
        if not await table_exists(conn, "chat_history"):
            await conn.execute("""
                CREATE TABLE chat_history (
                    id          SERIAL PRIMARY KEY,
                    session_id  VARCHAR(255) NOT NULL,
                    role        VARCHAR(20)  NOT NULL,
                    content     TEXT         NOT NULL,
                    phase       TEXT,
                    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("✓ Created chat_history")
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_history_session ON chat_history(session_id)"
            )
        else:
            logger.info("✓ chat_history already exists")

        # -------------------------
        # 4. interview_evaluations
        #    Fix: if table exists but is missing session_id, drop and recreate
        # -------------------------
        ie_exists = await table_exists(conn, "interview_evaluations")
        if ie_exists:
            has_session_id = await col_exists(conn, "interview_evaluations", "session_id")
            if not has_session_id:
                logger.warning("interview_evaluations exists but missing session_id – dropping to recreate")
                await conn.execute("DROP TABLE interview_evaluations CASCADE")
                ie_exists = False

        if not ie_exists:
            await conn.execute("""
                CREATE TABLE interview_evaluations (
                    eval_id       SERIAL PRIMARY KEY,
                    session_id    VARCHAR(255) NOT NULL,
                    decision      VARCHAR(10)  NOT NULL,
                    summary       TEXT,
                    tech_score    FLOAT,
                    problem_score FLOAT,
                    comm_score    FLOAT,
                    nonverbal_score FLOAT,
                    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("✓ Created interview_evaluations")
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_eval_session ON interview_evaluations(session_id)"
            )
        else:
            logger.info("✓ interview_evaluations already exists (correct schema)")

        # -------------------------
        # 5. Extend jobs table
        # -------------------------
        for col, definition in [
            ("description", "TEXT"),
            ("location",    "TEXT"),
            ("headcount",   "INTEGER"),
            ("deadline",    "DATE"),
            ("tags",        "TEXT[]"),
        ]:
            if not await col_exists(conn, "jobs", col):
                await conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {definition}")
                logger.info(f"✓ Added jobs.{col}")
            else:
                logger.info(f"✓ jobs.{col} already exists")

        # -------------------------
        # 6. Add resume_path to interviews
        # -------------------------
        if not await col_exists(conn, "interviews", "resume_path"):
            await conn.execute("ALTER TABLE interviews ADD COLUMN resume_path TEXT")
            logger.info("✓ Added interviews.resume_path")
        else:
            logger.info("✓ interviews.resume_path already exists")

        # -------------------------
        # Verify
        # -------------------------
        tables = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name = ANY($1)",
            ['user_info', 'chat_history', 'interview_evaluations', 'resumes']
        )
        found = {r["table_name"] for r in tables}
        expected = {"user_info", "chat_history", "interview_evaluations", "resumes"}
        if expected <= found:
            logger.info(f"✓ All UI tables verified: {sorted(expected)}")
        else:
            missing = expected - found
            logger.error(f"MISSING tables: {missing}")
            sys.exit(1)

        logger.info("✓ UI DB extension complete.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
