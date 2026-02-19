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

from packages.imh_core.errors import LockAcquisitionError
from packages.imh_service.infra.redis_runtime_store import RedisRuntimeStore
from packages.imh_session.infrastructure.redis_projection_repository import RedisProjectionRepository
from packages.imh_dto.projection import SessionProjectionDTO

class SessionService:
    """
    Application Service for managing interview sessions.
    Responsible for:
    1. Transaction boundaries (Loading/Saving Session)
    2. Concurrency Control (Redis Distributed Lock)
    3. Orchestrating Engine calls
    4. Runtime Mirroring (PG -> Redis)
    5. Projection Optimization (Read-Through)
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
        
        # CP0: Redis Components
        self.concurrency_manager = ConcurrencyManager() 
        self.runtime_store = RedisRuntimeStore()
        
        # CP1: Projection Repository
        self.projection_repo = RedisProjectionRepository()
        
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
        
        # CP0 Hydration Check (If Session exists in PG but missed in Redis?)
        # For now, we only hydrate if needed logic is triggered or explicitly requested.
        # But `_load_session_context` is reading from PG (Source of Truth), so it's fine.
        
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
            qbank_service=self.qbank_service,
            pg_state_repo=self.postgres_state_repo  # TASK-029: PG Hydration
        )
        
        # 3. Start Session (State Transition: APPLIED -> IN_PROGRESS)
        # TASK-030: engine.start_session() now performs Authority First Atomic Commit
        engine.start_session()
        
        # CP1: Invalidate Projection (New Session)
        self.projection_repo.delete(session_id)

        # 4. Return DTO (Context is updated in engine.context)

        # 4. Return DTO (Context is updated in engine.context)
        return SessionMapper.to_dto(engine.context)

    # Updated method signature
    def submit_answer(self, session_id: str, answer_dto: AnswerSubmissionDTO, request_id: Optional[str] = None) -> SessionResponseDTO:
        """
        Handles answer submission with Concurrency Control & Idempotency.
        CP0 Contract:
        - Lock: Fail-Fast if locked.
        - Idempotency: Return cached result if already processed (when request_id provided).
        """
        # 0. Idempotency Check (Before Lock)
        if request_id and self.concurrency_manager.idempotency:
            status, payload = self.concurrency_manager.idempotency.check_request(request_id)
            if status == self.concurrency_manager.idempotency.STATUS_DONE:
                self.logger.info(f"Idempotency hit for request {request_id}")
                return SessionResponseDTO.parse_raw(payload) # Return cached result
            elif status == self.concurrency_manager.idempotency.STATUS_IN_PROGRESS:
                raise LockAcquisitionError(f"Request {request_id} is already in progress.")

        # 1. Acquire Lock (Fail-Fast: Redis Down -> Error)
        with self.concurrency_manager.acquire_lock(session_id):
            
            # 0.5 Mark In-Progress (Inside Lock)
            if request_id and self.concurrency_manager.idempotency:
                 self.concurrency_manager.idempotency.mark_in_progress(request_id)

            try:
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
                    qbank_service=self.qbank_service,
                    pg_state_repo=self.postgres_state_repo  # TASK-029: PG Hydration
                )
                
                # Force context to be the loaded one (Engine does this in init)
    
                # 4. Delegate to Engine (Command)
                # This commits to PG internally
                duration = answer_dto.duration_seconds if answer_dto.duration_seconds else 0.0
                
                engine.process_answer(duration_sec=duration)
                
                # CP0: Mirror Update (Write Order: PG -> Redis)
                # Only executed if Step 4 succeeded (PG Committed)
                self._sync_runtime_mirror(session_id, engine.context)

                # CP1: Invalidate Projection (State Changed)
                self.projection_repo.delete(session_id)
                
                # 5. Return Updated State DTO
                dto = SessionMapper.to_dto(engine.context)
                
                # 6. Save Idempotency Result
                if request_id and self.concurrency_manager.idempotency:
                    self.concurrency_manager.idempotency.save_result(request_id, dto.json())
                    
                return dto
            except Exception:
                # Release Idempotency Lock on Failure so retry is possible
                if request_id and self.concurrency_manager.idempotency:
                    self.concurrency_manager.idempotency.release(request_id)
                raise

    def get_session(self, session_id: str) -> Optional[SessionResponseDTO]:
        """
        Read-Only operation. Bypasses Lock.
        Uses Full DTO (SessionResponseDTO).
        """
        # Use shared helper
        session = self._load_session_context(session_id)
        if not session: 
            return None
        return SessionMapper.to_dto(session)

    def get_session_projection(self, session_id: str) -> Optional[SessionProjectionDTO]:
        """
        CP1: Read Optimization with Redis Projection.
        Strategy: Read-Through (Redis -> Miss -> PG -> Redis).
        """
        # 1. Try Redis
        proj = self.projection_repo.get(session_id)
        if proj:
            return proj
        
        # 2. Miss -> Load from PG (Authority)
        session = self._load_session_context(session_id)
        if not session:
            return None
            
        # 3. Reconstruct
        dto = SessionMapper.to_projection_dto(session)
        
        # 4. Save to Redis (No Lock, Stempede Allowed)
        # Even if multiple threads do this, it's idempotent.
        self.projection_repo.save(dto)
        
        return dto

    def hydrate_session(self, session_id: str) -> bool:
        """
        CP0 Contract: Hydration (Mirror Restoration).
        Read from PG (Source of Truth) -> Overwrite Redis Mirror.
        """
        try:
            # 1. Load from PG (Source of Truth)
            context = self._load_session_context(session_id)
            if not context:
                self.logger.warning(f"Cannot hydrate session {session_id}: Not found in PG")
                return False
            
            # 2. Force Overwrite Redis Mirror
            self._sync_runtime_mirror(session_id, context)
            
            # CP1: Invalidate Projection (Consistency)
            self.projection_repo.delete(session_id)

            self.logger.info(f"Successfully hydrated Redis mirror for session {session_id}")
            return True
        except Exception as e:
            self.logger.error(f"Hydration failed for session {session_id}: {e}")
            return False

    def _sync_runtime_mirror(self, session_id: str, context: "SessionContext"):
        """
        Helper to serialize context and update Redis Mirror.
        """
        if not self.runtime_store:
            return

        # Simple serialization for mirror
        # In real world, use proper schema. Here we dump dict.
        state_dict = context.dict() if hasattr(context, 'dict') else context.__dict__
        self.runtime_store.save_mirror(session_id, state_dict)
