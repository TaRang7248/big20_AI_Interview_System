from functools import lru_cache
from typing import Optional
from packages.imh_session.infrastructure.postgresql_repo import PostgreSQLSessionRepository
from packages.imh_service.canary import CanaryManager

from packages.imh_core.config import IMHConfig
from packages.imh_job.repository import JobPostingRepository, MemoryJobPostingRepository
from packages.imh_job.postgresql_repository import PostgreSQLJobRepository
from packages.imh_session.infrastructure.memory_repo import MemorySessionRepository
from packages.imh_session.infrastructure.dual_repo import DualSessionStateRepository
from packages.imh_session.repository import SessionStateRepository, SessionHistoryRepository
from packages.imh_history.repository import FileHistoryRepository
from packages.imh_history.postgresql_repository import PostgreSQLHistoryRepository
from packages.imh_service.concurrency import ConcurrencyManager
from packages.imh_service.session_service import SessionService
from packages.imh_service.admin_query import AdminQueryService

# --- Providers (External Adapters) ---

from packages.imh_qbank.repository import JsonFileQuestionRepository
from packages.imh_qbank.redis_repository import RedisCandidateRepository
from packages.imh_qbank.cached_repository import CachedQuestionRepository
from packages.imh_qbank.repository_interface import QuestionRepository
from packages.imh_qbank.service import QuestionBankService
from packages.imh_providers.question import QuestionGenerator, LLMQuestionGenerator
from packages.imh_providers.mock_question import MockQuestionGenerator
import os

# --- Providers (External Adapters) ---

@lru_cache
def get_config() -> IMHConfig:
    return IMHConfig.load()

@lru_cache
def get_llm_provider() -> "ILLMProvider":
    """
    Singleton LLM Provider Factory (TASK-032).
    Instantiates Ollama, OpenAI, or Mock based on configuration.
    """
    config = get_config()
    provider_type = config.ACTIVE_LLM_PROVIDER.upper()
    
    if provider_type == "OLLAMA":
        from packages.imh_providers.llm.ollama import OllamaLLMProvider
        return OllamaLLMProvider(model_name=config.OLLAMA_MODEL)
    elif provider_type == "OPENAI":
        from packages.imh_providers.llm.openai import OpenAILLMProvider
        return OpenAILLMProvider(model_name=config.OPENAI_MODEL)
    else:
        from packages.imh_providers.llm.mock import MockLLMProvider
        return MockLLMProvider(config=config)


@lru_cache
def get_question_generator() -> QuestionGenerator:
    """
    Singleton Question Generator.
    TASK-032: Returns a real generator backed by the configured LLM provider.
    """
    provider = get_llm_provider()
    return LLMQuestionGenerator(provider=provider)

# --- Repositories (Persistence) ---

@lru_cache
def get_job_posting_repository() -> JobPostingRepository:
    """
    Singleton Job Repository (PostgreSQL).
    Uses DB-backed repository so jobs created via the API are visible to SessionService.
    """
    config = get_config()
    import re
    cs = config.POSTGRES_CONNECTION_STRING or ""
    m = re.match(r"postgresql(?:\+asyncpg)?://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", cs)
    if m:
        u, p, h, port, db = m.groups()
        conn_config = dict(host=h, port=int(port), user=u, password=p, database=db)
    else:
        conn_config = dict(host="localhost", port=5432, user="postgres", password="postgres", database="imh_db")
    return PostgreSQLJobRepository(conn_config=conn_config)

@lru_cache
def get_memory_session_state_repository() -> SessionStateRepository:
    """
    Singleton Memory Session Repository.
    Cached separately to persist across Config reloads (unless explicitly cleared).
    """
    return MemorySessionRepository()

@lru_cache
def get_session_state_repository() -> SessionStateRepository:
    """
    Singleton Session State Repository (Memory/Redis/Dual).
    Must be shared across requests to maintain state.
    """
    primary = get_memory_session_state_repository()
    secondary = get_postgres_session_state_repository()
    
    config = get_config()
    
    if secondary:
        if config.WRITE_PATH_PRIMARY == "POSTGRES":
            # Stage 3: Write Primary = Postgres, Secondary = Memory
            return DualSessionStateRepository(primary=secondary, secondary=primary)
        else:
            # Stage 2: Write Primary = Memory, Secondary = Postgres
            return DualSessionStateRepository(primary=primary, secondary=secondary)
        
    return primary

@lru_cache
def get_session_history_repository() -> SessionHistoryRepository:
    """
    Singleton History Repository (PostgreSQL Authority).
    TASK-029: FileHistoryRepository replaced by PostgreSQLHistoryRepository.
    Fallback to FileHistoryRepository if PG is not configured.
    """
    config = get_config()
    if config.POSTGRES_CONNECTION_STRING:
        dsn = config.POSTGRES_CONNECTION_STRING.replace("postgresql+asyncpg://", "postgresql://")
        return PostgreSQLHistoryRepository(conn_config={'dsn': dsn})
    # Fallback for local dev without PG
    return FileHistoryRepository()

@lru_cache
def get_question_repository() -> QuestionRepository:
    """
    Singleton Question Bank Repository (File-based).
    """
    # Hardcoded path for now, should be in config
    base_dir = os.path.join(os.getcwd(), "data", "qbank")
    file_path = os.path.join(base_dir, "questions.json")
    
    # CP3: Cached Repository Pattern
    # Source: File (JSON)
    # Cache: Redis (Candidate Pool)
    source_repo = JsonFileQuestionRepository(file_path=file_path)
    redis_repo = RedisCandidateRepository()
    
    return CachedQuestionRepository(source_repository=source_repo, redis_repository=redis_repo)

# --- Domain Services (Application Logic) ---

@lru_cache
def get_question_bank_service() -> QuestionBankService:
    """
    Singleton Question Bank Service.
    """
    return QuestionBankService(repository=get_question_repository())

@lru_cache
def get_postgres_session_state_repository() -> Optional[SessionStateRepository]:
    """
    Singleton PostgreSQL Session Repository (Shadow).
    Returns None if connection string is not configured.
    """
    config = get_config()
    if not config.POSTGRES_CONNECTION_STRING:
        return None
        
    # Sanitize DSN: asyncpg does not support '+asyncpg' scheme
    dsn = config.POSTGRES_CONNECTION_STRING.replace("postgresql+asyncpg://", "postgresql://")
    
    # Use dsn for asyncpg connection
    return PostgreSQLSessionRepository(conn_config={'dsn': dsn})

@lru_cache
def get_canary_manager() -> CanaryManager:
    """
    Singleton Canary Manager.
    """
    config = get_config()
    return CanaryManager(default_percentage=config.CANARY_ROLLOUT_PERCENTAGE)

def get_session_service() -> SessionService:
    """
    Transient Session Service.
    """
    return SessionService(
        state_repo=get_session_state_repository(),
        history_repo=get_session_history_repository(),
        job_repo=get_job_posting_repository(),
        question_generator=get_question_generator(),
        qbank_service=get_question_bank_service(),
        postgres_state_repo=get_postgres_session_state_repository(),
        canary_manager=get_canary_manager()
    )

def get_admin_query_service() -> AdminQueryService:
    """
    Transient Admin Query Service.
    Reads from standard Repositories (Read-Only Logic internal to Service).
    """
    return AdminQueryService(
        repository=get_session_state_repository(),
        job_repo=get_job_posting_repository(),
        postgres_repo=get_postgres_session_state_repository()
    )
