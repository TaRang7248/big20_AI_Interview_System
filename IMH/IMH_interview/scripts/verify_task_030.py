"""
verify_task_030.py
==================
Contract-enforced verification for TASK-030:
  "State Save Atomicity & PostgreSQL Authority Enforcement"

All scenarios use assert-based contract checks.
On any failure, the script exits with code 1.

Contracts under test:
  [C1] Order Invariant        : PG save_state always precedes any Redis operation.
  [C2] Atomicity Invariant    : PG failure MUST block Redis mirror update.
  [C3] Authority Resilience   : Redis failure MUST NOT propagate; engine continues.
  [C4] Authority Invariant    : redis_status <= pg_status (total-order on SessionStatus).
  [C5] Observability Invariant: Projection must never be updated before PG commit succeeds.
"""

import os
import sys
import logging
from typing import Any, Optional, List, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# Bootstrap
# ──────────────────────────────────────────────────────────────────────────────
sys.path.insert(0, os.getcwd())

from packages.imh_session.engine import InterviewSessionEngine
from packages.imh_session.dto import SessionConfig, SessionContext
from packages.imh_session.state import SessionStatus
from packages.imh_session.repository import SessionStateRepository, SessionHistoryRepository

logging.basicConfig(level=logging.WARNING)   # suppress info noise during testing

# ──────────────────────────────────────────────────────────────────────────────
# StatusOrder: defines total ordering for SessionStatus
# Used for Authority Invariant assertions (redis_status <= pg_status)
# ──────────────────────────────────────────────────────────────────────────────
STATUS_ORDER = {
    SessionStatus.APPLIED:     0,
    SessionStatus.IN_PROGRESS: 1,
    SessionStatus.INTERRUPTED: 2,
    SessionStatus.COMPLETED:   3,
    SessionStatus.EVALUATED:   4,
}

def status_le(a: SessionStatus, b: SessionStatus) -> bool:
    """Return True if status 'a' is less-than-or-equal-to 'b' in the defined order."""
    return STATUS_ORDER.get(a, -1) <= STATUS_ORDER.get(b, -1)


# ──────────────────────────────────────────────────────────────────────────────
# Mock repositories
# ──────────────────────────────────────────────────────────────────────────────
class TraceRepository(SessionStateRepository, SessionHistoryRepository):
    """
    Dual-role mock repository that:
      - Records all calls as (operation, session_id, status) tuples.
      - Optionally injects failures on specific operations.
      - Optionally appends to a shared_recorder for cross-repo timeline ordering.
        Each entry: (source_name, operation, session_id, status)
    """
    def __init__(self, name: str, fail_on: Optional[str] = None,
                 shared_recorder: Optional[List] = None):
        self.name = name
        self.log: List[Tuple[str, str, Any]] = []
        self.fail_on = fail_on
        self.states: dict = {}
        self._shared: Optional[List] = shared_recorder

    def _record(self, op: str, session_id: str, status: Any) -> None:
        """Append to local log and, if provided, the shared cross-repo recorder."""
        entry = (op, session_id, status)
        self.log.append(entry)
        if self._shared is not None:
            self._shared.append((self.name, op, session_id, status))

    # ── SessionStateRepository ────────────────────────────────────────────────
    def save_state(self, session_id: str, context: SessionContext) -> None:
        if self.fail_on == "save_state":
            raise Exception(f"Mock failure in {self.name}.save_state")
        self._record("save_state", session_id, context.status)
        self.states[session_id] = context

    def get_state(self, session_id: str) -> Optional[SessionContext]:
        return self.states.get(session_id)

    def update_status(self, session_id: str, status: SessionStatus) -> None:
        if self.fail_on == "update_status":
            raise Exception(f"Mock failure in {self.name}.update_status")
        self._record("update_status", session_id, status)

    def find_by_job_id(self, job_id: str) -> list:
        return []

    # ── SessionHistoryRepository ──────────────────────────────────────────────
    def update_interview_status(self, session_id: str, status: SessionStatus) -> None:
        if self.fail_on == "update_interview_status":
            raise Exception(f"Mock failure in {self.name}.update_interview_status")
        self._record("update_interview_status", session_id, status)

    def save_interview_result(self, session_id: str, result_data: Any) -> None:
        self._record("save_interview_result", session_id, None)


class ProjectionRepository:
    """
    Mock Projection Repository to enforce the Observability Invariant.
    Records every update; used to assert no update fires before PG commit.
    """
    def __init__(self):
        self.updates: List[str] = []

    def delete(self, session_id: str) -> None:
        self.updates.append(session_id)

    def save(self, session_id: str, data: Any) -> None:
        self.updates.append(session_id)


# ──────────────────────────────────────────────────────────────────────────────
# Shared mock services
# ──────────────────────────────────────────────────────────────────────────────
class MockGenerator:
    """Simulates a successful RAG question generation."""
    def generate_question(self, ctx):
        from collections import namedtuple
        Result = namedtuple("Result", ["success", "content", "metadata", "error"])
        return Result(True, "Generated Question", {}, None)


class MockQBank:
    """Simulates an empty question bank (forces emergency fallback path)."""
    def get_candidates(self, tags=None):
        return []


def make_engine(session_id: str, pg_repo: TraceRepository, redis_repo: TraceRepository,
                config: Optional[SessionConfig] = None) -> InterviewSessionEngine:
    if config is None:
        config = SessionConfig(job_id="job_030", total_question_limit=1)
    return InterviewSessionEngine(
        session_id=session_id,
        config=config,
        state_repo=redis_repo,
        history_repo=pg_repo,
        question_generator=MockGenerator(),
        qbank_service=MockQBank(),
        pg_state_repo=pg_repo,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Scenario helpers
# ──────────────────────────────────────────────────────────────────────────────
FAILURES: List[str] = []


def _fail(scenario: str, contract: str, detail: str) -> None:
    msg = f"[FAIL] Scenario '{scenario}' | {contract}: {detail}"
    print(msg)
    FAILURES.append(msg)


def _pass(scenario: str, contract: str) -> None:
    print(f"[PASS] Scenario '{scenario}' | {contract}")


# ─────────────────────────────────────────────────────────────
# [C1] Order Invariant  (single real-insertion-order timeline)
#      Uses a shared_recorder injected into both repos so every
#      PG and Redis event is captured in true call order with no
#      synthetic index arithmetic.
#
#      Invariants checked:
#        C1a – At least one PG save_state exists.
#        C1b – The very first save_state event is from PG.
#        C1c – No REDIS event appears before the first PG save_state.
# ─────────────────────────────────────────────────────────────
def scenario_1_order(config: SessionConfig) -> None:
    scenario = "1 – Order Invariant"
    print(f"\n{'='*60}")
    print(f"Scenario {scenario}")
    print("="*60)

    # Shared recorder captures (source_name, op, session_id, status)
    # in true wall-clock insertion order across both repos.
    shared: List = []

    pg_repo    = TraceRepository("PG_AUTHORITY", shared_recorder=shared)
    redis_repo = TraceRepository("REDIS_MIRROR", shared_recorder=shared)
    engine     = make_engine("sess_order", pg_repo, redis_repo, config)

    engine.start_session()

    print("Operations log (single real-insertion-order timeline):")
    for src, op, _sid, status in shared:
        print(f"  [{src}] {op} -> {status}")

    # --- C1a: At least one PG save_state must exist ---
    pg_saves = [
        (i, src, op, status)
        for i, (src, op, _sid, status) in enumerate(shared)
        if src == "PG_AUTHORITY" and op == "save_state"
    ]

    try:
        assert len(pg_saves) >= 1, "No PG save_state recorded"
        _pass(scenario, "C1a – PG save_state exists")
    except AssertionError as e:
        _fail(scenario, "C1a – PG save_state exists", str(e))
        return  # Cannot continue order check

    first_pg_idx = pg_saves[0][0]   # position in shared timeline

    # --- C1b: The FIRST save_state event overall must be from PG ---
    first_save_events = [
        (i, src, op, status)
        for i, (src, op, _sid, status) in enumerate(shared)
        if op == "save_state"
    ]
    try:
        assert first_save_events[0][1] == "PG_AUTHORITY", (
            f"First save_state came from '{first_save_events[0][1]}' "
            f"instead of 'PG_AUTHORITY'"
        )
        _pass(scenario, "C1b – First save_state is from PG")
    except AssertionError as e:
        _fail(scenario, "C1b – First save_state is from PG", str(e))

    # --- C1c: Zero REDIS events before the first PG save_state ---
    redis_before_pg = [
        (i, src, op, status)
        for i, (src, op, _sid, status) in enumerate(shared)
        if src == "REDIS_MIRROR" and i < first_pg_idx
    ]
    try:
        assert len(redis_before_pg) == 0, (
            f"{len(redis_before_pg)} REDIS event(s) appeared before "
            f"first PG save_state (timeline pos {first_pg_idx}): "
            f"{redis_before_pg}"
        )
        _pass(scenario, "C1c – Zero REDIS events before first PG save_state")
    except AssertionError as e:
        _fail(scenario, "C1c – Zero REDIS events before first PG save_state", str(e))


# ─────────────────────────────────────────────────────────────
# [C2] Atomicity Invariant
#      PG failure MUST block any Redis mirror update.
# ─────────────────────────────────────────────────────────────
def scenario_2_pg_failure(config: SessionConfig) -> None:
    scenario = "2 – Atomicity (PG Failure)"
    print(f"\n{'='*60}")
    print(f"Scenario {scenario}")
    print("="*60)

    pg_fail_repo = TraceRepository("PG_FAIL", fail_on="save_state")
    redis_repo   = TraceRepository("REDIS_MIRROR")
    engine       = make_engine("sess_fail", pg_fail_repo, redis_repo, config)

    # --- C2a: engine.start_session() must raise when PG fails ---
    exception_raised = False
    try:
        engine.start_session()
    except Exception as e:
        exception_raised = True
        print(f"  PG failure caught: {e}")

    try:
        assert exception_raised, (
            "engine.start_session() did NOT raise on PG failure – "
            "Authority contract violated"
        )
        _pass(scenario, "C2a – Exception propagated on PG failure")
    except AssertionError as e:
        _fail(scenario, "C2a – Exception propagated on PG failure", str(e))

    # --- C2b: Redis mirror must be completely empty ---
    try:
        assert len(redis_repo.log) == 0, (
            f"Redis Mirror was updated despite PG failure "
            f"({len(redis_repo.log)} ops recorded): {redis_repo.log}"
        )
        _pass(scenario, "C2b – Redis Mirror NOT updated after PG failure")
    except AssertionError as e:
        _fail(scenario, "C2b – Redis Mirror NOT updated after PG failure", str(e))


# ─────────────────────────────────────────────────────────────
# [C3] Authority Resilience
#      Redis failure MUST NOT propagate; engine must succeed.
# ─────────────────────────────────────────────────────────────
def scenario_3_redis_failure(config: SessionConfig) -> None:
    scenario = "3 – Authority Resilience (Redis Failure)"
    print(f"\n{'='*60}")
    print(f"Scenario {scenario}")
    print("="*60)

    pg_repo       = TraceRepository("PG_AUTHORITY")
    redis_fail    = TraceRepository("REDIS_FAIL", fail_on="save_state")
    engine        = make_engine("sess_resilient", pg_repo, redis_fail, config)

    # --- C3a: engine.start_session() must NOT raise when only Redis fails ---
    exception_raised = False
    try:
        engine.start_session()
    except Exception as e:
        exception_raised = True
        print(f"  Unexpected exception: {e}")

    try:
        assert not exception_raised, (
            "engine.start_session() raised an exception on Redis failure – "
            "Resilience contract violated"
        )
        _pass(scenario, "C3a – No exception propagated on Redis failure")
    except AssertionError as e:
        _fail(scenario, "C3a – No exception propagated on Redis failure", str(e))

    # --- C3b: PG Authority must have been updated ---
    pg_saves = [op for op in pg_repo.log if op[0] == "save_state"]
    try:
        assert len(pg_saves) >= 1, "PG Authority save_state was never called"
        _pass(scenario, f"C3b – PG Authority updated: {pg_saves[0]}")
    except AssertionError as e:
        _fail(scenario, "C3b – PG Authority updated", str(e))


# ─────────────────────────────────────────────────────────────
# [C4] Authority Invariant (status ordering)
#      After any commit, redis_status <= pg_status must hold.
#      Ensures Redis never claims a more advanced state than PG.
# ─────────────────────────────────────────────────────────────
def scenario_4_authority_invariant(config: SessionConfig) -> None:
    scenario = "4 – Authority Invariant (redis_status <= pg_status)"
    print(f"\n{'='*60}")
    print(f"Scenario {scenario}")
    print("="*60)

    pg_repo    = TraceRepository("PG_AUTHORITY")
    redis_repo = TraceRepository("REDIS_MIRROR")
    engine     = make_engine("sess_order_inv", pg_repo, redis_repo, config)

    engine.start_session()

    # Extract latest statuses from each repo
    pg_statuses = [
        status for (op, _sid, status) in pg_repo.log
        if op == "save_state" and isinstance(status, SessionStatus)
    ]
    redis_statuses = [
        status for (op, _sid, status) in redis_repo.log
        if op == "save_state" and isinstance(status, SessionStatus)
    ]

    if not pg_statuses:
        _fail(scenario, "C4 – PG status recorded", "No PG save_state found")
        return

    pg_status    = pg_statuses[-1]
    redis_status = redis_statuses[-1] if redis_statuses else None

    print(f"  PG status    : {pg_status}")
    print(f"  Redis status : {redis_status}")

    try:
        if redis_status is not None:
            assert status_le(redis_status, pg_status), (
                f"Redis status '{redis_status}' is MORE ADVANCED than PG status "
                f"'{pg_status}' – Authority Invariant violated"
            )
        _pass(scenario, f"C4 – redis_status({redis_status}) <= pg_status({pg_status})")
    except AssertionError as e:
        _fail(scenario, "C4 – redis_status <= pg_status", str(e))


# ─────────────────────────────────────────────────────────────
# [C5] Observability Invariant
#      Projection must NOT be updated before PG commit succeeds.
#      We simulate this by injecting a mock ProjectionRepository
#      and asserting it sees no updates when PG fails.
# ─────────────────────────────────────────────────────────────
def scenario_5_observability(config: SessionConfig) -> None:
    scenario = "5 – Observability Invariant (no premature Projection update)"
    print(f"\n{'='*60}")
    print(f"Scenario {scenario}")
    print("="*60)

    # ── Sub-test 5a: PG fails → Projection must receive NO update ─────────────
    pg_fail_repo  = TraceRepository("PG_FAIL", fail_on="save_state")
    redis_repo    = TraceRepository("REDIS_MIRROR")
    proj_repo     = ProjectionRepository()
    engine        = make_engine("sess_obs_fail", pg_fail_repo, redis_repo, config)
    # Inject projection repo into engine if supported; otherwise test at service layer
    # For this unit test, we simulate the service-layer pattern:
    # - service calls engine.start_session() (may raise)
    # - service calls proj_repo.delete() ONLY after engine succeeds

    def service_create_session_sim(eng: InterviewSessionEngine,
                                   proj: ProjectionRepository) -> None:
        """
        Simulates the SessionService pattern:
            engine.start_session()          ← PG + Redis atomic
            proj_repo.delete(session_id)    ← only if above succeeds
        """
        eng.start_session()           # raises on PG failure
        proj.delete(eng.session_id)   # must NOT reach here if PG failed

    try:
        service_create_session_sim(engine, proj_repo)
    except Exception:
        pass  # PG failure expected; projection update must not have occurred

    try:
        assert len(proj_repo.updates) == 0, (
            f"Projection was updated despite PG failure "
            f"({len(proj_repo.updates)} updates): {proj_repo.updates}"
        )
        _pass(scenario, "C5a – Projection NOT updated when PG fails")
    except AssertionError as e:
        _fail(scenario, "C5a – Projection NOT updated when PG fails", str(e))

    # ── Sub-test 5b: PG succeeds → Projection IS updated ─────────────────────
    pg_repo_ok    = TraceRepository("PG_AUTHORITY")
    redis_repo_ok = TraceRepository("REDIS_MIRROR")
    proj_repo_ok  = ProjectionRepository()
    engine_ok     = make_engine("sess_obs_ok", pg_repo_ok, redis_repo_ok, config)

    try:
        service_create_session_sim(engine_ok, proj_repo_ok)
    except Exception as e:
        _fail(scenario, "C5b – Projection updated when PG succeeds",
              f"Unexpected engine failure: {e}")
        return

    try:
        assert len(proj_repo_ok.updates) >= 1, (
            "Projection was NOT updated after a successful PG commit – "
            "service flow may be broken"
        )
        _pass(scenario, f"C5b – Projection updated after PG success "
                        f"({len(proj_repo_ok.updates)} update(s))")
    except AssertionError as e:
        _fail(scenario, "C5b – Projection updated after PG success", str(e))


# ──────────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 60)
    print("TASK-030 Contract Verification (Assert Mode)")
    print("=" * 60)

    config = SessionConfig(job_id="job_030", total_question_limit=1)

    scenario_1_order(config)
    scenario_2_pg_failure(config)
    scenario_3_redis_failure(config)
    scenario_4_authority_invariant(config)
    scenario_5_observability(config)

    print(f"\n{'=' * 60}")
    if FAILURES:
        print(f"RESULT: FAILED  ({len(FAILURES)} contract violation(s))")
        for f in FAILURES:
            print(f"  {f}")
        print("=" * 60)
        sys.exit(1)
    else:
        print("RESULT: ALL CONTRACTS PASSED")
        print("=" * 60)
        sys.exit(0)


if __name__ == "__main__":
    main()
