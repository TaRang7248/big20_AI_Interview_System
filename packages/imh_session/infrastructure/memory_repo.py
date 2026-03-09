from typing import Dict, List, Optional
from packages.imh_session.dto import SessionContext
from packages.imh_session.repository import SessionStateRepository
from packages.imh_session.state import SessionStatus

class MemorySessionRepository(SessionStateRepository):
    """
    In-Memory implementation of SessionStateRepository.
    Used for local development and testing (Phase 5).
    Replaces Redis Hot Store.
    """
    def __init__(self):
        self._store: Dict[str, SessionContext] = {}

    def save_state(self, session_id: str, context: SessionContext) -> None:
        self._store[session_id] = context

    def get_state(self, session_id: str) -> Optional[SessionContext]:
        return self._store.get(session_id)

    def update_status(self, session_id: str, status: SessionStatus) -> None:
        if session_id in self._store:
            self._store[session_id].status = status

    def find_by_job_id(self, job_id: str) -> List[SessionContext]:
        """
        Find active sessions by Job ID.
        Iterates through memory store (O(N)). In Redis, this would use a secondary index.
        """
        results = []
        for ctx in self._store.values():
            if hasattr(ctx, 'job_id') and ctx.job_id == job_id:
                results.append(ctx)
        return results
