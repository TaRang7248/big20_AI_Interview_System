import logging
from typing import List, Optional

from packages.imh_session.repository import SessionStateRepository
from packages.imh_session.dto import SessionContext
from packages.imh_session.state import SessionStatus

logger = logging.getLogger("imh.dual_write")

class DualSessionStateRepository(SessionStateRepository):
    """
    Dual Write Reservoir for Session State.
    Writes to both Primary (Memory) and Secondary (PostgreSQL).
    Reads from Primary only.
    Essential for Checkpoint 4 Shadow Read verification.
    """
    def __init__(self, primary: SessionStateRepository, secondary: SessionStateRepository):
        self.primary = primary
        self.secondary = secondary

    def save_state(self, session_id: str, context: SessionContext) -> None:
        # 1. Write to Primary (Source of Truth)
        self.primary.save_state(session_id, context)
        
        # 2. Write to Secondary (Shadow/Dual)
        try:
            self.secondary.save_state(session_id, context)
        except Exception as e:
            # Fallback as Anomaly Signal - Do not block main flow
            logger.error(f"[DualWrite] Failed to save state to Secondary for {session_id}: {e}")
            # In Phase 4.3, we might want to track this metric or even fail if strict consistency is required

    def get_state(self, session_id: str) -> Optional[SessionContext]:
        # Read from Primary
        return self.primary.get_state(session_id)

    def update_status(self, session_id: str, status: SessionStatus) -> None:
        self.primary.update_status(session_id, status)
        try:
            self.secondary.update_status(session_id, status)
        except Exception as e:
            logger.error(f"[DualWrite] Failed to update status in Secondary for {session_id}: {e}")

    def find_by_job_id(self, job_id: str) -> List[SessionContext]:
        return self.primary.find_by_job_id(job_id)
