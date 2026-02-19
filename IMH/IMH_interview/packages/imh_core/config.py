from pydantic_settings import BaseSettings, SettingsConfigDict
from packages.imh_core.errors import ConfigurationError

class IMHConfig(BaseSettings):
    """
    애플리케이션 전역 설정 클래스.
    .env 파일에서 환경 변수를 로드합니다.
    """
    # 기본 설정 (필요에 따라 필드 추가)
    PROJECT_NAME: str = "IMH AI Interview"
    VERSION: str = "0.1.0"
    
    # 예시: 필수 환경 변수가 있다면 여기에 정의 (Optional이 아니면 에러 발생)
    # OPENAI_API_KEY: str 
    
    # Checkpoint 3/4: PostgreSQL Connection String
    POSTGRES_CONNECTION_STRING: str = None 
    
    # Checkpoint 4: Canary Rollout
    CANARY_ROLLOUT_PERCENTAGE: int = 1 

    # TASK-027: Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = None
    # If provided, REDIS_URL takes precedence
    REDIS_URL: str = None

    # Stage 3: Write Path Switch
    WRITE_PATH_PRIMARY: str = "MEMORY" # MEMORY or POSTGRES
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # 정의되지 않은 환경변수는 무시
    )

    @classmethod
    def load(cls) -> "IMHConfig":
        """
        설정을 로드하고 에러 발생 시 커스텀 예외로 래핑합니다.
        """
        try:
            return cls()
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {str(e)}") from e
