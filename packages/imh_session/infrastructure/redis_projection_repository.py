import json
import logging
from typing import Optional
from packages.imh_core.infra.redis import RedisClient
from packages.imh_core.errors import RedisConnectionError
from packages.imh_dto.projection import SessionProjectionDTO

logger = logging.getLogger("imh.session.infrastructure.redis_projection")

class RedisProjectionRepository:
    """
    CP1: Redis-based Session Projection Repository.
    Handles Read/Write/Delete of SessionProjectionDTO.
    
    Authority Contract:
    - This is a VIEW ONLY.
    - NO WRITE-BACK to Postgres.
    - Redis Down -> Log Warning & Return None (Graceful Degradation).
    - Stampede Strategy: No Lock (Allow redundant writes).
    """
    
    # Prefix for Projection Keys
    KEY_PREFIX = "proj:session"
    TTL_SECONDS = 1800 # 30 minutes

    def __init__(self):
        try:
            self.redis = RedisClient.get_instance()
        except RedisConnectionError:
            self.redis = None
            logger.warning("Redis unreachable. Projection Cache is disabled.")

    def _get_key(self, session_id: str) -> str:
        return f"{self.KEY_PREFIX}:{session_id}"

    def get(self, session_id: str) -> Optional[SessionProjectionDTO]:
        """
        Try to get projection from Redis.
        Returns None on Miss or Redis Error.
        """
        if not self.redis:
            return None
        
        try:
            data = self.redis.get(self._get_key(session_id))
            if data:
                return SessionProjectionDTO.parse_raw(data)
            return None
        except Exception as e:
            logger.warning(f"Failed to read projection for {session_id}: {e}")
            return None

    def save(self, projection: SessionProjectionDTO):
        """
        Save projection to Redis with TTL.
        Stempede Strategy: No Lock (Last Write Wins).
        """
        if not self.redis:
            return
        
        try:
            self.redis.set(
                self._get_key(projection.session_id),
                projection.json(),
                ex=self.TTL_SECONDS
            )
        except Exception as e:
            logger.warning(f"Failed to save projection for {projection.session_id}: {e}")

    def delete(self, session_id: str):
        """
        Invalidate projection.
        Strategy: Invalidate First (DEL).
        """
        if not self.redis:
            return
            
        try:
            self.redis.delete(self._get_key(session_id))
        except Exception as e:
            logger.warning(f"Failed to delete projection for {session_id}: {e}")
