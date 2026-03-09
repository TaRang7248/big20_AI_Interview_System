import asyncio
import logging
import sys
import os
from datetime import datetime
import time

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from packages.imh_core.config import IMHConfig
from packages.imh_stats.repository import StatisticsRepository, RedisStatsRepository
from packages.imh_stats.service import StatisticsService
from packages.imh_stats.enums import StatQueryType

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("verify_ttl")

class TestRedisStatsRepository(RedisStatsRepository):
    """
    Test-only repository that forces a short TTL to verify expiration logic
    without waiting for the full production TTL (1 hour).
    Also uses a distinct Key Prefix to avoid collision with production keys.
    """
    TEST_TTL = 2  # 2 seconds for testing
    KEY_PREFIX = "stats:test:v1"  # Override Prefix for Isolation

    def save(self, query_name: str, params: dict, result: object, ttl_seconds: int = 3600):
        # Override TTL to short duration for testing
        logger.info(f"[TestRepo] Intercepting save. Forcing TTL={self.TEST_TTL}s (Original requested: {ttl_seconds}s)")
        super().save(query_name, params, result, ttl_seconds=self.TEST_TTL)

async def main():
    logger.info("Starting TASK-028 CP0 TTL & Consistency Verification...")
    
    # 1. Load Config
    try:
        config = IMHConfig.load()
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        # Assuming .env exists from previous step, otherwise strictly fails
        
    dsn = config.POSTGRES_CONNECTION_STRING
    if dsn:
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
    else:
        logger.error("POSTGRES_CONNECTION_STRING is missing.")
        sys.exit(1)

    # 2. Initialize Components with Test Repository
    stats_repo = StatisticsRepository(conn_config={"dsn": dsn})
    redis_repo = TestRedisStatsRepository() # Use the test repo
    service = StatisticsService(stats_repo, redis_repo)
    
    # Ensure Redis is reachable
    if not redis_repo.redis:
        logger.error("Redis is not reachable. Cannot perform TTL verification.")
        sys.exit(1)

    # 3. Test Scenario: Daily Applicant Counts
    # Clean up previous keys to start fresh? 
    # The key generation depends on params. We'll use a specific date range.
    start_date = datetime(2025, 1, 1) # Specific past date
    end_date = datetime(2025, 1, 31)
    
    logger.info(f"\n[Scenario] TTL={TestRedisStatsRepository.TEST_TTL}s Verification")
    
    # --- Step A: 1st Call (Cache Miss) ---
    logger.info("Step A: 1st Call (Expect Miss)")
    resp1 = await service.get_daily_applicant_counts(start_date, end_date)
    logger.info(f"  Meta: {resp1.meta}")
    
    if resp1.meta.is_cached:
        logger.warning("Cache was already present. Waiting for it to expire first...")
        time.sleep(TestRedisStatsRepository.TEST_TTL + 1)
        resp1 = await service.get_daily_applicant_counts(start_date, end_date)
        logger.info(f"  Retry Meta: {resp1.meta}")

    assert resp1.meta.is_cached is False, "Step A Failed: Should be Cache Miss"
    assert resp1.meta.query_type == StatQueryType.REALTIME, "Step A Failed: Should be REALTIME"
    as_of_1 = resp1.meta.as_of
    logger.info(f"Step A Passed. as_of_1={as_of_1}")

    # --- Step B: 2nd Call (Cache Hit) ---
    logger.info("\nStep B: 2nd Call (Expect Hit, Immediate)")
    resp2 = await service.get_daily_applicant_counts(start_date, end_date)
    logger.info(f"  Meta: {resp2.meta}")
    
    assert resp2.meta.is_cached is True, "Step B Failed: Should be Cache Hit"
    assert resp2.meta.query_type == StatQueryType.CACHED, "Step B Failed: Should be CACHED"
    
    # as_of Consistency Check
    as_of_2 = resp2.meta.as_of
    assert as_of_2 == as_of_1, f"Step B Failed: as_of should match cached value. Got {as_of_2}, Expected {as_of_1}"
    logger.info(f"Step B Passed. as_of consistency verified.")

    # --- Step C: Wait for TTL Expiry ---
    wait_time = TestRedisStatsRepository.TEST_TTL + 1.5 # 3.5s total
    logger.info(f"\nWaiting {wait_time}s for TTL expiry...")
    time.sleep(wait_time)

    # --- Step D: 3rd Call (Cache Miss / Renewal) ---
    logger.info("Step D: 3rd Call (Expect Miss / Renewal)")
    resp3 = await service.get_daily_applicant_counts(start_date, end_date)
    logger.info(f"  Meta: {resp3.meta}")
    
    assert resp3.meta.is_cached is False, "Step D Failed: Should be Cache Miss after TTL"
    assert resp3.meta.query_type == StatQueryType.REALTIME, "Step D Failed: Should be REALTIME"
    
    # Renewal Check
    as_of_3 = resp3.meta.as_of
    assert as_of_3 > as_of_1, f"Step D Failed: as_of should be newer. Old={as_of_1}, New={as_of_3}"
    logger.info(f"Step D Passed. as_of renewed ({as_of_3})")

    logger.info("\nAll TTL & Consistency Tests Passed.")

if __name__ == "__main__":
    asyncio.run(main())
