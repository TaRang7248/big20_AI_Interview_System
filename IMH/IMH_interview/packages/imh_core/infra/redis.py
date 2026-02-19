import redis
from packages.imh_core.config import IMHConfig
from packages.imh_core.errors import RedisConnectionError, ConfigurationError
import logging

logger = logging.getLogger("imh.infra.redis")

class RedisClient:
    _instance = None
    _client: redis.Redis = None

    @classmethod
    def get_instance(cls) -> redis.Redis:
        if cls._client is None:
            cls._connect()
        return cls._client

    @classmethod
    def _connect(cls):
        try:
            config = IMHConfig.load()
            
            # Prioritize REDIS_URL
            if config.REDIS_URL:
                cls._client = redis.from_url(
                    config.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            else:
                cls._client = redis.Redis(
                    host=config.REDIS_HOST,
                    port=config.REDIS_PORT,
                    db=config.REDIS_DB,
                    password=config.REDIS_PASSWORD,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            
            # Ping to verify connection
            cls._client.ping()
            logger.info(f"Connected to Redis at {config.REDIS_HOST}:{config.REDIS_PORT} (DB: {config.REDIS_DB})")

        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise RedisConnectionError(f"Cannot connect to Redis: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected Redis initialization error: {e}")
            raise RedisConnectionError(f"Redis init failed: {str(e)}") from e

    @classmethod
    def close(cls):
        if cls._client:
            cls._client.close()
            cls._client = None
