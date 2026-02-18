import logging
import threading
import json
import time
from typing import Any, Callable, Dict, Optional, TypeVar
from dataclasses import dataclass, asdict

# Configure specialized logger for Shadow Read
logger = logging.getLogger("imh.shadow_read")
# Ensure it doesn't propagate if root logger is noisy, or configure specifically
logger.setLevel(logging.INFO)

T = TypeVar('T')

@dataclass
class ShadowConfig:
    enabled: bool = True
    timeout_seconds: float = 0.5  # 500ms max for shadow read
    circuit_breaker_error_threshold: int = 10
    circuit_breaker_reset_seconds: int = 60

class CircuitBreaker:
    def __init__(self, threshold: int, reset_interval: int):
        self.threshold = threshold
        self.reset_interval = reset_interval
        self.failure_count = 0
        self.last_failure_time = 0
        self.is_open = False
        self._lock = threading.Lock()

    def record_failure(self):
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.threshold:
                if not self.is_open:
                    logger.warning("[CircuitBreaker] OPEN: Shadow Read disabled due to high error rate")
                self.is_open = True

    def record_success(self):
        with self._lock:
            if self.is_open:
                logger.info("[CircuitBreaker] CLOSED: Shadow Read re-enabled")
            self.is_open = False
            self.failure_count = 0

    def allow_request(self) -> bool:
        with self._lock:
            if not self.is_open:
                return True
            
            # Check for reset
            elapsed = time.time() - self.last_failure_time
            if elapsed > self.reset_interval:
                # Half-open state conceptually, but we'll just reset for simplicity
                self.is_open = False
                self.failure_count = 0
                logger.info("[CircuitBreaker] RESET: Probing Shadow Read availability")
                return True
            
            return False

class ShadowReader:
    """
    Shadow Reader with Fire-and-Forget isolation.
    Executes PostgreSQL read in a separate thread to ensure 0 impact on Main/Primary response.
    """
    _instance = None
    _config = ShadowConfig()
    _circuit_breaker = CircuitBreaker(_config.circuit_breaker_error_threshold, _config.circuit_breaker_reset_seconds)

    @classmethod
    def compare(cls, 
                primary_result: Any, 
                shadow_func: Callable[[], Any], 
                entity_name: str, 
                entity_id: str):
        """
        Fire-and-forget comparison.
        
        Args:
            primary_result: The data returned from the Primary repository (Source of Truth)
            shadow_func: A callable that executes the PostgreSQL read
            entity_name: 'Session', 'Job', etc.
            entity_id: The ID of the entity
        """
        if not cls._config.enabled:
            return

        if not cls._circuit_breaker.allow_request():
            return

        # Fire and forget thread
        t = threading.Thread(
            target=cls._run_shadow_safe,
            args=(primary_result, shadow_func, entity_name, entity_id),
            daemon=True,
            name=f"ShadowRead-{entity_name}-{entity_id}"
        )
        t.start()

    @classmethod
    def _run_shadow_safe(cls, primary_result: Any, shadow_func: Callable[[], Any], entity_name: str, entity_id: str):
        try:
            start_time = time.time()
            
            # 1. Execute Shadow Read
            # Note: Since we are in a thread, we rely on the repo implementation to handle its own connection/asyncio loop
            # The PostgreSQLRepository in this project uses internal loop.run_until_complete, so it should be fine in a thread
            
            # Enforce timeout logic (soft timeout since we can't kill threads easily in Python)
            # We measure time and log warning if exceeded, but the DB driver should ideally have its own timeout
            shadow_result = shadow_func()
            
            duration = time.time() - start_time
            
            if duration > cls._config.timeout_seconds:
                logger.warning(f"[ShadowRead] TIMEOUT limit exceeded: {duration:.3f}s for {entity_name}/{entity_id}")
                # We don't fail the CB for timeout usually unless strictly configured, but let's count it as potential strain
                # cls._circuit_breaker.record_failure() 
            
            # 2. Compare
            cls._do_compare(primary_result, shadow_result, entity_name, entity_id)
            
            # Success
            cls._circuit_breaker.record_success()

        except Exception as e:
            logger.error(f"[ShadowRead] EXECUTION ERROR for {entity_name}/{entity_id}: {e}")
            cls._circuit_breaker.record_failure()

    @classmethod
    def _do_compare(cls, primary: Any, shadow: Any, entity_name: str, entity_id: str):
        # 1. Handle Miss (Existence mismatch)
        if primary is not None and shadow is None:
            logger.error(f"[ShadowRead] MISMATCH: {entity_name} {entity_id} found in Primary but MISSING in Shadow")
            return
        
        if primary is None and shadow is not None:
             # This might happen if Postgres has stale data not in memory/file (unlikely with dual write) or if primary not found is logical
             logger.warning(f"[ShadowRead] MISMATCH: {entity_name} {entity_id} MISSING in Primary but found in Shadow")
             return

        if primary is None and shadow is None:
            # Both missing - Match
            return

        # 2. Convert to Dict for comparison
        primary_dict = cls._to_dict(primary)
        shadow_dict = cls._to_dict(shadow)

        # 3. Deep Compare
        if primary_dict != shadow_dict:
            cls._log_mismatch(entity_name, entity_id, primary_dict, shadow_dict)
        else:
            # Match
            # logger.debug(f"[ShadowRead] MATCH: {entity_name} {entity_id}")
            pass

    @classmethod
    def _to_dict(cls, obj: Any) -> Dict:
        if hasattr(obj, 'model_dump'):
            # Pydantic v2
            return obj.model_dump(mode='json')
        elif hasattr(obj, 'dict'):
            # Pydantic v1
            return obj.dict()
        elif isinstance(obj, list):
            return [cls._to_dict(item) for item in obj]
        elif isinstance(obj, dict):
            return obj
        else:
            # Best effort or scalar
            return str(obj)

    @classmethod
    def _log_mismatch(cls, entity_name: str, entity_id: str, p_data: Dict, s_data: Dict):
        # Flatten and compare keys
        all_keys = set(p_data.keys()) | set(s_data.keys())
        diffs = []
        
        for key in all_keys:
            p_val = p_data.get(key)
            s_val = s_data.get(key)
            
            if p_val != s_val:
                # Mask strict PII if necessary. 
                # For this system, we focus on identifying the field.
                # We'll hash values or truncate string length for safety.
                diffs.append(f"{key}: Primary='{cls._mask(p_val)}' vs Shadow='{cls._mask(s_val)}'")

        logger.error(f"[ShadowRead] CONTENT MISMATCH for {entity_name} {entity_id}: {', '.join(diffs[:5])}...")

    @classmethod
    def _mask(cls, val: Any) -> str:
        s_val = str(val)
        if len(s_val) > 20:
            return s_val[:10] + "..." + s_val[-5:]
        return s_val
