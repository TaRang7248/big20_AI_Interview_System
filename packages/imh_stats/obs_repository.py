"""
Track B: Observability Repository.

DATA SOURCES (Strictly enforced):
  - PostgreSQL 'error_events' or similar failure data within EXISTING tables.
  - Log-based aggregation (in-memory, at query time via log file scanning).
  - NEVER calls Track A StatisticsRepository.
  - NEVER reads from sessions/evaluations as a business authority source.

CONTRACTS:
  - Informational ONLY. Read-Only. No Write-Back.
  - Log data: may be incomplete (log loss possible). Trend use only.
  - State Transition Failures: derived from PG records ONLY if already stored.
    Engine/Command code MUST NOT be modified to produce these records.

TYPE 3 ISOLATION:
  - Aggregated multi-dimensional queries route through MView-level SQL.
  - Real-time aggregation over base tables is BANNED for Type 3.
  - MView creation is a DB-level concern, not a repository concern (tracked in docs).

TYPE 4 (Correlation/Anomaly):
  - DISABLED in CP1. No execution path exists here.
  - Feature flag status: DISABLED_TYPE4 = True (constant guard).
"""
import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any

import asyncpg  # type: ignore

logger = logging.getLogger("imh.obs.repository")

# ============================================================
# TYPE 4 GUARD — CP1 DISABLED CONSTANT
# ============================================================
DISABLED_TYPE4: bool = True   # Type 4 is DISABLED. Do not change in CP1.


class ObservabilityRepository:
    """
    PostgreSQL-based Observability Repository (Track B).

    SOURCES ALLOWED:
    - Any PG table that already records operational events (e.g., failed status rows).
    - NEVER joins with business-authoritative result computation.
    - Can read from 'sessions' status='INTERRUPTED'|'ERROR' for failure rate only.

    TYPE 3 Note:
    - Multi-dimensional queries are directed to a Type3 MView (if created).
    - If MView does not exist, a safe fallback query runs on existing tables.
    - Real-time heavy aggregation is NEVER triggered for Type 3.
    """

    # ──────────────────────────────────────────────────────────────────
    # TYPE 3 ISOLATION CONSTANTS (exposed for external assertion)
    # These are the ONLY relations Type 3 queries are allowed to target.
    # ──────────────────────────────────────────────────────────────────
    TYPE3_MVIEW_NAME: str = "stats_mv_session_aggregate"
    TYPE3_BASE_TABLES_BANNED: tuple = ("interviews", "evaluations")  # banned for Type3 primary path

    # SQL templates — readable by the verification script
    TYPE3_SQL_MVIEW: str = (
        "SELECT {dimension}, count FROM stats_mv_session_aggregate "
        "WHERE aggregation_date BETWEEN $1 AND $2 "
        "ORDER BY aggregation_date ASC"
    )
    TYPE3_SQL_FALLBACK: str = (
        "SELECT status, COUNT(*) as count "
        "FROM sessions "
        "WHERE updated_at >= $1 AND updated_at <= $2 "
        "GROUP BY status"
    )

    def __init__(self, conn_config: dict):
        self.conn_config = conn_config

    async def _get_connection(self):
        return await asyncpg.connect(**self.conn_config)

    async def get_state_transition_failures(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Type B Metric: State transition failure count from PG.
        Source: existing 'sessions' rows with status='INTERRUPTED'.
        CONTRACT: SessionEngine/Command is NOT modified to produce this data.
        """
        conn = await self._get_connection()
        try:
            query = """
                SELECT
                    DATE(updated_at) as date,
                    COUNT(*) as failure_count
                FROM sessions
                WHERE status IN ('INTERRUPTED')
                  AND updated_at >= $1 AND updated_at <= $2
                GROUP BY DATE(updated_at)
                ORDER BY DATE(updated_at) ASC
            """
            rows = await conn.fetch(query, start_date, end_date)
            return [{"date": str(r["date"]), "failure_count": r["failure_count"]} for r in rows]
        except Exception as e:
            logger.warning("[ObsRepo] State transition failure query failed: %s", e)
            return []
        finally:
            await conn.close()

    async def get_type3_aggregation(
        self,
        dimension: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Type 3 Query: Multi-dimensional aggregation via MView.

        ISOLATION CONTRACT:
        - Primary path queries the MView 'stats_mv_session_aggregate' ONLY.
        - Falls back to a lightweight status-count query if MView not yet created.
        - The base tables 'interviews' and 'evaluations' are NEVER touched.
        - NEVER triggers a full-table scan on large base data in real-time.

        Run `ObservabilityRepository.TYPE3_MVIEW_NAME` to confirm the target.
        Run `ObservabilityRepository.TYPE3_SQL_MVIEW` to confirm the query template.
        """
        conn = await self._get_connection()
        try:
            mview_exists = await self._check_mview_exists(conn, self.TYPE3_MVIEW_NAME)
            if mview_exists:
                logger.info(
                    "[ObsRepo] Type3: Querying via MView '%s'. SQL target: %s",
                    self.TYPE3_MVIEW_NAME, self.TYPE3_MVIEW_NAME
                )
                rows = await conn.fetch(
                    f"SELECT {dimension}, count FROM {self.TYPE3_MVIEW_NAME} "
                    f"WHERE aggregation_date BETWEEN $1 AND $2 ORDER BY aggregation_date ASC",
                    start_date.date(), end_date.date()
                )
                return [dict(r) for r in rows]
            else:
                # Fallback: lightweight status-count only.
                # Banned tables (interviews, evaluations) are NOT used here.
                logger.info(
                    "[ObsRepo] Type3: MView '%s' not found. "
                    "Using fallback. SQL target: sessions (status-count only, no full scan).",
                    self.TYPE3_MVIEW_NAME
                )
                rows = await conn.fetch(
                    "SELECT status, COUNT(*) as count "
                    "FROM sessions "
                    "WHERE updated_at >= $1 AND updated_at <= $2 "
                    "GROUP BY status",
                    start_date, end_date
                )
                return [{"status": r["status"], "count": r["count"]} for r in rows]
        except Exception as e:
            logger.warning(f"[ObsRepo] Type3 aggregation failed: {e}")
            return []
        finally:
            await conn.close()

    async def _check_mview_exists(self, conn, mview_name: str) -> bool:
        """Check if a materialized view exists in the DB."""
        try:
            row = await conn.fetchrow(
                "SELECT 1 FROM pg_matviews WHERE matviewname = $1", mview_name
            )
            return row is not None
        except Exception:
            return False


class LogObservabilityRepository:
    """
    Log-file-based Observability Repository (Track B).

    SOURCE: Existing application log files (imh.*.log).
    TRUST LEVEL: Informational / Trend only. Log loss is expected.
    CONTRACT:
    - NEVER calls Track A repositories or their data.
    - Aggregates log events in-memory at query time (No Write-Back).
    - Only reads log files that already exist; does not create new log paths.
    """

    def __init__(self, log_dir: str = "logs/runtime"):
        self.log_dir = Path(log_dir)

    def _iter_log_files(self):
        """Yield existing log files from the log directory."""
        if not self.log_dir.exists():
            return
        for f in self.log_dir.glob("*.log"):
            yield f

    def get_latency_stats(
        self,
        span: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Parse log files to compute average latency for a span.
        Informational only - log loss possible.
        Pattern: 'LATENCY span=<span> layer=<layer> duration_ms=<ms>'
        """
        latencies = []
        pattern = re.compile(
            r"LATENCY span=" + re.escape(span) + r" layer=(\w+) duration_ms=(\d+)"
        )

        for log_file in self._iter_log_files():
            try:
                for line in log_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    m = pattern.search(line)
                    if m:
                        latencies.append({
                            "layer": m.group(1),
                            "duration_ms": int(m.group(2))
                        })
            except Exception as e:
                logger.warning(f"[LogObsRepo] Failed to parse {log_file}: {e}")

        if not latencies:
            return {"span": span, "avg_latency_ms": None, "sample_count": 0}

        avg = sum(r["duration_ms"] for r in latencies) / len(latencies)
        return {"span": span, "avg_latency_ms": round(avg, 2), "sample_count": len(latencies)}

    def get_failure_rates(
        self,
        reason: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Parse existing log files to count failures for a reason code.
        Informational only - log loss does not imply actual zero failures.
        Pattern: 'FAILURE reason=<reason> layer=<layer>'
        """
        failures = 0
        total = 0
        pattern = re.compile(
            r"FAILURE reason=" + re.escape(reason) + r" layer=(\w+)"
        )
        total_pattern = re.compile(r"REQUEST span=\w+ layer=\w+")

        for log_file in self._iter_log_files():
            try:
                text = log_file.read_text(encoding="utf-8", errors="ignore")
                failures += len(pattern.findall(text))
                total += len(total_pattern.findall(text))
            except Exception as e:
                logger.warning(f"[LogObsRepo] Failed to parse {log_file}: {e}")

        rate = round(failures / total, 4) if total > 0 else 0.0
        return {
            "reason": reason,
            "failure_count": failures,
            "total_count": total,
            "failure_rate": rate,
        }

    def get_cache_hit_rate(self) -> Dict[str, Any]:
        """
        Parse log files to estimate Redis hit/miss rates (observational).
        Informational ONLY. Not used as business metric.
        Pattern: 'CACHE_HIT key=...' or 'CACHE_MISS key=...'
        """
        hits = 0
        misses = 0
        hit_p = re.compile(r"CACHE_HIT key=")
        miss_p = re.compile(r"CACHE_MISS key=")

        for log_file in self._iter_log_files():
            try:
                text = log_file.read_text(encoding="utf-8", errors="ignore")
                hits += len(hit_p.findall(text))
                misses += len(miss_p.findall(text))
            except Exception:
                pass

        total = hits + misses
        hit_rate = round(hits / total, 4) if total > 0 else 0.0
        return {"hit_count": hits, "miss_count": misses, "hit_rate": hit_rate, "total_requests": total}
