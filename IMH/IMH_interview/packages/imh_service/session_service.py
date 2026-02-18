from typing import Optional
from packages.imh_service.concurrency import ConcurrencyManager
from packages.imh_service.mapper import SessionMapper
from packages.imh_dto.session import SessionResponseDTO, AnswerSubmissionDTO
from packages.imh_session.engine import InterviewSessionEngine
from packages.imh_session.repository import SessionStateRepository, SessionHistoryRepository
from packages.imh_session.dto import SessionConfig
from packages.imh_service.shadow_reader import ShadowReader
import os
import logging
import logging


from packages.imh_job.enums import JobStatus
from packages.imh_service.canary import CanaryManager

class SessionService:
    """
    Application Service for managing interview sessions.
    Responsible for:
    1. Transaction boundaries (Loading/Saving Session)
    2. Concurrency Control (Locking)
    3. Orchestrating Engine calls
    """
    def __init__(
        self, 
        state_repo: SessionStateRepository, 
        history_repo: SessionHistoryRepository, 
        job_repo: "JobPostingRepository",
        question_generator: "QuestionGenerator",
        qbank_service: "QuestionBankService",
        postgres_state_repo: Optional[SessionStateRepository] = None,
        canary_manager: Optional[CanaryManager] = None
    ):
        self.state_repo = state_repo
        self.history_repo = history_repo
        self.job_repo = job_repo
        self.question_generator = question_generator
        self.qbank_service = qbank_service
        self.postgres_state_repo = postgres_state_repo
        self.canary_manager = canary_manager
        self.concurrency_manager = ConcurrencyManager()
        self.logger = logging.getLogger("imh.session_service")

    def _load_session_context(self, session_id: str) -> Optional["SessionContext"]:
        """
        Helper to load session context with Canary Routing and Shadow Read.
        """
        # Determine Primary Repo based on Canary
        primary_repo = self.state_repo
        shadow_repo = self.postgres_state_repo
        
        # Canary Logic
        if self.canary_manager and self.postgres_state_repo and self.canary_manager.check_canary_access(session_id):
            primary_repo = self.postgres_state_repo # Read from Postgres
            shadow_repo = self.state_repo # Shadow from Memory
            self.logger.info(f"Session {session_id} is in canary group. Loading from Postgres.")
            
        session = primary_repo.get_state(session_id)
        
        # Shadow Read
        if shadow_repo:
             # Copy for comparison to avoid race conditions (mutation during comparison)
             # Use model_copy if Pydantic v2, copy if v1
             primary_copy = session.model_copy(deep=True) if hasattr(session, 'model_copy') else session.copy(deep=True) if session else None
             
             ShadowReader.compare(
                primary_result=primary_copy,
                shadow_func=lambda: shadow_repo.get_state(session_id),
                entity_name="Session",
                entity_id=session_id
             )

        return session
    
    def create_session_from_job(self, job_id: str, user_id: str) -> SessionResponseDTO:
        """
        Orchestrates session creation from a Job ID.
        Fetches the Immutable Job Policy Snapshot and initializes the session.
        """
        # 1. Fetch Job Policy (Phase 5: Freeze at Publish)
        job = self.job_repo.find_by_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        # Proper Enum comparison
        if job.status != JobStatus.PUBLISHED:
             raise ValueError(f"Job {job_id} is not currently accepting applicants (Status: {job.status})")

        # 2. Create Snapshot
        policy_snapshot = job.create_session_config().dict()
        
        # 3. Delegate to Internal logic
        return self.create_session(policy_snapshot, user_id)

    def create_session(self, job_policy_snapshot: dict, user_id: str) -> SessionResponseDTO:
        # No lock needed for creation as it's a new resource
        # Phase 5 Contract: Use Job Policy Snapshot
        
        # 1. Prepare Config
        config = SessionConfig(**job_policy_snapshot)
        session_id = f"sess_{user_id}_{int(os.times().elapsed)}" # Simple ID generation for now

        # 2. Create Engine Instance (Loads or Inits context)
        engine = InterviewSessionEngine(
            session_id=session_id,
            config=config,
            state_repo=self.state_repo,
            history_repo=self.history_repo,
            question_generator=self.question_generator,
            qbank_service=self.qbank_service
        )
        
        # 3. Start Session (State Transition: APPLIED -> IN_PROGRESS)
        engine.start_session()

        # 4. Return DTO (Context is updated in engine.context)
        return SessionMapper.to_dto(engine.context)

    def submit_answer(self, session_id: str, answer_dto: AnswerSubmissionDTO) -> SessionResponseDTO:
        """
        Handles answer submission with Concurrency Control.
        """
        # 1. Acquire Lock (Fail-Fast)
        with self.concurrency_manager.acquire_lock(session_id):
            # 2. Load State to check existence
            # 2. Load State (with Routing & Shadow Read)
            context = self._load_session_context(session_id)

            if not context:
                raise ValueError(f"Session {session_id} not found")

            # 3. Instantiate Engine
            # Recreate config from Immutable Job (Phase 5 principle)
            job_id = context.job_id
            job = self.job_repo.find_by_id(job_id)
            if not job:
                 # Critical integrity error if job missing for active session
                 raise ValueError(f"Job {job_id} for session {session_id} not found")

            config = job.create_session_config()

            engine = InterviewSessionEngine(
                session_id=session_id,
                config=config, 
                state_repo=self.state_repo,
                history_repo=self.history_repo,
                question_generator=self.question_generator,
                qbank_service=self.qbank_service
            )
            
            # Force context to be the loaded one (Engine does this in init)

            # 4. Delegate to Engine (Command)
            duration = answer_dto.duration_seconds if answer_dto.duration_seconds else 0.0
            
            engine.process_answer(duration_sec=duration)
            
            # 5. Return Updated State DTO
            return SessionMapper.to_dto(engine.context)

    def get_session(self, session_id: str) -> Optional[SessionResponseDTO]:
        """
        Read-Only operation. Bypasses Lock.
        """
        # Use shared helper
        session = self._load_session_context(session_id)
        if not session: # Changed from 'context' to 'session'
            return None
        return SessionMapper.to_dto(session) # Changed from 'context' to 'session'
