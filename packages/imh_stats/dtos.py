from dataclasses import dataclass
from datetime import datetime
from typing import TypeVar, Generic, Optional, Any

T = TypeVar("T")

@dataclass
class StatsMetaDTO:
    """Metadata for statistics response."""
    query_type: str        # "REALTIME" | "CACHED"
    as_of: datetime        # Data snapshot time (UTC)
    period_from: Optional[datetime] = None
    period_to: Optional[datetime] = None
    group_by: Optional[str] = None
    is_cached: bool = False
    ttl_remaining: Optional[int] = None

@dataclass
class StatsResponseDTO(Generic[T]):
    """Standardized response wrapper for statistics."""
    meta: StatsMetaDTO
    result: T
