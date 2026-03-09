/**
 * AdminJobStats — Slice E: Admin Stats Dashboard (TASK-FRONT-001)
 *
 * Contracts enforced:
 * - Stats Snapshot Drift Guard: Stats data is NEVER merged/inferred with session projection
 * - Stats TTL: 60s freshness window; auto-refetch FORBIDDEN; only manual refresh
 * - Stale state: shown when TTL expires OR on fetch failure (last success data preserved)
 * - Failure handling: last successful data preserved; Stale banner + RAW error + Copy for Support
 * - 403 role boundary: redirect to /admin/postings
 * - No SSE; no polling; no candidate store import
 * - 0 values shown as 0 (never null/-)
 * - Observability: Copy for Support includes trace_id, job_id, received_at, stats_version
 * - DECIDED + EVALUATED only notice fixed at top of screen
 */

import React, { useState, useCallback, useRef, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { createTraceId, ActionTrace } from '../../lib/traceId'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'
import { Doughnut } from 'react-chartjs-2'

ChartJS.register(ArcElement, Tooltip, Legend)

const TTL_SECONDS = 60

function getTokenHeader() {
    return { Authorization: `Bearer ${localStorage.getItem('imh_token')}` }
}

function buildSupportPayload({ jobId, traceId, receivedAt, statsVersion }) {
    return [
        `job_id: ${jobId || 'N/A'}`,
        `trace_id: ${traceId || 'N/A'}`,
        `received_at: ${receivedAt || 'N/A'}`,
        `stats_version: ${statsVersion || 'N/A'}`,
    ].join('\n')
}

export default function AdminJobStats() {
    const { jobId } = useParams()
    const navigate = useNavigate()

    // ── Isolated stats state — no session store, no projection merge ──────
    const [stats, setStats] = useState(null)          // Last successful fetch (preserved on failure)
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState(null)          // Fetch failure (stats preserved)
    const [isStale, setIsStale] = useState(false)     // TTL expired or fetch failed
    const [receivedAt, setReceivedAt] = useState(null)
    const [ttlRemaining, setTtlRemaining] = useState(null)  // seconds countdown
    const traceIdRef = useRef(null)
    const ttlTimerRef = useRef(null)
    const countdownRef = useRef(null)
    const [copyDone, setCopyDone] = useState(false)

    // ── TTL countdown ─────────────────────────────────────────────────────
    const startTTL = useCallback((fetchedAt) => {
        clearInterval(ttlTimerRef.current)
        clearInterval(countdownRef.current)
        setIsStale(false)

        const expireAt = fetchedAt + TTL_SECONDS * 1000

        const tick = () => {
            const remaining = Math.max(0, Math.floor((expireAt - Date.now()) / 1000))
            setTtlRemaining(remaining)
            if (remaining === 0) {
                // TTL expired — mark stale; NO auto-refetch
                setIsStale(true)
                clearInterval(countdownRef.current)
            }
        }
        tick()
        countdownRef.current = setInterval(tick, 1000)
    }, [])

    useEffect(() => {
        return () => {
            clearInterval(ttlTimerRef.current)
            clearInterval(countdownRef.current)
        }
    }, [])

    // ── Stats Fetch (Authority Pull equivalent for Stats — Step 1 only) ───
    // Stats are fetched from /jobs/{id}/stats; completely separate from session Pull
    const fetchStats = useCallback(async () => {
        if (isLoading) return
        const traceId = createTraceId()
        traceIdRef.current = traceId
        ActionTrace.trigger(traceId, `admin:stats:fetch:${jobId}`)
        setIsLoading(true)
        setError(null)

        try {
            const res = await fetch(`/api/v1/jobs/${jobId}/stats`, {
                headers: { ...getTokenHeader() },
            })

            if (res.status === 403) {
                navigate('/admin/postings')
                return
            }
            if (!res.ok) {
                const errData = await res.json().catch(() => ({}))
                throw {
                    error_code: errData.error_code || 'E_STATS_FETCH_FAILED',
                    trace_id: errData.trace_id || traceId,
                    status: res.status,
                    message: errData.detail || 'Stats 조회에 실패했습니다.',
                }
            }

            const data = await res.json()
            const now = Date.now()

            // Full snapshot replace — no merge with any previous stats or session data
            setStats(data)
            setReceivedAt(now)
            setIsStale(false)
            setError(null)   // Clear previous failure error on success
            startTTL(now)
            ActionTrace.stateApplied(traceId, `stats:success:job=${jobId}`)
        } catch (err) {
            // Failure: preserve last successful stats; show Stale banner + RAW error
            setIsStale(true)
            setError(err.error_code ? err : { error_code: 'E_STATS_FETCH_FAILED', trace_id: traceId, message: '통계 조회 실패' })
            // ttlRemaining: leave as-is (stale flag already set)
        } finally {
            setIsLoading(false)
        }
    }, [jobId, isLoading, navigate, startTTL])

    // ── Initial load on mount ─────────────────────────────────────────────
    useEffect(() => { fetchStats() }, [jobId])  // eslint-disable-line react-hooks/exhaustive-deps

    const copySupport = () => {
        navigator.clipboard?.writeText(buildSupportPayload({
            jobId,
            traceId: traceIdRef.current,
            receivedAt: receivedAt ? new Date(receivedAt).toISOString() : null,
            statsVersion: stats?.stats_version ?? null,
        })).then(() => { setCopyDone(true); setTimeout(() => setCopyDone(false), 1500) })
    }

    // ── Computed KPI display values (raw from server; no front-end derivation) ─
    const total = stats?.total_interviews ?? stats?.total_applicants ?? 0
    const decided = stats?.decided_count ?? 0
    const pass = stats?.pass_count ?? 0
    const fail = stats?.fail_count ?? decided - pass  // Engine-provided; fallback decided-pass if absent
    const passRate = stats?.pass_rate != null
        ? Number(stats.pass_rate).toFixed(2)
        : (decided > 0 ? ((pass / decided) * 100).toFixed(2) : '0.00')
    const avgScore = stats?.average_score != null ? Number(stats.average_score).toFixed(1) : null

    const pieData = {
        labels: ['합격', '불합격', '미결정'],
        datasets: [{
            data: [pass, Math.max(0, fail), Math.max(0, total - decided)],
            backgroundColor: ['rgba(34,197,94,0.8)', 'rgba(239,68,68,0.8)', 'rgba(107,114,128,0.4)'],
            borderWidth: 0,
        }],
    }
    const pieOptions = {
        plugins: { legend: { position: 'bottom', labels: { color: '#9CA3AF', font: { size: 12 }, padding: 16 } } },
        cutout: '65%',
    }

    return (
        <div>
            {/* Breadcrumb */}
            <div style={s.breadcrumb}>
                <Link to="/admin/postings" style={s.breadLink}>공고 관리</Link>
                {' / '}
                <span style={{ color: '#f1f5f9' }}>Stats</span>
            </div>

            {/* Page header */}
            <div style={s.pageHeader}>
                <div>
                    <h1 style={s.pageTitle}>Admin 통계 대시보드</h1>
                    <p style={s.pageSubtitle}>Job ID: <code style={s.jobIdCode}>{jobId}</code></p>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <button
                        id="stats-refresh-btn"
                        onClick={fetchStats}
                        disabled={isLoading}
                        style={s.refreshBtn}
                    >
                        {isLoading ? '조회 중...' : '새로고침'}
                    </button>
                    <button onClick={copySupport} style={s.smallBtnGhost}>
                        {copyDone ? '✓' : 'Copy for Support'}
                    </button>
                </div>
            </div>

            {/* ── DECIDED + EVALUATED only notice (always visible, at top) ── */}
            <div style={s.scopeNotice}>
                ℹ️ 이 통계는 <strong>DECIDED + EVALUATED</strong> 세션만 집계한 값입니다.
                진행 중(IN_PROGRESS/COMPLETED) 세션은 포함되지 않습니다.
            </div>

            {/* ── Stale banner (TTL expired OR fetch failed) ─────────────── */}
            {isStale && (
                <div style={s.staleBanner}>
                    ⏱ Stale Data — 마지막 성공 데이터가 표시됩니다. 새로고침을 눌러 갱신하세요.
                    {error && (
                        <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#f87171', marginLeft: 12 }}>
                            {error.error_code} · {error.trace_id || 'N/A'}
                        </span>
                    )}
                </div>
            )}

            {/* ── Fetch error detail (when no prior data exists) ────────── */}
            {error && !stats && (
                <div style={s.errorBox}>
                    <p style={{ fontFamily: 'monospace', color: '#f87171', fontSize: 13, margin: 0 }}>
                        {error.error_code} · {error.trace_id || 'N/A'}
                    </p>
                    {error.message && <p style={{ color: '#94a3b8', fontSize: 13, marginTop: 4 }}>{error.message}</p>}
                    <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                        <button onClick={fetchStats} disabled={isLoading} style={s.smallBtn}>재시도</button>
                        <button onClick={copySupport} style={s.smallBtnGhost}>{copyDone ? '✓' : 'Copy for Support'}</button>
                    </div>
                </div>
            )}

            {/* ── Fresh / TTL status bar ─────────────────────────────────── */}
            {stats && (
                <div style={s.ttlBar}>
                    <span style={{ ...s.freshBadge, ...(isStale ? s.staleBadge : {}) }}>
                        {isStale ? '⏱ Stale' : `✓ Fresh — ${ttlRemaining}s`}
                    </span>
                    {receivedAt && (
                        <span style={s.tsLabel}>
                            조회 시각: {new Date(receivedAt).toLocaleTimeString('ko-KR')}
                        </span>
                    )}
                </div>
            )}

            {/* ── Loading spinner (initial only) ────────────────────────── */}
            {isLoading && !stats && (
                <div style={s.centered}>
                    <div style={s.spinner} />
                    <p style={{ color: '#64748b', marginTop: 12 }}>통계 조회 중...</p>
                </div>
            )}

            {/* ── KPI Cards ─────────────────────────────────────────────── */}
            {stats && (
                <>
                    <div style={s.kpiGrid}>
                        <KpiCard icon="📋" label="총 면접" value={total} color="#6366f1" />
                        <KpiCard icon="⚖️" label="DECIDED" value={decided} color="#a78bfa" />
                        <KpiCard icon="✅" label="합격" value={pass} color="#22c55e" />
                        <KpiCard icon="❌" label="불합격" value={Math.max(0, fail)} color="#ef4444" />
                        <KpiCard icon="📈" label="합격률" value={`${passRate}%`} color="#f59e0b" raw />
                        {avgScore !== null && (
                            <KpiCard icon="⭐" label="평균 점수" value={avgScore} color="#38bdf8" raw />
                        )}
                    </div>

                    {/* Doughnut chart */}
                    <div style={s.chartRow}>
                        <div style={s.chartCard}>
                            <div style={s.chartTitle}>DECIDED 기준 합격/불합격 분포</div>
                            {decided > 0 ? (
                                <Doughnut data={pieData} options={pieOptions} />
                            ) : (
                                <p style={{ color: '#475569', textAlign: 'center', marginTop: 32 }}>
                                    DECIDED 세션이 없습니다.
                                </p>
                            )}
                        </div>

                        {/* Raw snapshot info (admin observability) */}
                        <div style={s.rawBox}>
                            <div style={s.rawTitle}>서버 응답 메타데이터 (Admin)</div>
                            {[
                                ['stats_version', stats.stats_version ?? 'N/A'],
                                ['snapshot_at', stats.snapshot_at ?? stats.last_updated_at ?? 'N/A'],
                                ['scope', 'DECIDED + EVALUATED only'],
                            ].map(([k, v]) => (
                                <div key={k} style={s.rawRow}>
                                    <span style={s.rawKey}>{k}</span>
                                    <code style={s.rawVal}>{String(v)}</code>
                                </div>
                            ))}
                        </div>
                    </div>
                </>
            )}
        </div>
    )
}

function KpiCard({ icon, label, value, color, raw }) {
    return (
        <div style={{ ...s.kpiCard, borderTop: `3px solid ${color}` }}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>{icon}</div>
            <div style={{ fontSize: raw ? 22 : 28, fontWeight: 800, color, letterSpacing: '-0.5px' }}>
                {/* 0 values shown as 0 (never null) */}
                {value ?? 0}
            </div>
            <div style={s.kpiLabel}>{label}</div>
        </div>
    )
}

const s = {
    breadcrumb: { fontSize: 12, color: '#64748b', marginBottom: 4 },
    breadLink: { color: '#64748b', textDecoration: 'none' },
    pageHeader: {
        display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
        marginBottom: 16,
    },
    pageTitle: { fontSize: 22, fontWeight: 700, color: '#f1f5f9', margin: '0 0 4px' },
    pageSubtitle: { color: '#64748b', fontSize: 13, margin: 0 },
    jobIdCode: { color: '#a5b4fc', fontFamily: 'monospace', fontSize: 13 },
    scopeNotice: {
        background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.25)',
        borderRadius: 8, padding: '10px 16px', marginBottom: 16,
        color: '#a5b4fc', fontSize: 13,
    },
    staleBanner: {
        background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.3)',
        borderRadius: 8, padding: '10px 16px', marginBottom: 12,
        color: '#fde047', fontSize: 13, display: 'flex', alignItems: 'center', flexWrap: 'wrap',
    },
    errorBox: {
        background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)',
        borderRadius: 8, padding: '12px 16px', marginBottom: 16,
    },
    ttlBar: {
        display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20,
    },
    freshBadge: {
        padding: '3px 12px', borderRadius: 99, fontSize: 12, fontWeight: 700,
        background: 'rgba(34,197,94,0.1)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.3)',
    },
    staleBadge: {
        background: 'rgba(245,158,11,0.1)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.3)',
    },
    tsLabel: { color: '#475569', fontSize: 12 },
    centered: { display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '48px 0' },
    spinner: {
        width: 36, height: 36,
        border: '3px solid rgba(99,102,241,0.2)', borderTopColor: '#6366f1',
        borderRadius: '50%', animation: 'spin 0.8s linear infinite',
    },
    kpiGrid: {
        display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
        gap: 16, marginBottom: 24,
    },
    kpiCard: {
        background: '#1e293b', borderRadius: 12, padding: '20px 16px',
        border: '1px solid #334155', textAlign: 'center',
    },
    kpiLabel: { color: '#64748b', fontSize: 12, fontWeight: 600, marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.05em' },
    chartRow: { display: 'grid', gridTemplateColumns: '280px 1fr', gap: 24, marginBottom: 24 },
    chartCard: {
        background: '#1e293b', border: '1px solid #334155', borderRadius: 12,
        padding: '16px 20px',
    },
    chartTitle: { fontSize: 12, color: '#64748b', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 16 },
    rawBox: {
        background: '#1e293b', border: '1px solid #334155', borderRadius: 12,
        padding: '16px 20px',
    },
    rawTitle: { fontSize: 12, color: '#64748b', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 },
    rawRow: { display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 8 },
    rawKey: { color: '#475569', fontSize: 12, minWidth: 120 },
    rawVal: { color: '#a5b4fc', fontSize: 12, fontFamily: 'monospace', wordBreak: 'break-all' },
    refreshBtn: {
        padding: '8px 18px',
        background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.3)',
        borderRadius: 8, color: '#a5b4fc', cursor: 'pointer', fontSize: 13, fontWeight: 600,
    },
    smallBtn: {
        padding: '5px 12px', background: 'rgba(99,102,241,0.15)',
        border: '1px solid rgba(99,102,241,0.3)', borderRadius: 6,
        color: '#a5b4fc', cursor: 'pointer', fontSize: 12,
    },
    smallBtnGhost: {
        padding: '5px 12px', background: 'transparent',
        border: '1px solid #334155', borderRadius: 6,
        color: '#64748b', cursor: 'pointer', fontSize: 12,
    },
}
