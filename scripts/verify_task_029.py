"""
TASK-029 Baseline Alignment 검증 스크립트.

4종 검증 (Acceptance Criteria):
  V-1: Schema Check   - interviews, evaluation_scores 테이블 존재 여부
  V-2: DI Check       - get_session_history_repository()가 PostgreSQLHistoryRepository 반환
  V-3: Persistence Check - update_interview_status가 실제 DB UPDATE를 실행하는지 확인 (코드 분석)
  V-4: Hydration Check   - engine가 pg_state_repo를 받아 Redis Miss 시 복구 로직을 가지는지 확인

Usage:
    python scripts/verify_task_029.py
"""

import sys
import os
import logging
from pathlib import Path

# ── 경로 설정 ──────────────────────────────────────────────────────────────
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

env_path = project_root / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("verify_task_029")

PASS = "PASS"
FAIL = "FAIL"
results = {}


# ─────────────────────────────────────────────────────────────────────────────
# V-1: Schema Check
# ─────────────────────────────────────────────────────────────────────────────
def check_schema() -> str:
    """DB 연결 후 interviews, evaluation_scores 테이블이 존재하는지 확인한다."""
    import asyncio
    import asyncpg
    import re

    conn_str = os.getenv("POSTGRES_CONNECTION_STRING")
    if not conn_str:
        logger.warning("V-1 SKIP: POSTGRES_CONNECTION_STRING 미설정. 코드 수준 검사로 대체.")
        # Fallback: init_db.py 소스 확인
        init_db_path = project_root / "IMH" / "IMH_Interview" / "scripts" / "init_db.py"
        source = init_db_path.read_text(encoding="utf-8")
        required = ["CREATE TABLE IF NOT EXISTS interviews", "CREATE TABLE IF NOT EXISTS evaluation_scores"]
        for stmt in required:
            if stmt not in source:
                logger.error("V-1 FAIL: '%s' not found in init_db.py", stmt)
                return FAIL
        logger.info("V-1 PASS (code-level): init_db.py contains correct table names.")
        return PASS

    # Live DB check
    pattern = r"postgresql\+asyncpg://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)"
    match = re.match(pattern, conn_str)
    if not match:
        logger.error("V-1 FAIL: 잘못된 connection string 형식.")
        return FAIL

    user, password, host, port, database = match.groups()

    async def _check():
        conn = await asyncpg.connect(host=host, port=int(port), user=user, password=password, database=database)
        try:
            rows = await conn.fetch("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema='public'
                AND table_name IN ('interviews', 'evaluation_scores')
            """)
            found = {r["table_name"] for r in rows}
            required_tables = {"interviews", "evaluation_scores"}
            missing = required_tables - found
            if missing:
                logger.error("V-1 FAIL: 테이블 미존재 - %s", missing)
                return FAIL
            logger.info("V-1 PASS: interviews, evaluation_scores 테이블 확인.")
            return PASS
        finally:
            await conn.close()

    return asyncio.run(_check())


# ─────────────────────────────────────────────────────────────────────────────
# V-2: DI Check
# ─────────────────────────────────────────────────────────────────────────────
def check_di() -> str:
    """get_session_history_repository가 PostgreSQLHistoryRepository를 반환하는지 확인한다."""
    try:
        deps_path = project_root / "IMH" / "IMH_Interview" / "IMH" / "api" / "dependencies.py"
        source = deps_path.read_text(encoding="utf-8")

        if "PostgreSQLHistoryRepository" not in source:
            logger.error("V-2 FAIL: PostgreSQLHistoryRepository import가 dependencies.py에 없음.")
            return FAIL

        # get_session_history_repository 함수 안에 PostgreSQLHistoryRepository 반환 있는지 확인
        if "return PostgreSQLHistoryRepository(" not in source:
            logger.error("V-2 FAIL: get_session_history_repository가 PostgreSQLHistoryRepository를 반환하지 않음.")
            return FAIL

        logger.info("V-2 PASS: dependencies.py에 PostgreSQLHistoryRepository 주입 확인.")
        return PASS
    except Exception as e:
        logger.exception("V-2 FAIL: %s", e)
        return FAIL


# ─────────────────────────────────────────────────────────────────────────────
# V-3: Persistence Check
# ─────────────────────────────────────────────────────────────────────────────
def check_persistence() -> str:
    """update_interview_status가 실제 DB UPDATE 쿼리를 실행하는지 코드 분석으로 확인한다."""
    try:
        repo_path = (
            project_root
            / "IMH" / "IMH_Interview"
            / "packages" / "imh_history" / "postgresql_repository.py"
        )
        source = repo_path.read_text(encoding="utf-8")

        # 실제 UPDATE 쿼리가 존재해야 함
        if "UPDATE interviews" not in source:
            logger.error("V-3 FAIL: postgresql_repository.py에 'UPDATE interviews' 쿼리가 없음.")
            return FAIL

        # _async_update_interview_status 메서드가 존재해야 함
        if "_async_update_interview_status" not in source:
            logger.error("V-3 FAIL: _async_update_interview_status 메서드가 없음.")
            return FAIL

        # 단순 log-only였던 이전 코드 패턴이 없어야 함
        old_pattern = 'logger.info(f"[PostgreSQLHistoryRepo] Status update:'
        if old_pattern in source:
            logger.error("V-3 FAIL: 기존 log-only update_interview_status 패턴이 잔존함.")
            return FAIL

        logger.info("V-3 PASS: postgresql_repository.py에 실제 DB UPDATE 구현 확인.")
        return PASS
    except Exception as e:
        logger.exception("V-3 FAIL: %s", e)
        return FAIL


# ─────────────────────────────────────────────────────────────────────────────
# V-4: Hydration Check
# ─────────────────────────────────────────────────────────────────────────────
def check_hydration() -> str:
    """engine.py가 pg_state_repo를 받고 Redis Miss 시 PG에서 복구하는 로직을 갖는지 확인한다."""
    try:
        engine_path = (
            project_root
            / "IMH" / "IMH_Interview"
            / "packages" / "imh_session" / "engine.py"
        )
        source = engine_path.read_text(encoding="utf-8")

        # pg_state_repo 파라미터 존재 여부
        if "pg_state_repo" not in source:
            logger.error("V-4 FAIL: engine.py에 pg_state_repo 파라미터가 없음.")
            return FAIL

        # PG Hydration 로직 존재 여부
        if "pg_state_repo.get_state" not in source:
            logger.error("V-4 FAIL: Hydration 로직(pg_state_repo.get_state)이 없음.")
            return FAIL

        # session_service.py에도 pg_state_repo 전달 확인
        svc_path = (
            project_root
            / "IMH" / "IMH_Interview"
            / "packages" / "imh_service" / "session_service.py"
        )
        svc_source = svc_path.read_text(encoding="utf-8")
        if "pg_state_repo=self.postgres_state_repo" not in svc_source:
            logger.error("V-4 FAIL: session_service.py에서 pg_state_repo를 엔진에 전달하지 않음.")
            return FAIL

        logger.info("V-4 PASS: engine.py Hydration 로직 및 session_service.py 전달 확인.")
        return PASS
    except Exception as e:
        logger.exception("V-4 FAIL: %s", e)
        return FAIL


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    logger.info("=" * 60)
    logger.info("TASK-029 Baseline Alignment Verification")
    logger.info("=" * 60)

    results["V-1 Schema Check"] = check_schema()
    results["V-2 DI Check"] = check_di()
    results["V-3 Persistence Check"] = check_persistence()
    results["V-4 Hydration Check"] = check_hydration()

    logger.info("")
    logger.info("─" * 60)
    logger.info("결과 요약")
    logger.info("─" * 60)
    all_pass = True
    for name, result in results.items():
        status_str = "✓" if result == PASS else "✗"
        logger.info("  %s %s: %s", status_str, name, result)
        if result != PASS:
            all_pass = False

    logger.info("─" * 60)
    if all_pass:
        logger.info("TASK-029 Baseline Alignment: 4종 검증 ALL PASS")
        logger.info("scripts/verify_task_029.py Pass")
        return 0
    else:
        logger.error("TASK-029 Baseline Alignment: 일부 검증 FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
