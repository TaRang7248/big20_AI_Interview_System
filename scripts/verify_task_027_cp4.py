import asyncio
import logging
import sys
import os
import json
from unittest.mock import MagicMock, patch

# 0. Setup Environment for Config Validation
os.environ["POSTGRES_CONNECTION_STRING"] = "postgresql://dummy:dummy@localhost:5432/dummy"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["REDIS_PASSWORD"] = "dummy"

# Setup path
sys.path.append(os.getcwd())

# 1. Mock RedisClient BEFORE importing Repository
# We need to ensure RedisClient.get_instance() returns a Mock object
# so that Repository __init__ (which calls get_instance) succeeds.
import packages.imh_core.infra.redis as redis_infra

class MockRedis:
    def __init__(self):
        self.store = {}
    
    def get(self, key):
        return self.store.get(key)
    
    def setex(self, key, time, value):
        self.store[key] = value
        
    def keys(self, pattern):
        return []
    
    def delete(self, *keys):
        pass

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

mock_redis_instance = MockRedis()
redis_infra.RedisClient.get_instance = MagicMock(return_value=mock_redis_instance)

# Now import the components under test
from packages.imh_session.infrastructure.redis_prompt_repository import RedisPromptRepository
from packages.imh_service.prompt.composer import CachedPromptComposer
from packages.imh_core.constants import LOGICAL_PROMPT_VERSION

# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("verify_cp4")

async def verify_cp4():
    print(f"=== Starting CP4 Verification (Logical Version: {LOGICAL_PROMPT_VERSION}) ===")
    
    # 1. Initialize Components
    repo = RedisPromptRepository()
    composer = CachedPromptComposer(repository=repo)
    
    # 2. Prepare Context (Snapshot A)
    ctx_a = {
        "snapshot_id": "snap_1001",
        "persona_id": "p_dev_senior",
        "interview_mode": "REAL",
        "policy_hash": "policy_v1_hash",
        "model_id": "gpt-4-turbo",
        "input_data": {"history": ["Initial greeting"], "user_msg": "Hello"}
    }
    
    # 3. Test Cache MISS
    print("\n[Test 1] Cache MISS Scenario")
    result_1 = composer.compose_prompt(ctx_a)
    print(f"Result 1 (Miss): {result_1[:50]}...")
    assert "System:" in result_1
    
    # 4. Test Cache HIT
    print("\n[Test 2] Cache HIT Scenario")
    # Immediate retry with same context
    result_2 = composer.compose_prompt(ctx_a)
    print(f"Result 2 (Hit): {result_2[:50]}...")
    assert result_1 == result_2
    
    # Verify the cache contains the data
    # Note: MockRedis is simple dict, keys should exist
    print(f"Mock Redis Size: {len(mock_redis_instance.store)}")
    assert len(mock_redis_instance.store) > 0
    
    # 5. Test Key Change (Simulate different inputs)
    print("\n[Test 3] Context Change (New Key)")
    ctx_b = ctx_a.copy()
    ctx_b["input_data"] = {"history": ["Initial greeting"], "user_msg": "New Message"}
    
    result_3 = composer.compose_prompt(ctx_b)
    print(f"Result 3 (New Key): {result_3[:50]}...")
    
    # 6. Test Fail-Open (Redis Failure Simulation)
    print("\n[Test 4] Fail-Open Scenario")
    
    # Patch the MockRedis.get to raise Exception
    original_get = mock_redis_instance.get
    def mock_fail_get(key):
        raise Exception("Simulated Redis Failure")
    mock_redis_instance.get = mock_fail_get
    
    try:
        # Should NOT raise exception, but log warning and return composed prompt
        result_fail_open = composer.compose_prompt(ctx_a)
        print(f"Result (Fail-Open): {result_fail_open[:50]}...")
        assert result_fail_open == result_1
        print("Fail-Open Verified: System proceeded despite Redis error.")
    except Exception as e:
        print(f"[FAIL] Fail-Open failed. Exception raised: {e}")
        raise
    finally:
        # Restore
        mock_redis_instance.get = original_get


    # 7. Test Max Size Limit
    print("\n[Test 5] Max Size Limit Scenario")
    # Patch the constant to a very small value
    with patch("packages.imh_session.infrastructure.redis_prompt_repository.MAX_PROMPT_CACHE_SIZE_BYTES", 10):
        # Generate a prompt that is definitely larger than 10 bytes
        ctx_large = ctx_a.copy()
        ctx_large["input_data"] = {"user_msg": "This prompt is definitely larger than 10 bytes"}
        
        # Clear mock store to be sure
        mock_redis_instance.store = {}
        
        result_large = composer.compose_prompt(ctx_large)
        print(f"Result (Large): {result_large[:50]}...")
        
        # Check if saved to Redis
        # Since size > 10, it should NOT be in store (Prompt keys start with "prompt:")
        prompt_keys = [k for k in mock_redis_instance.store.keys() if k.startswith("prompt:")]
        if not prompt_keys:
            print("Max Size Limit Verified: Large prompt NOT saved to cache.")
        else:
            print(f"[FAIL] Large prompt saved to cache! Keys: {prompt_keys}")
            raise Exception("Max Size Limit Failed")

    # 8. Test Stampede Protection (Locking)
    print("\n[Test 6] Stampede Protection Scenario")
    
    # Case A: Leader (Lock acquired) -> Should Save
    mock_redis_instance.store = {}
    print("Testing Leader (Lock Acquired)...")
    result_leader = composer.compose_prompt(ctx_a)
    assert len([k for k in mock_redis_instance.store.keys() if k.startswith("prompt:")]) == 1
    print("Leader Logic Verified: Prompt Saved.")
    
    # Case B: Follower (Lock Busy) -> Should NOT Save
    mock_redis_instance.store = {}
    print("Testing Follower (Lock Busy)...")
    
    # Pre-occupy the lock
    # We need to calculate the key first or just mock set(nx=True) to return False
    original_set = mock_redis_instance.set
    def mock_busy_set(key, value, ex=None, nx=False):
        if key.startswith("lock:"):
            return False # Simulate lock busy
        return True
    
    mock_redis_instance.set = mock_busy_set
    
    result_follower = composer.compose_prompt(ctx_a)
    
    # Check if saved
    prompt_keys_follower = [k for k in mock_redis_instance.store.keys() if k.startswith("prompt:")]
    if not prompt_keys_follower:
         print("Follower Logic Verified: Prompt NOT Saved (Skipped due to lock busy).")
    else:
         print("[FAIL] Follower saved prompt despite lock busy!")
         raise Exception("Stampede Protection Failed")
    
    # Restore set
    mock_redis_instance.set = original_set


    print("\n=== CP4 Verification Success ===")

if __name__ == "__main__":
    asyncio.run(verify_cp4())
