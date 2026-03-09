import time
import uuid
import logging
from contextlib import contextmanager
from typing import Optional
from packages.imh_core.infra.redis import RedisClient
from packages.imh_core.errors import LockAcquisitionError, RedisConnectionError
import redis

logger = logging.getLogger("imh.service.concurrency")

class IdempotencyGuard:
    """
    Helper for Idempotency Control.
    Status: NEW (0), IN_PROGRESS (1), DONE (2)
    """
    STATUS_NEW = 0
    STATUS_IN_PROGRESS = 1
    STATUS_DONE = 2
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        
    def check_request(self, request_id: str) -> tuple[int, Optional[str]]:
        """
        Checks if request is already processed.
        Returns (status, result_payload).
        """
        key = f"idempotency:{request_id}"
        val = self.redis.get(key)
        
        if val is None:
            return self.STATUS_NEW, None
            
        if val == "PENDING":
            return self.STATUS_IN_PROGRESS, None
            
        # If not pending, it's the result payload
        return self.STATUS_DONE, val

    def mark_in_progress(self, request_id: str, ttl: int = 60):
        key = f"idempotency:{request_id}"
        # NT=True -> Only set if not exists (Lock the request ID)
        if not self.redis.set(key, "PENDING", nx=True, ex=ttl):
             # Already exists (Collision)
             raise LockAcquisitionError(f"Request {request_id} is already in progress.")

    def save_result(self, request_id: str, result_payload: str, ttl: int = 300):
        key = f"idempotency:{request_id}"
        # XX=True -> Only set if exists (we marked it pending)
        # Ideally we just set it.
        self.redis.set(key, result_payload, ex=ttl)

    def release(self, request_id: str):
         self.redis.delete(f"idempotency:{request_id}")

class ConcurrencyManager:
    """
    Manages concurrency: Distributed Lock + Idempotency.
    """
    def __init__(self):
        try:
            self.redis = RedisClient.get_instance()
            self.idempotency = IdempotencyGuard(self.redis) if self.redis else None
        except RedisConnectionError:
            self.redis = None
            self.idempotency = None
            logger.critical("Redis unavailable. Concurrency/Idempotency DISABLED (Fail-Safe: Writes Rejected).")

    @contextmanager
    def acquire_lock(self, resource_id: str, ttl_seconds: int = 30):
        """
        Acquires a distributed lock for the given resource_id.
        """
        if not self.redis:
            raise RedisConnectionError("Redis is down. Cannot acquire lock for write operation.")

        lock_key = f"lock:session:{resource_id}"
        token = str(uuid.uuid4())
        
        try:
            acquired = self.redis.set(lock_key, token, nx=True, ex=ttl_seconds)
        except redis.RedisError as e:
             raise RedisConnectionError(f"Redis error during lock acquisition: {str(e)}") from e

        if not acquired:
            logger.warning(f"Failed to acquire lock for {resource_id}")
            raise LockAcquisitionError(resource_id)

        logger.debug(f"Lock acquired for {resource_id} (token={token})")
        
        try:
            yield
        finally:
            try:
                unlock_script = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("del", KEYS[1])
                else
                    return 0
                end
                """
                self.redis.eval(unlock_script, 1, lock_key, token)
                logger.debug(f"Lock released for {resource_id}")
            except Exception as e:
                logger.error(f"Error releasing lock for {resource_id}: {e}")
