from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Optional
import logging

from packages.imh_session.repository import SessionStateRepository
from packages.imh_core.config import IMHConfig

class TTLContext(BaseModel):
    """
    Context for Dynamic TTL Calculation.
    Decouples Infrastructure details from the Caching Strategy.
    """
    active_candidates: int = 0
    is_debug: bool = False
    model_cost_high: bool = False

class TTLContextResolver(ABC):
    @abstractmethod
    def resolve(self, job_id: str) -> TTLContext:
        pass

class PostgresTTLResolver(TTLContextResolver):
    """
    Resolves TTL Context using PostgreSQL Authority (SessionStateRepository).
    Guarantees that 'Active Candidates' count comes from the Source of Truth.
    """
    def __init__(self, state_repo: SessionStateRepository):
        self.state_repo = state_repo
        self.logger = logging.getLogger("imh.ttl_resolver")
        # Ensure we have access to config for debug flag
        try:
            self.config = IMHConfig.load()
        except Exception:
            self.config = None # Fallback

    def resolve(self, job_id: str) -> TTLContext:
        is_debug = False
        active_count = 0
        
        # 1. Resolve Debug Mode
        if self.config:
            is_debug = self.config.DEBUG

        # 2. Resolve Active Candidates (Authority Query)
        try:
            # find_by_job_id returns list of active sessions
            active_sessions = self.state_repo.find_by_job_id(job_id)
            active_count = len(active_sessions)
        except Exception as e:
            # Safe Fallback: Log warning and assume 0 to use Default TTL
            self.logger.warning(f"Failed to resolve active candidates for job {job_id}: {e}")
            active_count = 0
            
        return TTLContext(
            active_candidates=active_count,
            is_debug=is_debug,
            model_cost_high=False # Placeholder for future logic
        )
