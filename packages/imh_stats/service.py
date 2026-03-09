import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from packages.imh_stats.repository import StatisticsRepository, RedisStatsRepository
from packages.imh_stats.dtos import StatsResponseDTO, StatsMetaDTO
from packages.imh_stats.enums import StatQueryType

logger = logging.getLogger("imh.stats.service")

class StatisticsService:
    """
    Service Layer for Business Statistics (Track A).
    
    CONTRACTS:
    - Orchestration Only: Coordinates Repositories vs Cache.
    - No Side Effects: Does not modify any state.
    - Metadata Handling: Enriches responses with caching info.
    """
    
    def __init__(self, stats_repo: StatisticsRepository, redis_repo: RedisStatsRepository):
        self.stats_repo = stats_repo
        self.redis_repo = redis_repo
        
    async def get_daily_applicant_counts(self, start_date: datetime, end_date: datetime) -> StatsResponseDTO[List[Dict[str, Any]]]:
        """
        Type 2 Query: Daily Counts. Cached for 1 hour.
        """
        query_name = "daily_applicant_counts"
        params = {"start": start_date.isoformat(), "end": end_date.isoformat()}
        
        # 1. Try Cache
        cached = self.redis_repo.get(query_name, params)
        if cached:
            payload, ttl = cached
            # Expect payload to wrap result and timestamp
            result = payload.get("result")
            as_of_str = payload.get("as_of")
            as_of = datetime.fromisoformat(as_of_str) if as_of_str else datetime.utcnow()
            
            return StatsResponseDTO(
                meta=StatsMetaDTO(
                    query_type=StatQueryType.CACHED,
                    as_of=as_of,
                    period_from=start_date,
                    period_to=end_date,
                    is_cached=True,
                    ttl_remaining=ttl
                ),
                result=result
            )

        # 2. Cache Miss: Query DB
        result = await self.stats_repo.get_daily_applicant_counts(start_date, end_date)
        now = datetime.utcnow()
        
        # 3. Save to Cache (1 hour TTL)
        cache_payload = {
            "result": result,
            "as_of": now.isoformat()
        }
        self.redis_repo.save(query_name, params, cache_payload, ttl_seconds=3600)
        
        return StatsResponseDTO(
            meta=StatsMetaDTO(
                query_type=StatQueryType.REALTIME,
                as_of=now,
                period_from=start_date,
                period_to=end_date,
                is_cached=False
            ),
            result=result
        )

    async def get_current_status(self) -> StatsResponseDTO[Dict[str, int]]:
        """
        Type 1 Query: Real-time Status. No Cache (or very short).
        Strategy: Direct DB Query (Realtime needed for dashboard monitoring).
        """
        # Direct DB Query
        result = await self.stats_repo.get_current_status_counts()
        now = datetime.utcnow()
        
        return StatsResponseDTO(
            meta=StatsMetaDTO(
                query_type=StatQueryType.REALTIME,
                as_of=now,
                is_cached=False
            ),
            result=result
        )

    async def get_average_scores(self, job_id: Optional[str] = None) -> StatsResponseDTO[Dict[str, float]]:
        """
        Type 2 Query: Average Scores. Cached for 1 hour.
        """
        query_name = "average_scores"
        params = {"job_id": job_id}
        
        # 1. Try Cache
        cached = self.redis_repo.get(query_name, params)
        if cached:
            payload, ttl = cached
            result = payload.get("result")
            as_of_str = payload.get("as_of")
            as_of = datetime.fromisoformat(as_of_str) if as_of_str else datetime.utcnow()
            
            return StatsResponseDTO(
                meta=StatsMetaDTO(
                    query_type=StatQueryType.CACHED,
                    as_of=as_of,
                    group_by="job_id" if job_id else "total",
                    is_cached=True,
                    ttl_remaining=ttl
                ),
                result=result
            )

        # 2. Cache Miss: Query DB
        result = await self.stats_repo.get_average_scores(job_id)
        now = datetime.utcnow()
        
        # 3. Save to Cache
        cache_payload = {
            "result": result,
            "as_of": now.isoformat()
        }
        self.redis_repo.save(query_name, params, cache_payload, ttl_seconds=3600)
        
        return StatsResponseDTO(
            meta=StatsMetaDTO(
                query_type=StatQueryType.REALTIME,
                as_of=now,
                group_by="job_id" if job_id else "total",
                is_cached=False
            ),
            result=result
        )
