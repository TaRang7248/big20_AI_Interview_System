import logging
from typing import Optional
from .state import SessionStatus, SessionEvent, TerminationReason
from .dto import SessionConfig, SessionContext, SessionQuestion, SessionQuestionType, SessionStepType
from .policy import get_policy, InterviewMode
from .repository import SessionStateRepository, SessionHistoryRepository
from packages.imh_providers.question import QuestionGenerator
from packages.imh_qbank.service import QuestionBankService
try:
    from packages.imh_core.wiring_flags import WiringFlags  # TASK-035
except ModuleNotFoundError:
    try:
        import sys as _sys
        import os as _os
        _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", ".."))
        from packages.imh_core.wiring_flags import WiringFlags  # TASK-035
    except Exception:
        class WiringFlags:  # type: ignore
            @classmethod
            def weight_sync_active(cls): return False
            @classmethod
            def phase_active(cls): return False
            @classmethod
            def fixed_q_active(cls): return False
from .phase_manager import PhaseManager                 # TASK-035
import uuid
import random

# Logger setup
logger = logging.getLogger("imh.session")

class InterviewSessionEngine:
    """
    Core Logic for Interview Session.
    Orchestrates state transitions and policy enforcement.
    Strict compliance with TASK-017_PLAN.md & TASK-025_PLAN.md.
    """
    def __init__(
        self,
        session_id: str,
        config: SessionConfig,
        state_repo: SessionStateRepository,
        history_repo: SessionHistoryRepository,
        question_generator: QuestionGenerator,
        qbank_service: QuestionBankService,
        pg_state_repo: Optional[SessionStateRepository] = None  # TASK-029: PG Authority for Hydration
    ):
        self.session_id = session_id
        self.config = config
        self.state_repo = state_repo
        self.history_repo = history_repo
        self.question_generator = question_generator
        self.qbank_service = qbank_service
        # PostgreSQL Authority Repository (Required for TASK-030)
        self.pg_authority_repo = pg_state_repo

        # Initialize Policy
        self.policy = get_policy(self.config.mode)

        # TASK-035: PhaseManager (guarded by WIRING_PHASE_ENABLED)
        if WiringFlags.phase_active():
            self._phase_manager = PhaseManager(
                main_question_n=self.config.total_question_limit,
                tail_question_limit=2,
            )
        else:
            self._phase_manager = None

        # Initialize or load context
        self.context = self._load_or_initialize_context()

    def _load_or_initialize_context(self) -> SessionContext:
        """
        Load from Hot Storage (Redis/Memory). On miss, Hydrate from PG Authority.
        TASK-029: Redis Miss -> PG Hydration guarantees PostgreSQL as Authority.
        """
        # 1. Try Hot Storage (Redis/Memory - fast path)
        existing = self.state_repo.get_state(self.session_id)
        if existing:
            return existing

        # 2. Hot Storage Miss: Try PG Authority (Hydration)
        if self.pg_authority_repo is not None:
            try:
                pg_context = self.pg_authority_repo.get_state(self.session_id)
                if pg_context:
                    logger.info(
                        "Hydration: Restored session %s from PostgreSQL Authority.",
                        self.session_id
                    )
                    # Mirror to Hot Storage after PG success (TASK-030 Flow)
                    try:
                        self.state_repo.save_state(self.session_id, pg_context)
                    except Exception as me:
                        logger.warning(f"Hydration Mirror failed: {me}. (Availability issue only)")
                    return pg_context
            except Exception as e:
                logger.warning(
                    "Hydration failed for session %s: %s. Initializing fresh context.",
                    self.session_id, e
                )

        # 3. No existing data anywhere: create new context
        logger.info("No existing state found for session %s. Initializing fresh context.", self.session_id)
        return SessionContext(
            session_id=self.session_id,
            job_id=self.config.job_id or "UNKNOWN",
            status=SessionStatus.APPLIED
        )


    def _get_next_question(self) -> SessionQuestion:
        """
        TASK-032 / TASK-025: Determine the next question using RAG -> Fallback strategy.
        TASK-035: PhaseManager flow + Fixed Question injection wiring.
        Strict Immutable Rule: Engine decides source.
        Deduplication rule applied via history injection.
        """
        # 1. Prepare Context for Generator
        history_contents = [q.content for q in self.context.question_history]
        used_ids = [q.id for q in self.context.question_history]
        current_step = self.context.current_step
        total_steps = self.config.total_question_limit

        # ── TASK-035: Phase step-type assignment (flag-gated) ──────────.
        assigned_step_type = SessionStepType.MAIN  # default (legacy path)
        if WiringFlags.phase_active() and self._phase_manager:
            assigned_step_type = self._phase_manager.get_step_type(
                step_index=current_step - 1,   # convert 1-based step to 0-based index
                total_steps=total_steps,
            )

        # ── TASK-035: Fixed Question injection (last MAIN slot, flag-gated) ─────
        if WiringFlags.fixed_q_active() and assigned_step_type == SessionStepType.MAIN:
            fixed_text = self._resolve_fixed_question(current_step, total_steps)
            if fixed_text is not None:
                logger.info("[FixedQ] Serving fixed_question verbatim at step %s", current_step)
                return SessionQuestion(
                    id=str(uuid.uuid4()),
                    content=fixed_text,
                    source_type=SessionQuestionType.STATIC,
                    source_metadata={"bank_id": "fixed"},
                    step_type=SessionStepType.MAIN,
                    question_relaxed=True,
                )
        # ────────────────────────────────────────────────────────────

        gen_context = {
            "job_id": self.context.job_id,
            "step": current_step + 1,
            "question_history": history_contents,
            # TASK-035: Resume Summary injection (passed to generator)
            "resume_summary": self.context.resume_summary if WiringFlags.phase_active() else None,
            "step_type": assigned_step_type,
        }

        # 2. Try RAG Generation (Primary Strategy - Tier 1)
        try:
            # Check policy or config if we should even try RAG (Optional, for now assume yes)
            result = self.question_generator.generate_question(gen_context)

            if result.success:
                logger.info(f"RAG Generation Success for session {self.session_id}")
                return SessionQuestion(
                    id=str(uuid.uuid4()),
                    content=result.content,
                    source_type=SessionQuestionType.GENERATED,
                    source_metadata=result.metadata,
                    step_type=assigned_step_type,
                )
            else:
                logger.warning("RAG Generation Failed: %s. Triggering Fallback.", result.error)
        except Exception as e:
            logger.error("RAG Generation Exception: %s. Triggering Fallback.", e)

        # 3. Fallback to Static QBank (Secondary Strategy - Tier 2)
        # Fetch candidates
        candidates = self.qbank_service.get_candidates(
            tags=["BEHAVIORAL"]
        )

        # TASK-032: Deduplicate from Fallback Candidates
        available_candidates = [c for c in candidates if c.id not in used_ids]

        if not available_candidates:
             # Critical Failure: Safe Fallback Set (Tier 3 - Emergency)
             logger.error("CRITICAL: Static QBank Empty or Exhausted! Using Emergency Question.")

             emergencies = [
                 "Please introduce yourself and your key strengths.",
                 "What is your biggest weakness and how are you overcoming it?",
                 "Describe a time you faced a significant challenge at work.",
                 "Where do you see yourself in 5 years?"
             ]

             emergency_content = next((eq for eq in emergencies if eq not in history_contents), emergencies[0])

             return SessionQuestion(
                 id=f"emergency-fallback-{uuid.uuid4()}",
                 content=emergency_content,
                 source_type=SessionQuestionType.STATIC,
                 source_metadata={"note": "Emergency Fallback"},
                 step_type=assigned_step_type,
             )

        # Select one random candidate from the unused pool
        selected = random.choice(available_candidates)
        return SessionQuestion(
            id=selected.id,
            content=selected.content,
            source_type=SessionQuestionType.STATIC,
            source_metadata={"bank_id": selected.id, "tags": selected.tags},
            step_type=assigned_step_type,
        )

    def _resolve_fixed_question(self, current_step: int, total_steps: int) -> Optional[str]:
        """
        TASK-035: Resolve fixed_question text for the last MAIN slot.
        Returns the verbatim question text, or None if not applicable.
        Priority: job_policy_snapshot.fixed_question > session_config_snapshot.fixed_question
        Insertion: only at the last MAIN slot (step == total_steps - 1, i.e. the step before CLOSING).
        """
        # Last MAIN slot = second-to-last step (total_steps - 1 is CLOSING index 0-based)
        last_main_step = total_steps - 1  # 1-based: step N-1
        if current_step != last_main_step:
            return None

        snap = self.context.job_policy_snapshot or {}
        fixed_text = snap.get("fixed_question")
        if not fixed_text:
            snap2 = self.context.session_config_snapshot or {}
            fixed_text = snap2.get("fixed_question")
        if not fixed_text:
            logger.warning("[FixedQ] fixed_question not found in job_policy_snapshot or session_config_snapshot.")
        return fixed_text or None

    def start_session(self):
        """Transition from APPLIED to IN_PROGRESS."""
        if self.context.status != SessionStatus.APPLIED:
            logger.warning("Session %s cannot start from %s", self.session_id, self.context.status)
            return
        
        logger.info("Starting session %s", self.session_id)
        self._update_status(SessionStatus.IN_PROGRESS)
        self.context.current_step = 1
        
        # Prepare First Question
        next_q = self._get_next_question()
        self.context.current_question = next_q
        self.context.question_history.append(next_q)
        
        # TASK-030: Single Atomic Commit (Authority -> Mirror)
        self._atomic_commit()

    def process_answer(self, duration_sec: float):
        """
        Trigger 1: User clicked 'Answer Completed'.
        """
        self._complete_current_step(is_no_answer=False, termination_trigger="USER_ACTION")

    def handle_silence_timeout(self, is_no_answer: bool):
        """
        Trigger 3: Silence Timeout.
        Policy: 
          - Post-Answer Silence -> is_no_answer=False
          - No-Answer Silence -> is_no_answer=True
        """
        logger.info(f"Silence timeout for {self.session_id}. No Answer: {is_no_answer}")
        
        # Policy: Must emit SILENCE_TIMEOUT event (Log for now, in real impl transmit to socket)
        # Note: warning event should have been emitted by client/socket layer BEFORE calling this.
        # But engine must record it.
        
        self._complete_current_step(is_no_answer=is_no_answer, termination_trigger="SILENCE_TIMEOUT")

    def handle_question_timeout(self):
        """
        Trigger 2: Question Time Limit Exceeded.
        """
        logger.warning(f"Question timeout for {self.session_id}")
        self._complete_current_step(is_no_answer=False, termination_trigger="QUESTION_TIMEOUT") # Treat as answer given but cut off? 
        # Policy doesn't explicitly say if timeout is no-answer. 
        # Usually implies partial answer. Let's assume is_no_answer=False unless specified otherwise.

    def _complete_current_step(self, is_no_answer: bool, termination_trigger: str):
        """
        Internal: Finalize the current step/question.
        """
        if self.context.status != SessionStatus.IN_PROGRESS:
            logger.error(f"Cannot complete step in status {self.context.status}")
            return

        # 1. Update counters
        self.context.completed_questions_count += 1
        
        # 2. Log/Record Step (In real logic, we'd save the actual Q&A text here)
        logger.info(f"Step {self.context.current_step} completed. Trigger: {termination_trigger}, NoAns: {is_no_answer}")
        
        # 3. Request Asynchronous Evaluation (Placeholder - TASK-011/012 interaction)
        # self.eval_engine.evaluate_async(...)
        
        # 4. Check Termination Conditions
        config = self.config
        current_completed = self.context.completed_questions_count
        
        # Condition 1: Total questions reached
        if current_completed >= config.total_question_limit:
            self.terminate_session(TerminationReason.MAX_QUESTIONS_REACHED)
            return

        # Condition 2: Early Exit
        # Policy Check: Requires Min Questions?
        can_check_early_exit = True
        if self.policy.requires_min_questions_for_early_exit():
            if current_completed < config.min_question_count:
                can_check_early_exit = False
                
        if can_check_early_exit:
            if self._check_early_exit_signal():
                self.terminate_session(TerminationReason.EARLY_EXIT_SIGNAL)
                return

        # Prepare Next Step
        self.context.current_step += 1
        
        # Fetch Next Question
        next_q = self._get_next_question()
        self.context.current_question = next_q
        self.context.question_history.append(next_q)
        
        # TASK-030: Single Atomic Commit
        self._atomic_commit()

    def _check_early_exit_signal(self) -> bool:
        """
        Check if Evaluation Layer has sent an early exit signal.
        For Plan/Verification, we check the flag in context.
        """
        return self.context.early_exit_signaled

    def terminate_session(self, reason: TerminationReason):
        """
        Transition to COMPLETED.
        TASK-035: Runtime Assertion for Phase Flow contract (flag-gated).
        """
        # ── TASK-035: Runtime Assertion ─────────────────────────────────
        if WiringFlags.phase_active():
            history = self.context.question_history
            main_count = sum(
                1 for q in history if getattr(q, "step_type", None) == SessionStepType.MAIN
            )
            first_type = getattr(history[0], "step_type", None) if history else None
            last_type = getattr(history[-1], "step_type", None) if history else None
            n = self.context.main_question_n or self.config.total_question_limit

            if main_count != n:
                logger.critical(
                    "[PhaseAssertion] MAIN count mismatch: expected %s, got %s. Aborting.",
                    n, main_count,
                )
                return  # Abort state transition
            if first_type != SessionStepType.OPENING:
                logger.critical("[PhaseAssertion] First step is not OPENING (%s). Aborting.", first_type)
                return
            if last_type != SessionStepType.CLOSING:
                logger.critical("[PhaseAssertion] Last step is not CLOSING (%s). Aborting.", last_type)
                return
        # ────────────────────────────────────────────────────────────
        logger.info("Terminating session %s. Reason: %s", self.session_id, reason)
        self._update_status(SessionStatus.COMPLETED)

        # Final Authority Commit (Status and History)
        self._atomic_commit()

    def interrupt_session(self, reason: TerminationReason):
        """
        Transition to INTERRUPTED.
        """
        logger.warning("Interrupting session %s. Reason: %s", self.session_id, reason)
        self._update_status(SessionStatus.INTERRUPTED)
        
        self._finalize_persistence()
        self._atomic_commit()

    def abort_session(self, reason: TerminationReason):
        """
        Final Terminal State for system/audio failures. (Phase 3-FIX-C2)
        Does NOT trigger evaluation.
        """
        logger.error("Aborting session %s. Reason: %s", self.session_id, reason)
        self._update_status(SessionStatus.ABORTED)
        
        # Save aggregated results without evaluation
        self.history_repo.save_interview_result(self.session_id, {
            "final_status": SessionStatus.ABORTED,
            "completed_questions": self.context.completed_questions_count,
            "abort_reason": reason
        })
        
        self._atomic_commit()

    def resume_session(self):
        """
        Attempt to resume an INTERRUPTED session.
        Allowed only if Policy permits.
        """
        if self.context.status != SessionStatus.INTERRUPTED:
             logger.warning("Cannot resume session %s from %s", self.session_id, self.context.status)
             return

        if not self.policy.can_resume_from_interruption():
            logger.error("Policy Violation: Cannot resume session %s in %s mode.", self.session_id, self.policy.mode)
            return

        logger.info("Resuming session %s", self.session_id)
        self._update_status(SessionStatus.IN_PROGRESS)
        self._atomic_commit()

    def _update_status(self, new_status: SessionStatus):
        """
        TASK-030: Memory-only status update. 
        Persistence is deferred to _atomic_commit.
        """
        self.context.status = new_status
        logger.debug("[Engine] Memory status updated: %s", new_status)

    def _atomic_commit(self):
        """
        Authority Enforcement Contract (TASK-030):
        1. PostgreSQL (Authority) First
        2. Hot Storage (Mirror) Second
        """
        # --- Stage 1: PostgreSQL Authority Enforcement ---
        if self.pg_authority_repo:
            try:
                # 1.1 Persist full context (status, history, etc in one transaction)
                # PostgreSQLSessionRepository.save_state performs this atomically.
                self.pg_authority_repo.save_state(self.session_id, self.context)
                
                # 1.2 Persist status redundantly only if history_repo is different from pg_authority_repo
                # Actually, pg_authority_repo already updated the 'interviews' table.
                # But history_repo might be tracking it separately?
                # For baseline alignment, we also call history_repo.update_interview_status if it's not the same repo instance
                if self.history_repo and self.history_repo != self.pg_authority_repo:
                    self.history_repo.update_interview_status(self.session_id, self.context.status)
                
                logger.info("[Authority] PostgreSQL commit SUCCESS for %s", self.session_id)
            except Exception as e:
                logger.error("[Authority] PostgreSQL commit FAILED for %s: %s", self.session_id, e)
                # Critical Failure: Authority mis-save must block Mirroring
                raise
        else:
            logger.warning("[Authority] No PG Authority repo provided for %s. Persistence at risk.", self.session_id)

        # --- Stage 2: Hot Storage Mirroring ---
        try:
             # Mirror to Hot Storage (Redis/Memory)
             # This must happen only AFTER PG success.
             self.state_repo.save_state(self.session_id, self.context)
             
             # Also sync status explicitly for backward compatibility if state_repo supports it independently
             if hasattr(self.state_repo, 'update_status'):
                 self.state_repo.update_status(self.session_id, self.context.status)

             logger.info("[Mirror] Hot Storage update SUCCESS for %s", self.session_id)
        except Exception as e:
             # Mirroring failure is an 'Availability Issue'
             logger.error("[Mirror] Hot Storage update FAILED for %s (Availability only): %s", self.session_id, e)
             # We do NOT raise here to satisfy Authority First Resilience.

    def _finalize_persistence(self):
        """
        End of Session: Finalize data to Cold Storage.
        """
        # Save aggregated results
        # In reality, this aggregates data from Redis/Hot and flushes to Postgres.
        self.history_repo.save_interview_result(self.session_id, {
            "final_status": self.context.status,
            "completed_questions": self.context.completed_questions_count
        })
        # After this, background worker might pick up for EVALUATED transition.

    # Event Helper
    def emit_silence_warning(self):
        """
        Execute Policy: MUST emit SILENCE_WARNING.
        """
        logger.info("Event: %s for %s", SessionEvent.SILENCE_WARNING, self.session_id)
        # In real impl, send to WebSocket/Client
