import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import hashlib

import asyncpg  # type: ignore
from redis.exceptions import RedisError

from packages.imh_core.infra.redis import RedisClient
from packages.imh_stats.dtos import StatsMetaDTO
from packages.imh_stats.enums import StatQueryType

logger = logging.getLogger("imh.stats.repository")

class StatisticsRepository:
    """
    PostgreSQL Repository for Business Statistics (Track A).
    
    CONTRACTS:
    - Source of Truth: PostgreSQL Only.
    - Read-Only: SELECT queries only. NO INSERT/UPDATE.
    - No Engine Dependency: Pure data projection.
    """
    
    def __init__(self, conn_config: dict):
        self.conn_config = conn_config
        
    def _get_event_loop(self):
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

    async def _get_connection(self):
        # reuse connection logic pattern if needed or just connect
        return await asyncpg.connect(**self.conn_config)

    async def get_daily_applicant_counts(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """
        Type 2 Query: Daily applicant counts within range.
        Snapshot Source: interviews table.
        """
        conn = await self._get_connection()
        try:
            query = """
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as count
                FROM sessions
                WHERE created_at >= $1 AND created_at <= $2
                GROUP BY DATE(created_at)
                ORDER BY DATE(created_at) ASC
            """
            rows = await conn.fetch(query, start_date, end_date)
            return [{"date": str(row["date"]), "count": row["count"]} for row in rows]
        finally:
            await conn.close()

    async def get_current_status_counts(self) -> Dict[str, int]:
        """
        Type 1 Query: Real-time status counts.
        Snapshot Source: interviews table.
        """
        conn = await self._get_connection()
        try:
            query = """
                SELECT 
                    status,
                    COUNT(*) as count
                FROM sessions
                GROUP BY status
            """
            rows = await conn.fetch(query)
            return {row["status"]: row["count"] for row in rows}
        finally:
            await conn.close()

    async def get_average_scores(self, job_id: Optional[str] = None) -> Dict[str, float]:
        """
        Type 2 Query: Average scores (Total + Categories).
        Snapshot Source: evaluations table (JSONB).
        """
        conn = await self._get_connection()
        try:
            # Note: This relies on evaluations storing scores in JSONB
            # We assume evaluations.report_data -> header -> total_score
            # And we need to join with interviews if filtering by job_id is needed, 
            # OR if evaluation stores job_id. 
            # Looking at HistoryRepo, report_data has header -> job_id.
            
            where_clause = ""
            args = []
            if job_id:
                where_clause = "WHERE report_data->'header'->>'job_id' = $1"
                args.append(job_id)

            query = f"""
                SELECT 
                    AVG(CAST(report_data->'header'->>'total_score' AS FLOAT)) as avg_total
                FROM reports
                {where_clause}
            """
            # Note: The table name is 'reports' (from HistoryRepo), not 'evaluations'.
            # Wait, doc says 'evaluations' schema applies. 
            # Let's check CURRENT_STATE. Phase 8 says "evaluations schema applied".
            # But HistoryRepo uses "reports" table. 
            # HistoryRepo docstring says "Stores interview reports in the 'reports' table".
            # I must use 'reports' table as verified source.
            
            row = await conn.fetchrow(query, *args)
            return {"avg_total": row["avg_total"] or 0.0}
        finally:
            await conn.close()

class RedisStatsRepository:
    """
    Redis Repository for Statistics Cache (Read-Through).
    
    CONTRACTS:
    - Cache Only: Not Source of Truth.
    - No Write-Back: Does not write to PG.
    - TTL Required: All keys must have expiry.
    """
    
    KEY_PREFIX = "stats:v1"

    def __init__(self):
        try:
            self.redis = RedisClient.get_instance()
        except Exception:
            self.redis = None
            logger.warning("Redis unreachable. Stats Cache is disabled.")

    def _generate_key(self, query_name: str, params: dict) -> str:
        # Standardize params to string for consistent hashing
        param_str = json.dumps(params, sort_keys=True, default=str)
        param_hash = hashlib.sha256(param_str.encode()).hexdigest()
        return f"{self.KEY_PREFIX}:{query_name}:{param_hash}"

    def get(self, query_name: str, params: dict) -> Optional[tuple[Any, int]]:
        """
        Returns (result, ttl_remaining) or None.
        """
        if not self.redis:
            return None
        
        key = self._generate_key(query_name, params)
        try:
            data = self.redis.get(key)
            if data:
                ttl = self.redis.ttl(key)
                return json.loads(data), ttl
            return None
        except Exception:
            return None

    def save(self, query_name: str, params: dict, result: Any, ttl_seconds: int = 3600):
        if not self.redis:
            return
            
        key = self._generate_key(query_name, params)
        try:
            self.redis.setex(key, timedelta(seconds=ttl_seconds), json.dumps(result, default=str))
        except Exception as e:
            logger.warning(f"Failed to cache stats {key}: {e}")
