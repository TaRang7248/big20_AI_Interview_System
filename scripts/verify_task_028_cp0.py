import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from packages.imh_core.config import IMHConfig
from packages.imh_stats.repository import StatisticsRepository, RedisStatsRepository
from packages.imh_stats.service import StatisticsService
from packages.imh_stats.dtos import StatsResponseDTO
from packages.imh_stats.enums import StatQueryType

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("verify_task_028_cp0")

async def main():
    logger.info("Starting TASK-028 CP0 Verification...")
    
    # 1. Load Config
    try:
        config = IMHConfig.load()
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)
        
    dsn = config.POSTGRES_CONNECTION_STRING
    if not dsn:
        logger.error("POSTGRES_CONNECTION_STRING not set in .env")
        sys.exit(1)
        
    # AsyncPG expects postgresql:// not postgresql+asyncpg://
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
    
    # 2. Initialize Components
    stats_repo = StatisticsRepository(conn_config={"dsn": dsn})
    redis_repo = RedisStatsRepository()
    service = StatisticsService(stats_repo, redis_repo)
    
    # 3. Test Cases
    
    # [Test 1] Type 1 (Real-time Status)
    logger.info("\n[Test 1] Type 1: Real-time Status Check")
    try:
        response = await service.get_current_status()
        logger.info(f"Response: {response}")
        
        # Assertions
        assert isinstance(response, StatsResponseDTO), "Response must be DTO"
        assert response.meta.query_type == StatQueryType.REALTIME, "Must be REALTIME"
        assert response.meta.is_cached is False, "Must not be cached"
        assert isinstance(response.result, dict), "Result must be dict"
        logger.info("✅ Type 1 Verification Passed")
    except Exception as e:
        logger.error(f"❌ Type 1 Verification Failed: {e}")
        # Don't exit yet, proceed to next test
    
    # [Test 2] Type 2 (Daily Applicants) - Cache Miss -> Cache Hit
    logger.info("\n[Test 2] Type 2: Daily Applicants (Cache Test)")
    today = datetime.utcnow()
    start_date = today - timedelta(days=7)
    
    try:
        # 2-1. First Call (Miss)
        logger.info("  >> 2-1: First Call (Expect Miss)")
        resp1 = await service.get_daily_applicant_counts(start_date, today)
        logger.info(f"  Result 1 Meta: {resp1.meta}")
        
        assert resp1.meta.is_cached is False, "First call must be cache miss"
        assert resp1.meta.query_type == StatQueryType.REALTIME, "First call must be REALTIME type"
        
        # 2-2. Second Call (Hit)
        logger.info("  >> 2-2: Second Call (Expect Hit)")
        resp2 = await service.get_daily_applicant_counts(start_date, today)
        logger.info(f"  Result 2 Meta: {resp2.meta}")
        
        assert resp2.meta.is_cached is True, "Second call must be cache hit"
        assert resp2.meta.query_type == StatQueryType.CACHED, "Second call must be CACHED type"
        assert resp2.result == resp1.result, "Results must strictly match"
        # as_of in cached response should be from when it was cached
        # Since calls are immediate, likely close, but logic validation is key
        
        logger.info("✅ Type 2 Verification Passed (Read-Through works)")
    except Exception as e:
        logger.error(f"❌ Type 2 Verification Failed: {e}")

    # [Test 3] Type 2 (Average Scores)
    logger.info("\n[Test 3] Type 2: Average Scores (Aggregate Check)")
    try:
        resp_score = await service.get_average_scores()
        logger.info(f"Response Score: {resp_score}")
        
        assert isinstance(resp_score.result, dict), "Result must be dict"
        assert "avg_total" in resp_score.result, "Must contain avg_total"
        logger.info("✅ Type 2 Scores Verification Passed")
    except Exception as e:
        logger.error(f"❌ Type 2 Scores Verification Failed: {e}")

    logger.info("\n---------------------------------------------------")
    logger.info("TASK-028 CP0 Verification Complete.")

if __name__ == "__main__":
    asyncio.run(main())
