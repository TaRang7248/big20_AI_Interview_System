"""
Track B: Observability Service.

CONTRACTS:
- Orchestrates ObservabilityRepository and RedisStatsRepository (for caching).
- NEVER calls Track A (StatisticsRepository, StatisticsService).
- All responses include as_of, is_cached, ttl_remaining.
- Redis is Result Cache Only (setex/TTL). Not Authority.
- Type 4: DISABLED guard enforced before any execution.

PHYSICAL SEPARATION:
- This service imports only obs_* modules and RedisStatsRepository (shared cache).
- It does NOT import StatisticsRepository or StatisticsService.
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from packages.imh_stats.obs_repository import (
    ObservabilityRepository,
    LogObservabilityRepository,
    DISABLED_TYPE4,
)
from packages.imh_stats.repository import RedisStatsRepository
from packages.imh_stats.obs_dtos import (
    ObsMetaDTO,
    ObsResponseDTO,
    LatencyMetricDTO,
    FailureRateMetricDTO,
    CacheHitRateDTO,
)

logger = logging.getLogger("imh.obs.service")

# Redis TTL strategies for Track B metrics
TTL_REALTIME_OBS = 30          # 30s: short-lived metrics (cache hit rate, current failures)
TTL_PERIOD_OBS = 3600          # 1h:  period-based aggregations (latency, failure trend)


class ObservabilityService:
    """
    Service for Track B: Operational Observability.

    PHYSICAL SEPARATION CONTRACT:
    - Does NOT import or call StatisticsRepository (Track A).
    - Does NOT import or call StatisticsService (Track A).
    - Uses ObservabilityRepository (PG failure events) independently.
    - Uses LogObservabilityRepository (log-based, in-memory aggregation).
    - Uses RedisStatsRepository only as a Result Cache (setex).

    DATA AUTHORITY:
    - Track B results are Informational ONLY.
    - Cached results preserve as_of from the original query time.
    """

    def __init__(
        self,
        obs_repo: ObservabilityRepository,
        log_repo: LogObservabilityRepository,
        redis_repo: RedisStatsRepository,
    ):
        self.obs_repo = obs_repo
        self.log_repo = log_repo
        self.redis_repo = redis_repo

    def _build_cache_key_prefix(self) -> str:
        return "obs:v1"

    async def get_state_transition_failures(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> ObsResponseDTO[List[Dict[str, Any]]]:
        """
        Track B: State transition failure trend from PG.
        Source: sessions.status='INTERRUPTED'. NOT derived from Engine modification.
        Cached for TTL_PERIOD_OBS seconds.
        """
        query_name = "state_transition_failures"
        params = {"start": start_date.isoformat(), "end": end_date.isoformat()}
        full_key = f"{self._build_cache_key_prefix()}"

        cached = self.redis_repo.get(query_name, params)
        if cached:
            payload, ttl = cached
            as_of = datetime.fromisoformat(payload.get("as_of", datetime.utcnow().isoformat()))
            return ObsResponseDTO(
                meta=ObsMetaDTO(
                    as_of=as_of,
                    period_from=start_date,
                    period_to=end_date,
                    is_cached=True,
                    ttl_remaining=ttl,
                ),
                result=payload.get("result", []),
            )

        result = await self.obs_repo.get_state_transition_failures(start_date, end_date)
        now = datetime.utcnow()
        self.redis_repo.save(query_name, params, {"result": result, "as_of": now.isoformat()}, ttl_seconds=TTL_PERIOD_OBS)

        return ObsResponseDTO(
            meta=ObsMetaDTO(
                as_of=now,
                period_from=start_date,
                period_to=end_date,
                is_cached=False,
            ),
            result=result,
        )

    def get_latency_stats(
        self,
        span: str,
        start_date: datetime,
        end_date: datetime,
    ) -> ObsResponseDTO[Dict[str, Any]]:
        """
        Track B: Average latency per span from log files.
        Source: log files (Informational, log loss expected).
        Cached for TTL_PERIOD_OBS seconds.
        """
        query_name = "latency_stats"
        params = {"span": span, "start": start_date.isoformat(), "end": end_date.isoformat()}

        cached = self.redis_repo.get(query_name, params)
        if cached:
            payload, ttl = cached
            as_of = datetime.fromisoformat(payload.get("as_of", datetime.utcnow().isoformat()))
            return ObsResponseDTO(
                meta=ObsMetaDTO(
                    as_of=as_of,
                    span=span,
                    period_from=start_date,
                    period_to=end_date,
                    is_cached=True,
                    ttl_remaining=ttl,
                ),
                result=payload.get("result", {}),
            )

        result = self.log_repo.get_latency_stats(span, start_date, end_date)
        now = datetime.utcnow()
        self.redis_repo.save(query_name, params, {"result": result, "as_of": now.isoformat()}, ttl_seconds=TTL_PERIOD_OBS)

        return ObsResponseDTO(
            meta=ObsMetaDTO(
                as_of=now,
                span=span,
                period_from=start_date,
                period_to=end_date,
                is_cached=False,
            ),
            result=result,
        )

    def get_failure_rates(
        self,
        reason: str,
        start_date: datetime,
        end_date: datetime,
    ) -> ObsResponseDTO[Dict[str, Any]]:
        """
        Track B: Failure rate per reason from log files.
        Source: log files (Informational, log loss expected).
        Cached for TTL_PERIOD_OBS seconds.
        """
        query_name = "failure_rates"
        params = {"reason": reason, "start": start_date.isoformat(), "end": end_date.isoformat()}

        cached = self.redis_repo.get(query_name, params)
        if cached:
            payload, ttl = cached
            as_of = datetime.fromisoformat(payload.get("as_of", datetime.utcnow().isoformat()))
            return ObsResponseDTO(
                meta=ObsMetaDTO(
                    as_of=as_of,
                    reason=reason,
                    period_from=start_date,
                    period_to=end_date,
                    is_cached=True,
                    ttl_remaining=ttl,
                ),
                result=payload.get("result", {}),
            )

        result = self.log_repo.get_failure_rates(reason, start_date, end_date)
        now = datetime.utcnow()
        self.redis_repo.save(query_name, params, {"result": result, "as_of": now.isoformat()}, ttl_seconds=TTL_PERIOD_OBS)

        return ObsResponseDTO(
            meta=ObsMetaDTO(
                as_of=now,
                reason=reason,
                period_from=start_date,
                period_to=end_date,
                is_cached=False,
            ),
            result=result,
        )

    def get_cache_hit_rate(self) -> ObsResponseDTO[Dict[str, Any]]:
        """
        Track B: Redis Cache Hit/Miss rate from log files.
        Source: log files (Informational, NOT from Redis itself as Authority).
        Cached for TTL_REALTIME_OBS (short, near-real-time).
        """
        query_name = "cache_hit_rate"
        params: Dict = {}

        cached = self.redis_repo.get(query_name, params)
        if cached:
            payload, ttl = cached
            as_of = datetime.fromisoformat(payload.get("as_of", datetime.utcnow().isoformat()))
            return ObsResponseDTO(
                meta=ObsMetaDTO(as_of=as_of, is_cached=True, ttl_remaining=ttl),
                result=payload.get("result", {}),
            )

        result = self.log_repo.get_cache_hit_rate()
        now = datetime.utcnow()
        self.redis_repo.save(query_name, params, {"result": result, "as_of": now.isoformat()}, ttl_seconds=TTL_REALTIME_OBS)

        return ObsResponseDTO(
            meta=ObsMetaDTO(as_of=now, is_cached=False),
            result=result,
        )

    async def get_type3_aggregation(
        self,
        dimension: str,
        start_date: datetime,
        end_date: datetime,
    ) -> ObsResponseDTO[List[Dict[str, Any]]]:
        """
        Type 3 Query: Multi-dimensional aggregation via MView.
        Isolation Contract: Always routes through MView (or safe fallback).
        Cached for TTL_PERIOD_OBS.
        """
        query_name = f"type3_{dimension}"
        params = {"start": start_date.isoformat(), "end": end_date.isoformat()}

        cached = self.redis_repo.get(query_name, params)
        if cached:
            payload, ttl = cached
            as_of = datetime.fromisoformat(payload.get("as_of", datetime.utcnow().isoformat()))
            return ObsResponseDTO(
                meta=ObsMetaDTO(as_of=as_of, is_cached=True, ttl_remaining=ttl, period_from=start_date, period_to=end_date),
                result=payload.get("result", []),
            )

        result = await self.obs_repo.get_type3_aggregation(dimension, start_date, end_date)
        now = datetime.utcnow()
        self.redis_repo.save(query_name, params, {"result": result, "as_of": now.isoformat()}, ttl_seconds=TTL_PERIOD_OBS)

        return ObsResponseDTO(
            meta=ObsMetaDTO(as_of=now, is_cached=False, period_from=start_date, period_to=end_date),
            result=result,
        )

    def execute_type4(self, *args, **kwargs):
        """
        Type 4 (Correlation/Anomaly): DISABLED in CP1.
        This method exists as a guard. Raises if called.
        """
        if DISABLED_TYPE4:
            raise RuntimeError(
                "Type 4 queries are DISABLED in CP1. "
                "No synchronous execution or persistent storage allowed. "
                "Re-enable only in future phases via a separate design gate."
            )
