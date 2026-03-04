/**
 * InterviewResult — Slice C: Result Screen (TASK-FRONT-001)
 *
 * Contracts enforced:
 * - Authority Pull 2-Step: Step 1 (GET /sessions/{id}) on every entry; no cached snapshot reuse
 * - Evaluating vs Finalized: Strictly server snapshot-driven; no front-end assumption
 * - Result Visibility Guard (ACTUAL vs PRACTICE): DOM removal (not hidden) for score/evidence
 * - Evaluation Finalization Lock: no recalculation/re-sort after DECIDED
 * - Admin Authority Boundary: evaluation_input_hash never shown in candidate view
 * - SSE for change detection only (canMutate = always false on this screen)
 * - SAFE_MODE: Read-Only banner + Copy for Support (trace_id/session_id/snapshot_hash/event_seq)
 * - No polling: SSE handles state change; manual "Refresh" via authority pull only
 * - Observability: errors include trace_id, session_id, event_seq, snapshot_hash
 * - No-Template Fallback: no placeholder result text; error overlay if data missing
 */

import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useSessionStore } from '../../stores/sessionStore'
import { useSSEProjection, SSE_STATUS } from '../../hooks/useSSEProjection'
import ErrorBanner from '../../components/ErrorBanner'
import { createTraceId, ActionTrace } from '../../lib/traceId'

const TERMINAL_STATUSES = new Set(['ABORTED', 'DECIDED', 'EVALUATED'])
const EVAL_IN_PROGRESS = new Set(['COMPLETED'])  // Server status meaning "eval running"

function getTokenHeader() {
    return { Authorization: `Bearer ${localStorage.getItem('imh_token')}` }
}

// ── Copy for Support payload (Observability tags) ────────────────────────────
function buildSupportPayload({ sessionId, traceId, snapshotHash, eventSeq }) {
    return [
        `session_id: ${sessionId || 'N/A'}`,
        `trace_id: ${traceId || 'N/A'}`,
        `snapshot_hash: ${snapshotHash || 'N/A'}`,
        `event_seq: ${eventSeq != null ? eventSeq : 'N/A'}`,
    ].join('\n')
}

export default function InterviewResult() {
    const { interviewId } = useParams()
    const navigate = useNavigate()

    // ── Local result state (ephemeral — never persisted; DOM-removed on page leave) ─
    const [snapshot, setSnapshot] = useState(null)       // Raw Step 1 server snapshot
    const [resultData, setResultData] = useState(null)   // Evaluation result (ephemeral)
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState(null)
    const [isSafeMode, setIsSafeMode] = useState(false)
    const [isStaleBanner, setIsStaleBanner] = useState(false)
    const [hydrated, setHydrated] = useState(false)
    const [copyDone, setCopyDone] = useState(false)

    // SSE seq tracking for observability
    const lastSeqRef = useRef(0)
    const lastHashRef = useRef(null)
    const traceIdRef = useRef(null)

    // ── Authority Pull (Step 1 + optional Step 2) ────────────────────────────
    const performAuthorityPull = useCallback(async () => {
        const traceId = createTraceId()
        traceIdRef.current = traceId
        ActionTrace.trigger(traceId, 'result:authority-pull')
        setIsLoading(true)
        setError(null)

        try {
            // Step 1: PG Authority Snapshot (mandatory)
            const sessionRes = await fetch(`/api/v1/interviews/${interviewId}`, {
                headers: { ...getTokenHeader() },
            })
            if (!sessionRes.ok) {
                const errData = await sessionRes.json().catch(() => ({}))
                throw { error_code: errData.error_code || 'E_PULL_FAILED', trace_id: traceId, status: sessionRes.status }
            }
            const session = await sessionRes.json()
            ActionTrace.stateApplied(traceId, 'Step1:success')

            // Step 2: fetch result/evaluation data (separate from session snapshot)
            let evaluation = null
            try {
                const resultRes = await fetch(`/api/v1/interviews/${interviewId}/result`, {
                    headers: { ...getTokenHeader() },
                })
                if (resultRes.ok) {
                    evaluation = await resultRes.json()
                    ActionTrace.stateApplied(traceId, 'Step2:result')
                }
            } catch {
                // Step 2 unavailable → evaluation pending; no error
            }

            // Full overwrite — no merge
            setSnapshot(session)
            setResultData(evaluation)  // null = evaluating in progress or unavailable
            lastHashRef.current = session.snapshot_hash ?? null
            setHydrated(true)
            setIsSafeMode(false)
        } catch (err) {
            const normalizedError = err.error_code ? err : {
                error_code: 'E_PULL_FAILED',
                trace_id: traceId,
                session_id: interviewId,
                snapshot_hash: lastHashRef.current || 'N/A',
                event_seq: lastSeqRef.current || 'N/A',
                message: '결과를 불러오지 못했습니다.',
            }
            if (!hydrated) {
                // Never shown result before: surface error
                setError(normalizedError)
            } else {
                // Previous snapshot exists: show SAFE_MODE + keep last data
                setIsSafeMode(true)
                setError(normalizedError)
            }
        } finally {
            setIsLoading(false)
        }
    }, [interviewId, hydrated])

    // ── Initial load ─────────────────────────────────────────────────────────
    useEffect(() => {
        performAuthorityPull()
        return () => {
            // Ephemeral data cleared on unmount (Result Visibility Guard: no persistent storage)
            setResultData(null)
            setSnapshot(null)
        }
    }, [interviewId])  // eslint-disable-line react-hooks/exhaustive-deps

    // ── SSE: change detection only (canMutate always false here) ────────────
    const handleSSEEvent = useCallback((data) => {
        if (data.event_seq) lastSeqRef.current = data.event_seq
        if (data.snapshot_hash) lastHashRef.current = data.snapshot_hash

        // If server signals evaluation is now complete → trigger authority pull
        const newStatus = data.status
        if (newStatus && (TERMINAL_STATUSES.has(newStatus) || newStatus === 'EVALUATED')) {
            performAuthorityPull()
        }
    }, [performAuthorityPull])

    // SSE on result screen — change detection only; no projection store (results screen is standalone)
    const { sseStatus } = useSSEProjection(interviewId, {
        isPullLocked: false,   // Result screen never locks SSE (read-only; no mutation conflict)
        lastAppliedSeq: lastSeqRef.current,
        onAuthorityPull: performAuthorityPull,
        onEvent: handleSSEEvent,
        onStaleModeChange: setIsStaleBanner,
    })

    // ── Derived display values from server snapshot (no front-end recalculation) ─
    const serverStatus = snapshot?.status ?? null
    const interviewMode = snapshot?.interview_mode ?? snapshot?.mode ?? null  // ACTUAL | PRACTICE | null
    const isPractice = interviewMode === 'PRACTICE'

    // Evaluating vs Finalized: strictly from server snapshot (No Assumption Rule)
    // - COMPLETED + evaluation pending = evaluating
    // - DECIDED or EVALUATED = finalized
    // - evaluation_status field present → use it; absent → use status enum only
    const evalStatus = resultData?.evaluation_status ?? null
    const isEvaluating = (() => {
        if (!serverStatus) return true  // still loading
        if (evalStatus === 'IN_PROGRESS') return true
        if (evalStatus === 'COMPLETED') return false
        if (EVAL_IN_PROGRESS.has(serverStatus) && !resultData) return true
        return false
    })()
    const isFinalized = !isEvaluating && (
        serverStatus === 'DECIDED' || serverStatus === 'EVALUATED' || evalStatus === 'COMPLETED'
    )
    const isAborted = serverStatus === 'ABORTED'

    // ── Result Visibility Guard (ACTUAL vs PRACTICE) ─────────────────────────
    // decision: shown post-finalized for both modes (ACTUAL: only after result_sent; PRACTICE: immediate)
    // score/evidence: DOM REMOVED for candidates in all cases
    const resultSent = snapshot?.result_sent ?? false
    const canShowDecision = isFinalized && !isAborted && (
        isPractice || resultSent  // ACTUAL: only if result_sent is true
    )

    // score/evidence: NEVER rendered in candidate view (DOM removal enforced)
    // evaluation_input_hash: NEVER rendered in candidate view (Admin boundary)
    const decision = canShowDecision ? (resultData?.evaluation?.decision ?? resultData?.decision ?? null) : null
    // Summary: shown if finalized and explicitly provided by server
    const summary = canShowDecision ? (resultData?.evaluation?.summary ?? resultData?.summary ?? null) : null

    // ── Copy for Support ─────────────────────────────────────────────────────
    const handleCopySupport = useCallback(() => {
        const payload = buildSupportPayload({
            sessionId: interviewId,
            traceId: traceIdRef.current,
            snapshotHash: lastHashRef.current,
            eventSeq: lastSeqRef.current,
        })
        navigator.clipboard?.writeText(payload).then(() => {
            setCopyDone(true)
            setTimeout(() => setCopyDone(false), 2000)
        })
    }, [interviewId])

    // ── Manual refresh (no auto-retry) ───────────────────────────────────────
    const handleManualRefresh = useCallback(async (e) => {
        e?.preventDefault()
        await performAuthorityPull()
    }, [performAuthorityPull])

    // ── Loading ───────────────────────────────────────────────────────────────
    if (isLoading && !hydrated) {
        return (
            <div style={styles.page}>
                <div style={styles.centerBox}>
                    <div style={styles.spinner} />
                    <p style={{ color: '#64748b', marginTop: 16 }}>결과를 불러오는 중...</p>
                </div>
            </div>
        )
    }

    return (
        <div style={styles.page}>
            {/* SSE status indicator (non-intrusive) */}
            <div style={styles.topBar}>
                <span style={{ color: '#475569', fontSize: 12 }}>면접 결과</span>
                <span style={{ ...styles.sseChip, ...(sseStatus === SSE_STATUS.LIVE ? styles.sseLive : styles.sseStale) }}>
                    {sseStatus === SSE_STATUS.LIVE ? '● 실시간' : `● ${sseStatus}`}
                </span>
            </div>

            {isStaleBanner && (
                <div style={styles.staleBanner}>📡 연결 불안정 — 화면은 마지막 성공 snapshot 기준으로 유지됩니다.</div>
            )}

            {/* SAFE_MODE banner */}
            {isSafeMode && (
                <div style={styles.safeModeBanner}>
                    🔒 오프라인 – 읽기 전용
                    <button onClick={handleCopySupport} style={styles.copyBtn}>
                        {copyDone ? '✓ 복사됨' : 'Copy for Support'}
                    </button>
                    {error && (
                        <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#64748b', marginLeft: 12 }}>
                            {error.error_code} · {error.trace_id || 'N/A'}
                        </span>
                    )}
                </div>
            )}

            <ErrorBanner error={!isSafeMode ? error : null} onDismiss={() => setError(null)} />

            {/* ── Aborted ───────────────────────────────────────────────── */}
            {isAborted && (
                <div style={styles.abortedCard}>
                    <div style={styles.abortIcon}>🚫</div>
                    <h2 style={{ color: '#f1f5f9', marginBottom: 8 }}>면접 중단</h2>
                    <p style={{ color: '#94a3b8', textAlign: 'center', maxWidth: 400 }}>
                        면접이 중단되었습니다. 결과가 생성되지 않습니다.
                    </p>
                    <div style={styles.navRow}>
                        <button id="back-home-aborted" onClick={() => navigate('/candidate/home')} style={styles.navBtn}>홈으로</button>
                    </div>
                </div>
            )}

            {/* ── Evaluating in progress ────────────────────────────────── */}
            {!isAborted && isEvaluating && (
                <div style={styles.pendingCard}>
                    <div style={styles.pendingIcon}>⏳</div>
                    <h2 style={{ color: '#f1f5f9', marginBottom: 8 }}>평가 처리 중</h2>
                    <p style={{ color: '#94a3b8', textAlign: 'center', maxWidth: 400 }}>
                        AI가 면접 내용을 분석하고 있습니다. 이 페이지에서 이동하셔도 평가는 계속 진행됩니다.
                    </p>
                    <div style={styles.pulseDot} />
                    {/* Manual refresh only — no auto-polling */}
                    <button
                        onClick={handleManualRefresh}
                        style={styles.refreshBtn}
                        disabled={isLoading}
                    >
                        {isLoading ? '확인 중...' : '상태 확인'}
                    </button>
                </div>
            )}

            {/* ── Finalized: Result View ────────────────────────────────── */}
            {!isAborted && isFinalized && (
                <div style={styles.resultCard}>
                    {/* Decision — only shown when policy allows */}
                    {canShowDecision && decision ? (
                        <div style={{ textAlign: 'center', marginBottom: 32 }}>
                            <div style={{
                                ...styles.decisionBadge,
                                background: decision === 'PASS'
                                    ? 'linear-gradient(135deg, #16a34a, #22c55e)'
                                    : 'linear-gradient(135deg, #dc2626, #ef4444)',
                            }}>
                                {decision === 'PASS' ? '✅ 합격' : '❌ 불합격'}
                            </div>
                            <p style={{ color: '#94a3b8', marginTop: 12, fontSize: 14 }}>
                                {snapshot?.job_title || '면접 결과'}
                                {isPractice && (
                                    <span style={styles.practiceBadge}> PRACTICE</span>
                                )}
                            </p>
                        </div>
                    ) : (
                        /* ACTUAL: result_sent=false → no decision shown; no placeholder text */
                        !isPractice && !resultSent && (
                            <div style={styles.pendingResultBox}>
                                <p style={{ color: '#94a3b8', textAlign: 'center' }}>
                                    평가가 완료되었습니다. 결과는 담당자를 통해 전달됩니다.
                                </p>
                            </div>
                        )
                    )}

                    {/* Summary — server-provided only; no template fallback */}
                    {summary && (
                        <div style={styles.summaryBox}>
                            <h3 style={styles.sectionTitle}>종합 평가</h3>
                            <p style={{ color: '#cbd5e1', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{summary}</p>
                        </div>
                    )}

                    {/* score/evidence: NEVER rendered in candidate view — DOM removal enforced */}
                    {/* evaluation_input_hash: NEVER rendered in candidate view */}

                    {/* Mode badge */}
                    <div style={styles.modeBadgeRow}>
                        <span style={{ ...styles.modeBadge, ...(isPractice ? styles.practiceMode : styles.actualMode) }}>
                            {isPractice ? '연습 모드' : '실전 모드'}
                        </span>
                        {interviewMode && (
                            <span style={{ color: '#475569', fontSize: 12 }}>{snapshot?.job_title}</span>
                        )}
                    </div>

                    {/* Navigation */}
                    <div style={styles.navRow}>
                        <button
                            id="back-to-home-btn"
                            onClick={() => navigate('/candidate/home')}
                            style={styles.navBtn}
                        >
                            홈으로
                        </button>
                        <button
                            id="view-postings-btn"
                            onClick={() => navigate('/candidate/postings')}
                            style={{ ...styles.navBtn, ...styles.navBtnPrimary }}
                        >
                            다른 공고 보기
                        </button>
                    </div>

                    {/* Copy for Support (observability tags hidden from UI but copyable) */}
                    <div style={styles.supportRow}>
                        <button onClick={handleCopySupport} style={styles.copyBtnSmall}>
                            {copyDone ? '✓ 복사됨' : 'Copy for Support'}
                        </button>
                    </div>
                </div>
            )}
        </div>
    )
}

const styles = {
    page: {
        minHeight: '80vh', padding: '24px 24px 48px',
        maxWidth: 640, margin: '0 auto',
    },
    topBar: {
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginBottom: 16,
    },
    sseChip: { padding: '2px 8px', borderRadius: 99, fontSize: 12, fontWeight: 600 },
    sseLive: { color: '#22c55e', background: 'rgba(34,197,94,0.1)' },
    sseStale: { color: '#f59e0b', background: 'rgba(245,158,11,0.1)' },
    staleBanner: {
        background: 'rgba(234,179,8,0.1)', border: '1px solid rgba(234,179,8,0.3)',
        color: '#fde047', padding: '8px 16px', borderRadius: 8, fontSize: 13,
        marginBottom: 12, textAlign: 'center',
    },
    safeModeBanner: {
        background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
        color: '#fca5a5', padding: '10px 16px', borderRadius: 8, fontSize: 13,
        marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
    },
    centerBox: {
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', minHeight: '60vh',
    },
    spinner: {
        width: 44, height: 44,
        border: '4px solid rgba(59,130,246,0.2)', borderTopColor: '#3b82f6',
        borderRadius: '50%', animation: 'spin 0.8s linear infinite',
    },
    abortedCard: {
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', minHeight: '60vh', gap: 12,
    },
    abortIcon: { fontSize: 64, marginBottom: 8 },
    pendingCard: {
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', minHeight: '60vh', gap: 12,
    },
    pendingIcon: { fontSize: 64, animation: 'pulse 2s ease-in-out infinite' },
    pulseDot: {
        width: 10, height: 10, background: '#3b82f6', borderRadius: '50%',
        marginTop: 8, animation: 'pulse 1.5s ease-in-out infinite',
    },
    refreshBtn: {
        marginTop: 12, padding: '8px 20px',
        background: 'rgba(59,130,246,0.1)', border: '1px solid #3b82f6',
        borderRadius: 6, color: '#60a5fa', cursor: 'pointer', fontSize: 13,
    },
    resultCard: {
        background: '#1e293b', borderRadius: 16, padding: 32,
        border: '1px solid #334155',
    },
    decisionBadge: {
        display: 'inline-flex', alignItems: 'center', gap: 8,
        padding: '12px 32px', borderRadius: 12, fontSize: 22,
        fontWeight: 800, color: '#fff',
    },
    practiceBadge: {
        background: 'rgba(59,130,246,0.15)', color: '#60a5fa',
        padding: '1px 8px', borderRadius: 99, fontSize: 11,
        border: '1px solid rgba(59,130,246,0.3)',
    },
    pendingResultBox: {
        padding: '20px 24px', background: 'rgba(15,23,42,0.6)',
        borderRadius: 10, border: '1px solid #1e293b', marginBottom: 24,
    },
    summaryBox: {
        background: '#0f172a', borderRadius: 10, padding: '16px 20px',
        marginBottom: 24, border: '1px solid #1e293b',
    },
    sectionTitle: {
        color: '#94a3b8', fontSize: 13, fontWeight: 600,
        textTransform: 'uppercase', letterSpacing: '0.1em',
        marginBottom: 12, marginTop: 0,
    },
    modeBadgeRow: {
        display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24,
    },
    modeBadge: { padding: '3px 12px', borderRadius: 99, fontSize: 12, fontWeight: 600 },
    practiceMode: { background: 'rgba(59,130,246,0.15)', color: '#60a5fa', border: '1px solid rgba(59,130,246,0.3)' },
    actualMode: { background: 'rgba(239,68,68,0.15)', color: '#f87171', border: '1px solid rgba(239,68,68,0.3)' },
    navRow: { display: 'flex', gap: 12, justifyContent: 'center', marginTop: 24 },
    navBtn: {
        padding: '10px 24px', background: 'transparent',
        border: '1px solid #334155', borderRadius: 8,
        color: '#94a3b8', cursor: 'pointer', fontSize: 14,
    },
    navBtnPrimary: {
        background: 'linear-gradient(135deg, #1d4ed8, #4338ca)',
        border: 'none', color: '#fff', fontWeight: 600,
    },
    supportRow: { marginTop: 16, textAlign: 'center' },
    copyBtn: {
        padding: '4px 12px', background: 'transparent',
        border: '1px solid #334155', borderRadius: 6,
        color: '#64748b', cursor: 'pointer', fontSize: 12,
    },
    copyBtnSmall: {
        padding: '4px 12px', background: 'transparent',
        border: '1px solid #334155', borderRadius: 6,
        color: '#64748b', cursor: 'pointer', fontSize: 11,
    },
}
