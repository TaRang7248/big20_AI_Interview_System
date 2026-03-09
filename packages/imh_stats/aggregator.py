"""
Phase 4 Slice 1: Deterministic Aggregate Statistics Repository
==============================================================

CONTRACTS (LOCKED):
- Source of Truth: PostgreSQL ONLY (REPEATABLE READ isolation).
- Status Filter: status = 'DECIDED' ONLY. COMPLETED/ABORTED/PENDING/INVALIDATED must be excluded at SQL level.
- Time Standard: decided_at (UTC). NEVER created_at.
- Isolation Criterion: evaluation_policy = 'EVALUATIVE' for job stats.
- Rebuild Safety: All stats can be fully reconstructed from PG with no side effects.
- Zero Guard: 0-count returns 0 (not NULL). Division-by-zero protected.
- Rounding: All ratios round to 2 decimal places (round(..., 2)).
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg  # type: ignore

logger = logging.getLogger("imh.stats.aggregator")

# Rebuild triggers: these event types cause cache invalidation
REBUILD_TRIGGER_EVENTS = {"DECISION_MADE", "DECISION_OVERRIDDEN", "INVALIDATED"}


class AggregateStatsRepository:
    """
    Phase 4 PG-Authoritative Aggregate Statistics.

    All queries run under REPEATABLE READ isolation to guarantee snapshot consistency.
    Full-table scans are guarded by the composite index: (status, evaluation_policy, decided_at).
    """

    INDEX_DDL = """
        CREATE INDEX IF NOT EXISTS idx_interviews_stats_composite
        ON interviews (status, evaluation_policy, decided_at)
        WHERE status = 'DECIDED';
    """

    def __init__(self, conn_config: dict):
        self.conn_config = conn_config

    async def _get_connection(self):
        return await asyncpg.connect(**self.conn_config)

    async def ensure_index(self):
        """Create the composite index required by Phase 4 performance contract."""
        conn = await self._get_connection()
        try:
            await conn.execute(self.INDEX_DDL)
            logger.info("[P4] Composite stats index ensured.")
        finally:
            await conn.close()

    # ------------------------------------------------------------------
    # 1. Pass/Fail Count by Job (DECIDED only, evaluation_policy='EVALUATIVE')
    # ------------------------------------------------------------------
    async def get_pass_fail_by_job(
        self,
        job_id: str,
        month_bucket: Optional[str] = None,  # Format: "YYYY-MM"
        decided_at_from: Optional[datetime] = None,
        decided_at_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Returns pass_count, fail_count, total, pass_rate for a specific job_id.

        Conditions (must):
        - status = 'DECIDED'
        - evaluation_policy = 'EVALUATIVE'
        - Filtered by job_id
        - Optional time window: month_bucket OR (decided_at_from, decided_at_to)
        """
        conn = await self._get_connection()
        try:
            async with conn.transaction(isolation="repeatable_read"):
                where_clauses = [
                    "status = 'DECIDED'",
                    "evaluation_policy = 'EVALUATIVE'",
                    "job_id = $1",
                ]
                args: List[Any] = [job_id]

                if month_bucket:
                    # e.g. "2026-03" → filter by that UTC month
                    args.append(month_bucket)
                    where_clauses.append(
                        f"TO_CHAR(decided_at AT TIME ZONE 'UTC', 'YYYY-MM') = ${len(args)}"
                    )
                elif decided_at_from and decided_at_to:
                    args.append(decided_at_from)
                    args.append(decided_at_to)
                    where_clauses.append(
                        f"decided_at AT TIME ZONE 'UTC' >= ${len(args)-1}"
                        f" AND decided_at AT TIME ZONE 'UTC' <= ${len(args)}"
                    )

                where = " AND ".join(where_clauses)
                query = f"""
                    SELECT
                        COUNT(*) FILTER (WHERE decision = 'PASS') AS pass_count,
                        COUNT(*) FILTER (WHERE decision = 'FAIL') AS fail_count,
                        COUNT(*) AS total
                    FROM interviews
                    WHERE {where}
                """

                # Performance evidence: log explain plan for latency guard
                await self._log_explain(conn, query, args)

                row = await conn.fetchrow(query, *args)
                pass_count = int(row["pass_count"] or 0)
                fail_count = int(row["fail_count"] or 0)
                total = int(row["total"] or 0)
                # Zero guard: division-by-zero protection
                pass_rate = round(pass_count / total, 2) if total > 0 else 0.0

                return {
                    "job_id": job_id,
                    "pass_count": pass_count,
                    "fail_count": fail_count,
                    "total": total,
                    "pass_rate": pass_rate,
                    "time_basis": "decided_at_utc",
                }
        finally:
            await conn.close()

    # ------------------------------------------------------------------
    # 2. Monthly Trend (DECIDED only, UTC decided_at)
    # ------------------------------------------------------------------
    async def get_monthly_trend(
        self,
        job_id: Optional[str] = None,
        year: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Returns monthly aggregated stats grouped by decided_at UTC month.

        Conditions (must):
        - status = 'DECIDED'
        - evaluation_policy = 'EVALUATIVE'
        - Grouped by DATE_TRUNC('month', decided_at AT TIME ZONE 'UTC')
        """
        conn = await self._get_connection()
        try:
            async with conn.transaction(isolation="repeatable_read"):
                where_clauses = [
                    "status = 'DECIDED'",
                    "evaluation_policy = 'EVALUATIVE'",
                ]
                args: List[Any] = []

                if job_id:
                    args.append(job_id)
                    where_clauses.append(f"job_id = ${len(args)}")

                if year:
                    args.append(year)
                    where_clauses.append(
                        f"EXTRACT(YEAR FROM decided_at AT TIME ZONE 'UTC') = ${len(args)}"
                    )

                where = " AND ".join(where_clauses)
                query = f"""
                    SELECT
                        TO_CHAR(DATE_TRUNC('month', decided_at AT TIME ZONE 'UTC'), 'YYYY-MM') AS month_bucket,
                        COUNT(*) FILTER (WHERE decision = 'PASS') AS pass_count,
                        COUNT(*) FILTER (WHERE decision = 'FAIL') AS fail_count,
                        COUNT(*) AS total
                    FROM interviews
                    WHERE {where}
                    GROUP BY DATE_TRUNC('month', decided_at AT TIME ZONE 'UTC')
                    ORDER BY DATE_TRUNC('month', decided_at AT TIME ZONE 'UTC') ASC
                """

                await self._log_explain(conn, query, args)
                rows = await conn.fetch(query, *args)

                result = []
                for row in rows:
                    total = int(row["total"] or 0)
                    p = int(row["pass_count"] or 0)
                    result.append({
                        "month_bucket": row["month_bucket"],
                        "pass_count": p,
                        "fail_count": int(row["fail_count"] or 0),
                        "total": total,
                        "pass_rate": round(p / total, 2) if total > 0 else 0.0,
                    })
                return result
        finally:
            await conn.close()

    # ------------------------------------------------------------------
    # 3. Full Rebuild (PG Direct) — Rebuild Safety Contract
    # ------------------------------------------------------------------
    async def rebuild_all(self) -> Dict[str, Any]:
        """
        Full PG-Direct rebuild of aggregate stats.

        "통계는 항상 PG 원본 데이터로부터 완전 재생성 가능해야 한다."
        Redis/MView cache should be invalidated before calling this.
        """
        conn = await self._get_connection()
        try:
            async with conn.transaction(isolation="repeatable_read"):
                query = """
                    SELECT
                        job_id,
                        TO_CHAR(DATE_TRUNC('month', decided_at AT TIME ZONE 'UTC'), 'YYYY-MM') AS month_bucket,
                        COUNT(*) FILTER (WHERE decision = 'PASS') AS pass_count,
                        COUNT(*) FILTER (WHERE decision = 'FAIL') AS fail_count,
                        COUNT(*) AS total
                    FROM interviews
                    WHERE status = 'DECIDED'
                      AND evaluation_policy = 'EVALUATIVE'
                    GROUP BY job_id, DATE_TRUNC('month', decided_at AT TIME ZONE 'UTC')
                    ORDER BY job_id, DATE_TRUNC('month', decided_at AT TIME ZONE 'UTC')
                """
                rows = await conn.fetch(query)
                rebuilt = []
                for row in rows:
                    total = int(row["total"] or 0)
                    p = int(row["pass_count"] or 0)
                    rebuilt.append({
                        "job_id": row["job_id"],
                        "month_bucket": row["month_bucket"],
                        "pass_count": p,
                        "fail_count": int(row["fail_count"] or 0),
                        "total": total,
                        "pass_rate": round(p / total, 2) if total > 0 else 0.0,
                    })
                logger.info("[P4 REBUILD] Completed. %d job/month buckets.", len(rebuilt))
                return {"rebuilt_at": datetime.utcnow().isoformat(), "buckets": rebuilt}
        finally:
            await conn.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _log_explain(self, conn, query: str, args: list):
        """Log EXPLAIN ANALYZE output; warn if cost exceeds threshold."""
        try:
            plan_rows = await conn.fetch(f"EXPLAIN (ANALYZE, FORMAT TEXT) {query}", *args)
            plan_text = "\n".join(r[0] for r in plan_rows)
            if "Seq Scan" in plan_text:
                logger.warning("[P4 PERF] Sequential scan detected! Review index.\n%s", plan_text[:500])
            else:
                logger.debug("[P4 PERF] Index scan confirmed.\n%s", plan_text[:300])
        except Exception as e:
            logger.warning("[P4 PERF] Could not run EXPLAIN: %s", e)


class GranularStatsCache:
    """
    Phase 4 Granular Cache-Aside for Stats.

    Cache Invalidation Contract (Locked):
    - Key granularity: stats:v2:{job_id}:{month_bucket} or stats:v2:{job_id}:trend:{year}
    - TTL: 60 seconds (fixed, per Phase 4 plan).
    - Invalidation trigger events: DECISION_MADE, DECISION_OVERRIDDEN, INVALIDATED.
    - Invalidation scope: job_id + month_bucket level ONLY (no global flush).
    """

    KEY_PREFIX = "stats:v2"
    TTL_SECONDS = 60

    def __init__(self):
        from packages.imh_core.infra.redis import RedisClient
        try:
            self.redis = RedisClient.get_instance()
        except Exception:
            self.redis = None
            logger.warning("[P4 Cache] Redis unreachable. Stats cache disabled.")

    def _key_pass_fail(self, job_id: str, month_bucket: Optional[str]) -> str:
        bucket = month_bucket or "all"
        return f"{self.KEY_PREFIX}:{job_id}:{bucket}:passfail"

    def _key_trend(self, job_id: Optional[str], year: Optional[int]) -> str:
        j = job_id or "all"
        y = str(year) if year else "all"
        return f"{self.KEY_PREFIX}:{j}:trend:{y}"

    def get_pass_fail(self, job_id: str, month_bucket: Optional[str]) -> Optional[Dict]:
        if not self.redis:
            return None
        try:
            raw = self.redis.get(self._key_pass_fail(job_id, month_bucket))
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def set_pass_fail(self, job_id: str, month_bucket: Optional[str], data: Dict):
        if not self.redis:
            return
        try:
            self.redis.setex(
                self._key_pass_fail(job_id, month_bucket),
                self.TTL_SECONDS,
                json.dumps(data, default=str),
            )
        except Exception as e:
            logger.warning("[P4 Cache] set_pass_fail failed: %s", e)

    def get_trend(self, job_id: Optional[str], year: Optional[int]) -> Optional[List]:
        if not self.redis:
            return None
        try:
            raw = self.redis.get(self._key_trend(job_id, year))
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def set_trend(self, job_id: Optional[str], year: Optional[int], data: List):
        if not self.redis:
            return
        try:
            self.redis.setex(
                self._key_trend(job_id, year),
                self.TTL_SECONDS,
                json.dumps(data, default=str),
            )
        except Exception as e:
            logger.warning("[P4 Cache] set_trend failed: %s", e)

    def invalidate_for_job(self, job_id: str, month_bucket: Optional[str] = None):
        """
        Granular invalidation: target only the affected job_id + month_bucket.
        Called on DECISION_MADE, DECISION_OVERRIDDEN, INVALIDATED events.
        """
        if not self.redis:
            return
        keys_to_delete = []
        if month_bucket:
            keys_to_delete.append(self._key_pass_fail(job_id, month_bucket))
            # Also invalidate 'all' bucket for the job
            keys_to_delete.append(self._key_pass_fail(job_id, None))
        else:
            # Invalidate all known buckets for this job via scan pattern
            try:
                pattern = f"{self.KEY_PREFIX}:{job_id}:*"
                keys = list(self.redis.scan_iter(pattern))
                keys_to_delete.extend(keys)
            except Exception as e:
                logger.warning("[P4 Cache] scan_iter failed: %s", e)

        if keys_to_delete:
            try:
                self.redis.delete(*keys_to_delete)
                logger.info("[P4 Cache] Invalidated %d keys for job=%s bucket=%s", len(keys_to_delete), job_id, month_bucket)
            except Exception as e:
                logger.warning("[P4 Cache] delete failed: %s", e)
