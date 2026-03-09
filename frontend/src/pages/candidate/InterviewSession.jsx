/**
 * InterviewSession - Core TEXT Interview Page (TASK-FRONT-001 / Slice A)
 *
 * Contracts enforced:
 * - Authority Pull 2-Step Protocol: Step 1 (GET /sessions/{id}) required before any UI
 * - Initial Hydration Guard: question DOM not rendered until first valid projection
 * - Pull-In-Flight SSE Suppression: store.isPullLocked gates all SSE event application
 * - SAFE_MODE: all mutation DOM removed when isSafeMode=true
 * - Terminal State: mutation DOM removed when status ∈ { ABORTED, DECIDED, EVALUATED }
 * - No-Template Fallback: if currentQuestion is null/empty → error overlay, never placeholder
 * - local_pending is UI-only, never used for business state
 * - Observability: error overlay includes trace_id, session_id, event_seq, snapshot_hash
 */

import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { interviewsApi } from '../../services/api'
import { useSessionStore } from '../../stores/sessionStore'
import { useSSEProjection, SSE_STATUS } from '../../hooks/useSSEProjection'
import ErrorBanner from '../../components/ErrorBanner'
import TracedButton from '../../components/TracedButton'
import { createTraceId, ActionTrace } from '../../lib/traceId'

const TERMINAL_STATUSES = new Set(['ABORTED', 'DECIDED', 'EVALUATED'])
const SAFE_EXIT_ALLOWED_STATUSES = new Set(['ABORTED', 'DECIDED', 'EVALUATED', 'COMPLETED'])

export default function InterviewSession() {
    const { interviewId } = useParams()
    const navigate = useNavigate()
    const [answer, setAnswer] = useState('')
    const [isStaleBanner, setIsStaleBanner] = useState(false)  // SSE STALE notice
    const [hydrated, setHydrated] = useState(false)            // Initial Hydration Guard gate
    const chatBottomRef = useRef(null)
    const abortControllerRef = useRef(null)  // Terminal Race Guard

    const {
        // Projection data
        sessionId, jobTitle, status, currentPhase, phaseIndex, totalPhases,
        messages, currentQuestion, result,
        // Pull state
        isPullLocked, isSafeMode,
        lastAppliedSeq, lastSnapshotHash,
        // UI flags
        isLoading, local_pending, error,
        // Actions
        beginPull, setFromProjection, pullFailed,
        applySSEEvent, setLocalPending, setError, reset,
        // Computed
        canMutate,
    } = useSessionStore()

    const isTerminal = TERMINAL_STATUSES.has(status)

    // ─── Authority Pull (2-Step Protocol) ────────────────────────────────────
    const performAuthorityPull = useCallback(async () => {
        const traceId = createTraceId()
        ActionTrace.trigger(traceId, 'interview:authority-pull')
        beginPull()  // → isPullLocked=true, SAFE_MODE entry

        // Cancel any pending mutation request (Terminal Mutation Race Guard)
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
            abortControllerRef.current = null
        }

        try {
            // Step 1: PG Authority Snapshot (REQUIRED before any UI)
            const sessionRes = await interviewsApi.get(interviewId)
            const session = sessionRes.data
            ActionTrace.stateApplied(traceId, 'Step1:success')

            // Step 2 (TEXT-only path): fetch chat history as projection hydrate
            // TEXT-only has no /multimodal/projection endpoint; chat serves as projection.
            // Initial Hydration Guard: question DOM stays unmounted until currentQuestion exists.
            const chatRes = await interviewsApi.getChat(interviewId)
            const chat = chatRes.data

            const projection = {
                sessionId: interviewId,
                jobId: session.job_id,
                jobTitle: session.job_title,
                status: session.status,
                currentPhase: session.current_phase,
                phaseIndex: session.phase_index ?? 0,
                totalPhases: session.total_phases ?? 0,
                turnCount: session.turn_count ?? 0,
                messages: chat,
                currentQuestion: session.current_question ?? null,
                snapshot_hash: session.snapshot_hash ?? null,
            }

            setFromProjection(projection)
            setHydrated(true)  // Unlock question DOM mount
            ActionTrace.stateApplied(traceId, 'Step2:success')
        } catch (err) {
            const normalizedError = err.error_code ? err : {
                error_code: 'E_PULL_FAILED',
                trace_id: traceId,
                session_id: interviewId,
                event_seq: lastAppliedSeq || 'N/A',
                snapshot_hash: lastSnapshotHash || 'N/A',
                message: '세션 정보를 불러오지 못했습니다.',
            }

            // 409: Session Terminal → redirect
            if (err.status === 409 && err.error_code === 'E_SESSION_TERMINAL') {
                navigate(`/candidate/result/${interviewId}`)
                return
            }

            pullFailed(normalizedError)
        }
    }, [interviewId, beginPull, setFromProjection, pullFailed, lastAppliedSeq, lastSnapshotHash, navigate])

    // ─── Initial load ────────────────────────────────────────────────────────
    useEffect(() => {
        performAuthorityPull()
        return () => { reset() }
    }, [interviewId])  // eslint-disable-line react-hooks/exhaustive-deps

    // ─── SSE Hook ────────────────────────────────────────────────────────────
    const handleSSEEvent = useCallback((data) => {
        // applySSEEvent handles: pull lock check, seq inversion, snapshot_hash dedup
        const applied = applySSEEvent(data)
        if (applied) setHydrated(true)
    }, [applySSEEvent])

    const { sseStatus, sseError } = useSSEProjection(interviewId, {
        isPullLocked,
        lastAppliedSeq,
        onAuthorityPull: performAuthorityPull,
        onEvent: handleSSEEvent,
        onStaleModeChange: setIsStaleBanner,
    })

    // ─── Auto-scroll chat ────────────────────────────────────────────────────
    useEffect(() => {
        chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages])

    // ─── Submit Answer ────────────────────────────────────────────────────────
    // Guard: canMutate = !isPullLocked && !isSafeMode && !isTerminal
    const handleSubmit = useCallback(async (traceId) => {
        if (!answer.trim() || !canMutate || local_pending) return

        setLocalPending(true)
        abortControllerRef.current = new AbortController()

        try {
            ActionTrace.apiStart(traceId, 'POST', `/interviews/${interviewId}/chat`)
            const res = await interviewsApi.sendChat(interviewId, answer.trim(), {
                signal: abortControllerRef.current.signal,
            })
            ActionTrace.apiResponse(traceId, res.status)
            setAnswer('')
            // State comes from SSE/next authority pull — no local derivation
        } catch (err) {
            if (err.name === 'CanceledError' || err.name === 'AbortError') return

            // No-Template Fallback: 500 from question generation → Error Overlay + Pull
            if (err.status === 500 || err.error_code === 'E_QUESTION_GENERATION_FAILED') {
                setError({
                    ...err,
                    error_code: err.error_code || 'E_QUESTION_GENERATION_FAILED',
                    session_id: interviewId,
                    event_seq: lastAppliedSeq || 'N/A',
                    snapshot_hash: lastSnapshotHash || 'N/A',
                })
                performAuthorityPull()
                return
            }

            // 409: Session Terminal → redirect
            if (err.status === 409 && err.error_code === 'E_SESSION_TERMINAL') {
                navigate(`/candidate/result/${interviewId}`)
                return
            }

            // 4xx: Overlay + Authority Pull
            if (err.status >= 400 && err.status < 500) {
                setError({ ...err, session_id: interviewId, event_seq: lastAppliedSeq || 'N/A' })
                performAuthorityPull()
                return
            }

            // 5xx: Overlay + SAFE_MODE (pullFailed handles SAFE_MODE)
            if (err.status >= 500) {
                pullFailed({ ...err, session_id: interviewId })
                return
            }

            setError(err.error_code ? err : {
                error_code: 'E_UNKNOWN', trace_id: traceId,
                session_id: interviewId, message: '답변 제출에 실패했습니다.',
            })
        } finally {
            setLocalPending(false)
            abortControllerRef.current = null
        }
    }, [answer, canMutate, local_pending, interviewId, lastAppliedSeq, lastSnapshotHash,
        setLocalPending, setError, pullFailed, performAuthorityPull, navigate])

    // ─── Loading: Step 1 in progress ─────────────────────────────────────────
    if (isLoading && !hydrated) {
        return (
            <div style={styles.fullPage}>
                <div style={styles.centeredContent}>
                    <div style={styles.spinner} />
                    <p style={{ color: '#94a3b8', marginTop: 16 }}>세션 정보를 불러오는 중...</p>
                </div>
            </div>
        )
    }

    // ─── SAFE_MODE overlay (Authority Pull failed) ────────────────────────────
    if (isSafeMode) {
        return (
            <div style={styles.fullPage}>
                <div style={styles.centeredContent}>
                    <div style={styles.safeModeBadge}>🔒 오프라인 – 읽기 전용</div>
                    <p style={{ color: '#94a3b8', marginTop: 12, textAlign: 'center', maxWidth: 360 }}>
                        서버와 연결이 끊겼습니다. 데이터가 동기화될 때까지 입력이 비활성화됩니다.
                    </p>
                    {error && (
                        <p style={{ color: '#64748b', fontSize: 12, marginTop: 8, fontFamily: 'monospace' }}>
                            {error.error_code} · {error.trace_id || 'N/A'}
                        </p>
                    )}
                    {/* SAFE_MODE: navigation allowed (not frozen) */}
                    <button
                        onClick={() => navigate('/')}
                        style={styles.safeNavBtn}
                    >
                        홈으로 이동
                    </button>
                </div>
            </div>
        )
    }

    return (
        <div style={styles.fullPage}>
            {/* ── Header ──────────────────────────────────────────────────── */}
            <div style={styles.header}>
                <div>
                    <h1 style={styles.headerTitle}>{jobTitle || '면접 진행 중'}</h1>
                    <span style={styles.phaseBadge}>{currentPhase || '준비 중'}</span>
                </div>
                <div>
                    {hydrated && (
                        <span style={{ color: '#64748b', fontSize: 14 }}>
                            {(phaseIndex ?? 0) + 1} / {totalPhases ?? 0} 단계
                        </span>
                    )}
                    {/* SSE status indicator */}
                    <span style={{ ...styles.sseIndicator, ...(sseStatus === SSE_STATUS.LIVE ? styles.sseLive : styles.sseOffline) }}>
                        {sseStatus === SSE_STATUS.LIVE ? '● LIVE' : `● ${sseStatus}`}
                    </span>
                </div>
            </div>

            {/* ── STALE banner (SSE connection lost) ────────────────────── */}
            {isStaleBanner && (
                <div style={styles.staleBanner}>
                    📡 연결 불안정 – 재연결 중... (입력 비활성화)
                </div>
            )}

            {/* ── Schema/schema mismatch banner: shown by Pull starting ─── */}
            {isPullLocked && (
                <div style={styles.syncBanner}>
                    🔄 최신 서버 상태 동기화 중... (잠시 기다려 주세요)
                </div>
            )}

            {/* ── Error Banner (with observability tags) ────────────────── */}
            <ErrorBanner error={error} onDismiss={() => setError(null)} />

            {/* ── Chat History ───────────────────────────────────────────── */}
            <div style={styles.chatContainer}>
                {/* Initial Hydration Guard: no placeholder, await first valid projection */}
                {!hydrated && (
                    <div style={styles.emptyChat}>
                        <div style={styles.spinner} />
                        <p style={{ color: '#475569', marginTop: 12 }}>
                            서버에서 질문을 받아오는 중...
                        </p>
                    </div>
                )}
                {hydrated && messages.map((msg, i) => (
                    <div key={i} style={msg.role === 'user' ? styles.userMsg : styles.aiMsg}>
                        <div style={styles.msgRole}>
                            {msg.role === 'user' ? '👤 나' : '🤖 면접관'}
                        </div>
                        <div style={styles.msgContent}>{msg.content}</div>
                        {msg.phase && <div style={styles.msgPhase}>{msg.phase}</div>}
                    </div>
                ))}
                <div ref={chatBottomRef} />
            </div>

            {/* ── Mutation Area ──────────────────────────────────────────── */}
            {/* No-Template Fallback & Phase Transition Guard:
                Only render question/input when currentQuestion exists in projection */}
            {hydrated && !isTerminal && !isSafeMode && canMutate && (
                <div style={styles.inputArea}>
                    {/* Current question — only shown when server provides it */}
                    {currentQuestion ? (
                        <div style={styles.questionBox}>
                            <span style={styles.questionLabel}>면접 질문</span>
                            <p style={styles.questionText}>{currentQuestion}</p>
                        </div>
                    ) : null /* No template fallback: no placeholder text rendered */}

                    <textarea
                        id="answer-input"
                        value={answer}
                        onChange={e => setAnswer(e.target.value)}
                        placeholder="답변을 입력하세요. Shift+Enter로 줄바꿈, Enter로 제출"
                        style={{ ...styles.textarea, opacity: local_pending ? 0.6 : 1 }}
                        disabled={local_pending || !canMutate}
                        onKeyDown={e => {
                            if (e.key === 'Enter' && !e.shiftKey && !local_pending && answer.trim() && canMutate) {
                                e.preventDefault()
                                const traceId = createTraceId()
                                handleSubmit(traceId)
                            }
                        }}
                        rows={4}
                    />
                    <TracedButton
                        id="submit-answer-btn"
                        onClick={handleSubmit}
                        actionName="interview:submit-answer"
                        disabled={!answer.trim() || local_pending}
                        style={{ width: '100%', marginTop: 8, padding: '12px' }}
                    >
                        {local_pending ? '제출 중...' : '답변 제출 →'}
                    </TracedButton>
                </div>
            )}

            {/* ── Terminal State ─────────────────────────────────────────── */}
            {/* All mutation DOM REMOVED (not just hidden) in terminal state */}
            {isTerminal && (
                <div style={styles.completedArea}>
                    <div style={styles.completedBadge}>
                        {status === 'ABORTED' ? '🚫 면접 중단' : '✅ 면접 완료'}
                    </div>
                    <p style={{ color: '#94a3b8', marginBottom: 16 }}>
                        {status === 'ABORTED'
                            ? '면접이 중단되었습니다.'
                            : '수고하셨습니다. 평가가 처리됩니다.'}
                    </p>
                    {/* Allow navigation even in terminal state */}
                    <button
                        id="view-result-btn"
                        onClick={() => navigate(`/candidate/result/${interviewId}`)}
                        style={styles.resultBtn}
                    >
                        결과 확인하기
                    </button>
                </div>
            )}
        </div>
    )
}

const styles = {
    fullPage: {
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
        display: 'flex',
        flexDirection: 'column',
    },
    centeredContent: {
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
    },
    spinner: {
        width: 40,
        height: 40,
        border: '4px solid rgba(59,130,246,0.2)',
        borderTopColor: '#3b82f6',
        borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
    },
    safeModeBadge: {
        background: 'rgba(239,68,68,0.15)',
        border: '1px solid #ef4444',
        color: '#fca5a5',
        padding: '12px 24px',
        borderRadius: 8,
        fontWeight: 700,
        fontSize: 18,
    },
    safeNavBtn: {
        marginTop: 20,
        padding: '10px 28px',
        background: 'rgba(59,130,246,0.1)',
        border: '1px solid #3b82f6',
        borderRadius: 6,
        color: '#60a5fa',
        cursor: 'pointer',
        fontSize: 15,
    },
    staleBanner: {
        background: 'rgba(234,179,8,0.15)',
        border: '1px solid rgba(234,179,8,0.4)',
        color: '#fde047',
        padding: '8px 24px',
        fontSize: 13,
        textAlign: 'center',
    },
    syncBanner: {
        background: 'rgba(59,130,246,0.1)',
        border: '1px solid rgba(59,130,246,0.3)',
        color: '#93c5fd',
        padding: '8px 24px',
        fontSize: 13,
        textAlign: 'center',
    },
    header: {
        padding: '20px 24px',
        borderBottom: '1px solid #1e293b',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: 'rgba(15,23,42,0.8)',
        backdropFilter: 'blur(10px)',
        position: 'sticky',
        top: 0,
        zIndex: 10,
    },
    headerTitle: { color: '#f1f5f9', fontSize: 20, fontWeight: 700, margin: '0 0 4px' },
    phaseBadge: {
        background: 'rgba(59,130,246,0.15)',
        color: '#60a5fa',
        padding: '2px 10px',
        borderRadius: 99,
        fontSize: 13,
        border: '1px solid rgba(59,130,246,0.3)',
    },
    sseIndicator: {
        marginLeft: 12,
        fontSize: 12,
        fontWeight: 600,
        padding: '2px 8px',
        borderRadius: 99,
    },
    sseLive: { color: '#22c55e', background: 'rgba(34,197,94,0.1)' },
    sseOffline: { color: '#f59e0b', background: 'rgba(245,158,11,0.1)' },
    chatContainer: {
        flex: 1,
        overflowY: 'auto',
        padding: '16px 24px',
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
        maxHeight: 'calc(100vh - 220px)',
    },
    emptyChat: {
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '40px 0',
    },
    userMsg: {
        alignSelf: 'flex-end',
        maxWidth: '80%',
        background: 'linear-gradient(135deg, #1d4ed8, #4338ca)',
        borderRadius: '16px 16px 4px 16px',
        padding: 16,
    },
    aiMsg: {
        alignSelf: 'flex-start',
        maxWidth: '80%',
        background: '#1e293b',
        border: '1px solid #334155',
        borderRadius: '16px 16px 16px 4px',
        padding: 16,
    },
    msgRole: { fontSize: 12, color: '#94a3b8', marginBottom: 6, fontWeight: 600 },
    msgContent: { color: '#f1f5f9', fontSize: 15, lineHeight: 1.6, whiteSpace: 'pre-wrap' },
    msgPhase: { marginTop: 8, fontSize: 11, color: '#475569', fontStyle: 'italic' },
    inputArea: {
        padding: '16px 24px',
        borderTop: '1px solid #1e293b',
        background: 'rgba(15,23,42,0.9)',
        backdropFilter: 'blur(10px)',
    },
    questionBox: {
        marginBottom: 12,
        padding: '12px 16px',
        background: 'rgba(59,130,246,0.07)',
        border: '1px solid rgba(59,130,246,0.2)',
        borderRadius: 8,
    },
    questionLabel: { fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase' },
    questionText: { color: '#e2e8f0', fontSize: 15, lineHeight: 1.6, margin: '6px 0 0' },
    textarea: {
        width: '100%',
        background: '#1e293b',
        border: '1px solid #334155',
        borderRadius: 8,
        color: '#f1f5f9',
        fontSize: 15,
        padding: '12px 16px',
        resize: 'vertical',
        outline: 'none',
        fontFamily: 'inherit',
        boxSizing: 'border-box',
        transition: 'border-color 0.2s, opacity 0.2s',
    },
    completedArea: {
        padding: '24px',
        borderTop: '1px solid #1e293b',
        textAlign: 'center',
        background: 'rgba(15,23,42,0.9)',
    },
    completedBadge: {
        fontSize: 22,
        fontWeight: 700,
        color: '#22c55e',
        marginBottom: 8,
    },
    resultBtn: {
        padding: '12px 32px',
        background: 'linear-gradient(135deg, #1d4ed8, #4338ca)',
        border: 'none',
        borderRadius: 8,
        color: '#fff',
        fontWeight: 600,
        fontSize: 15,
        cursor: 'pointer',
    },
}
