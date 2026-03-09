"""
Track B: Operational Observability DTOs.

CONTRACTS:
- Informational ONLY. NEVER used for business decisions.
- All responses MUST include as_of, is_cached, ttl_remaining.
- Physically separate from Track A (StatsMetaDTO, StatsResponseDTO).
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import TypeVar, Generic, Optional, Any, Dict, List

T = TypeVar("T")


@dataclass
class ObsMetaDTO:
    """Metadata for observability response (Track B)."""
    as_of: datetime                          # Data reference time (UTC)
    span: Optional[str] = None               # ObsSpan value
    layer: Optional[str] = None              # ObsLayer value
    reason: Optional[str] = None             # ObsReason value (for failures)
    period_from: Optional[datetime] = None
    period_to: Optional[datetime] = None
    is_cached: bool = False
    ttl_remaining: Optional[int] = None
    informational_only: bool = True          # ALWAYS True for Track B


@dataclass
class ObsResponseDTO(Generic[T]):
    """
    Standardized Track B response wrapper.

    CONTRACT: NEVER mixed with Track A StatsResponseDTO in a single API response.
    """
    meta: ObsMetaDTO
    result: T


@dataclass
class LatencyMetricDTO:
    """Average latency per span/layer."""
    span: str
    layer: str
    avg_latency_ms: float
    sample_count: int


@dataclass
class FailureRateMetricDTO:
    """Failure rate per reason/layer."""
    reason: str
    layer: str
    failure_count: int
    total_count: int
    failure_rate: float  # 0.0 - 1.0


@dataclass
class CacheHitRateDTO:
    """Redis cache hit/miss rate (observational only)."""
    hit_count: int
    miss_count: int
    hit_rate: float  # 0.0 - 1.0
    total_requests: int
