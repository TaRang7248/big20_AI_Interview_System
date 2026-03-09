import json
import logging
from typing import Optional, Dict, Any
from packages.imh_core.infra.redis import RedisClient
from packages.imh_core.errors import RedisConnectionError

logger = logging.getLogger("imh.service.runtime_store")

class RedisRuntimeStore:
    """
    Manages Runtime State Mirroring in Redis.
    CP0 Contract:
    - No Write-Back (PG is source of truth).
    - Writes are MIRROR UPDATES only (after PG commit).
    - TTL based on Session Timeout.
    """
    SESSION_TTL = 1800 # 30 minutes

    def __init__(self):
        try:
            self.redis = RedisClient.get_instance()
        except RedisConnectionError:
            self.redis = None # Fail-Safe mode (but logs error)
            logger.error("Redis unreachable. Runtime Mirroring is disabled.")

    def save_mirror(self, session_id: str, state_data: Dict[str, Any]):
        """
        Mirror Update: Overwrite Redis key with latest PG state.
        This must be called AFTER PG Commit interaction.
        """
        if not self.redis:
            logger.warning(f"Skipping Redis mirror update for {session_id} (Redis Down)")
            return

        key = f"session:runtime:{session_id}"
        try:
            # Serialize
            # Assuming state_data is JSON serializable dict
            # If it contains datetime, we need a custom encoder or convert before passing
            # For CP0, we assume DTO-like dictionary.
            payload = json.dumps(state_data, default=str)
            
            # SET with TTL
            self.redis.set(key, payload, ex=self.SESSION_TTL)
            logger.debug(f"Updated Runtime Mirror for {session_id}")
            
        except Exception as e:
            # CP0 Contract: Redis Failure should NOT fail the request (Fail-Open for Mirroring?)
            # Wait, CP0 Plan says: "1. PG Commit Success / Redis Fail -> Success (Client sees success)"
            # So we catch and log error, preventing exception propagation.
            logger.error(f"Failed to update Redis mirror for {session_id}: {e}")

    def get_mirror(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Read from Redis Mirror.
        """
        if not self.redis:
            return None
        
        key = f"session:runtime:{session_id}"
        try:
            data = self.redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to read Redis mirror for {session_id}: {e}")
            return None
