from enum import Enum

class StatQueryType(str, Enum):
    REALTIME = "REALTIME"  # Type 1: Direct DB Query
    CACHED = "CACHED"      # Type 2: Read-Through Cached

class StatPeriod(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
