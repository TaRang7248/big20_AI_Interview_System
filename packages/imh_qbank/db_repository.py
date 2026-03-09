import json
import logging
from typing import List, Optional

import asyncpg
from packages.imh_core.config import IMHConfig
from packages.imh_dto.session import QuestionDTO

logger = logging.getLogger(__name__)

class DBQuestionRepository:
    """
    Repository for interacting with the question_bank table in PostgreSQL.
    """
    def __init__(self, conn_pool: asyncpg.Pool = None):
        self.pool = conn_pool

    async def _get_conn(self):
        # Fallback mechanism if pool isn't provided (e.g. standalone test scripts)
        if self.pool:
            return self.pool.acquire()
        
        cfg = IMHConfig.load()
        cs = cfg.POSTGRES_CONNECTION_STRING or ""
        import re
        m = re.match(r"postgresql(?:\+asyncpg)?://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", cs)
        if m:
            u, p, h, port, db = m.groups()
            conn_params = dict(host=h, port=int(port), user=u, password=p, database=db)
            return await asyncpg.connect(**conn_params)
        raise RuntimeError("Could not parse POSTGRES_CONNECTION_STRING")

    def _row_to_dto(self, row: dict, index: int = 0) -> QuestionDTO:
        # Map DB row to QuestionDTO
        # metadata = json.loads(row.get("metadata", "{}")) if isinstance(row.get("metadata"), str) else (row.get("metadata") or {})
        return QuestionDTO(
            id=row["question_id"],
            content=row["text"],
            type="TEXT", 
            time_limit_seconds=120, # Default to 120s for now
            sequence_number=index + 1
        )

    async def get_random_questions(self, limit: int = 5) -> List[QuestionDTO]:
        """Fetch random questions from the database."""
        conn = await self._get_conn()
        try:
            query = """
                SELECT * FROM question_bank
                WHERE is_active = true
                ORDER BY RANDOM()
                LIMIT $1
            """
            rows = await conn.fetch(query, limit)
            return [self._row_to_dto(dict(r), i) for i, r in enumerate(rows)]
        finally:
            if not self.pool:
                await conn.close()
            else:
                await self.pool.release(conn)

    async def get_by_category(self, category: str, limit: int = 5) -> List[QuestionDTO]:
        """Fetch questions by category."""
        conn = await self._get_conn()
        try:
            query = """
                SELECT * FROM question_bank
                WHERE is_active = true AND category = $1
                ORDER BY RANDOM()
                LIMIT $2
            """
            rows = await conn.fetch(query, category, limit)
            return [self._row_to_dto(dict(r), i) for i, r in enumerate(rows)]
        finally:
            if not self.pool:
                await conn.close()
            else:
                await self.pool.release(conn)

    async def get_by_tag(self, tag: str, limit: int = 5) -> List[QuestionDTO]:
        """Fetch questions containing a specific tag."""
        conn = await self._get_conn()
        try:
            query = """
                SELECT * FROM question_bank
                WHERE is_active = true AND $1 = ANY(tags)
                ORDER BY RANDOM()
                LIMIT $2
            """
            rows = await conn.fetch(query, tag, limit)
            return [self._row_to_dto(dict(r), i) for i, r in enumerate(rows)]
        finally:
            if not self.pool:
                await conn.close()
            else:
                await self.pool.release(conn)

