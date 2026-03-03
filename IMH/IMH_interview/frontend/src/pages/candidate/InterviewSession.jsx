/**
 * InterviewSession - Core TEXT Interview Page (PHASE 1 Vertical Slice)
 *
 * Contracts enforced:
 * - Section 9.4: No local business state derivation
 * - Section 14: Server-authoritative progression
 * - Section 17: Status enum from server
 * - Section 23.1: Traced button lifecycle
 * - Section 27: Authority Pull on re-entry
 * - Section 37: All state updates from server
 * - Section 42: Rapid click guard via TracedButton
 */

import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { interviewsApi } from '../../services/api'
import { useSessionStore } from '../../stores/sessionStore'
import ErrorBanner from '../../components/ErrorBanner'
import TracedButton from '../../components/TracedButton'
import { createTraceId, ActionTrace } from '../../lib/traceId'
import { useSSEProjection } from '../../hooks/useSSEProjection'

export default function InterviewSession() {
    const { interviewId } = useParams()
    const navigate = useNavigate()
    const [answer, setAnswer] = useState('')
    const [chatHistory, setChatHistory] = useState([])
    const [sessionData, setSessionData] = useState(null)
    const [isDone, setIsDone] = useState(false)
    const chatBottomRef = useRef(null)

    const {
        setLoading, setError, error, isLoading, isPendingMutation, setFromProjection,
        setPendingMutation, reset
    } = useSessionStore()

    // ─── Section 27: Authority Pull on initial load / re-entry ────────────────
    useEffect(() => {
        let cancelled = false

        async function authorityPull() {
            const traceId = createTraceId()
            ActionTrace.trigger(traceId, 'interview:authority-pull')
            setLoading(true)

            try {
                // Get session state (authority)
                const [sessionRes, chatRes] = await Promise.all([
                    interviewsApi.get(interviewId),
                    interviewsApi.getChat(interviewId),
                ])
                if (cancelled) return

                const session = sessionRes.data
                const chat = chatRes.data

                // Section 9.4: Status comes from server
                if (session.status === 'EVALUATED' || session.status === 'COMPLETED') {
                    setIsDone(true)
                }

                setSessionData(session)
                setChatHistory(chat)

                // Section 27: Full overwrite of projection store
                setFromProjection({
                    sessionId: interviewId,
                    jobId: session.job_id,
                    jobTitle: session.job_title,
                    status: session.status,
                    currentPhase: session.current_phase,
                    phaseIndex: session.phase_index,
                    totalPhases: session.total_phases,
                    turnCount: session.turn_count,
                    messages: chat,
                })

                ActionTrace.stateApplied(traceId, 'SessionStore')
            } catch (err) {
                if (!cancelled) {
                    setError(err.error_code ? err : { error_code: 'E_UNKNOWN', trace_id: traceId, message: '세션 정보를 불러오지 못했습니다.' })
                }
            }
        }

        authorityPull()
        return () => { cancelled = true; reset() }
    }, [interviewId])

    // Auto-scroll chat
    useEffect(() => {
        chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [chatHistory])

    // ─── Submit Answer (Section 23.1: Traced button lifecycle) ────────────────
    const handleSubmit = useCallback(async (traceId) => {
        if (!answer.trim() || isPendingMutation) return

        const userMsg = { role: 'user', content: answer.trim(), phase: sessionData?.currentPhase, created_at: new Date().toISOString() }
        // Append local display (not business state, only for visual continuity)
        setChatHistory(prev => [...prev, userMsg])
        setAnswer('')
        setPendingMutation(true)

        try {
            ActionTrace.apiStart(traceId, 'POST', `/interviews/${interviewId}/chat`)
            const res = await interviewsApi.sendChat(interviewId, answer.trim())
            ActionTrace.apiResponse(traceId, res.status)

            const data = res.data
            const aiMsg = { role: 'ai', content: data.ai_message, phase: data.current_phase, created_at: new Date().toISOString() }
            setChatHistory(prev => [...prev, aiMsg])

            // Section 9.4 / Section 17: Status enum from server
            if (data.is_done || data.status === 'COMPLETED') {
                setIsDone(true)
                setSessionData(prev => ({ ...prev, status: 'COMPLETED' }))
            } else {
                setSessionData(prev => ({ ...prev, currentPhase: data.current_phase, turnCount: data.turn || prev?.turnCount }))
            }

            ActionTrace.stateApplied(traceId, 'SessionStore')
        } catch (err) {
            setError(err.error_code ? err : { error_code: 'E_UNKNOWN', trace_id: traceId, message: '답변 제출에 실패했습니다.' })
        } finally {
            setPendingMutation(false)
        }
    }, [answer, interviewId, isPendingMutation, sessionData])

    const handleViewResult = useCallback(async (traceId) => {
        ActionTrace.trigger(traceId, 'interview:view-result')
        navigate(`/candidate/result/${interviewId}`)
    }, [interviewId, navigate])

    if (isLoading && !sessionData) {
        return (
            <div style={styles.fullPage}>
                <div style={styles.loadingCard}>
                    <div style={styles.spinner} />
                    <p style={{ color: '#94a3b8', marginTop: 16 }}>면접 세션을 불러오는 중...</p>
                </div>
            </div>
        )
    }

    return (
        <div style={styles.fullPage}>
            {/* Header */}
            <div style={styles.header}>
                <div>
                    <h1 style={styles.headerTitle}>
                        {sessionData?.job_title || '면접 진행 중'}
                    </h1>
                    <span style={styles.phaseBadge}>
                        {sessionData?.currentPhase || '준비 중'}
                    </span>
                </div>
                <div style={styles.phaseProgress}>
                    {sessionData && (
                        <span style={{ color: '#64748b', fontSize: 14 }}>
                            {sessionData.phaseIndex + 1} / {sessionData.totalPhases} 단계
                        </span>
                    )}
                </div>
            </div>

            {/* Error Banner */}
            <ErrorBanner error={error} onDismiss={() => setError(null)} />

            {/* Chat History */}
            <div style={styles.chatContainer}>
                {chatHistory.length === 0 && !isLoading && (
                    <div style={styles.emptyChat}>
                        <p style={{ color: '#475569' }}>면접이 시작되면 질문이 표시됩니다.</p>
                    </div>
                )}
                {chatHistory.map((msg, i) => (
                    <div key={i} style={msg.role === 'user' ? styles.userMsg : styles.aiMsg}>
                        <div style={styles.msgRole}>
                            {msg.role === 'user' ? '👤 나' : '🤖 면접관'}
                        </div>
                        <div style={styles.msgContent}>{msg.content}</div>
                        {msg.phase && (
                            <div style={styles.msgPhase}>{msg.phase}</div>
                        )}
                    </div>
                ))}
                <div ref={chatBottomRef} />
            </div>

            {/* Answer Input Area */}
            {!isDone ? (
                <div style={styles.inputArea}>
                    <textarea
                        id="answer-input"
                        value={answer}
                        onChange={e => setAnswer(e.target.value)}
                        placeholder="답변을 입력하세요. Enter+Shift로 줄바꿈, Enter로 제출..."
                        style={styles.textarea}
                        disabled={isPendingMutation}
                        onKeyDown={e => {
                            if (e.key === 'Enter' && !e.shiftKey && !isPendingMutation && answer.trim()) {
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
                        disabled={!answer.trim()}
                        style={{ width: '100%', marginTop: 8, padding: '12px' }}
                    >
                        답변 제출 →
                    </TracedButton>
                </div>
            ) : (
                <div style={styles.completedArea}>
                    <div style={styles.completedBadge}>✅ 면접 완료</div>
                    <p style={{ color: '#94a3b8', marginBottom: 16 }}>
                        수고하셨습니다. 평가가 백그라운드에서 진행됩니다.
                    </p>
                    <TracedButton
                        id="view-result-btn"
                        onClick={handleViewResult}
                        actionName="interview:navigate-result"
                        style={{ padding: '12px 32px' }}
                    >
                        결과 확인하기
                    </TracedButton>
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
        padding: 0,
    },
    loadingCard: {
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
    },
    spinner: {
        width: 48,
        height: 48,
        border: '4px solid rgba(59,130,246,0.2)',
        borderTopColor: '#3b82f6',
        borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
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
    headerTitle: {
        color: '#f1f5f9',
        fontSize: 20,
        fontWeight: 700,
        margin: '0 0 4px',
    },
    phaseBadge: {
        background: 'rgba(59,130,246,0.15)',
        color: '#60a5fa',
        padding: '2px 10px',
        borderRadius: 99,
        fontSize: 13,
        border: '1px solid rgba(59,130,246,0.3)',
    },
    phaseProgress: {
        textAlign: 'right',
    },
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
    msgRole: {
        fontSize: 12,
        color: '#94a3b8',
        marginBottom: 6,
        fontWeight: 600,
    },
    msgContent: {
        color: '#f1f5f9',
        fontSize: 15,
        lineHeight: 1.6,
        whiteSpace: 'pre-wrap',
    },
    msgPhase: {
        marginTop: 8,
        fontSize: 11,
        color: '#475569',
        fontStyle: 'italic',
    },
    inputArea: {
        padding: '16px 24px',
        borderTop: '1px solid #1e293b',
        background: 'rgba(15,23,42,0.9)',
        backdropFilter: 'blur(10px)',
    },
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
        transition: 'border-color 0.2s',
    },
    completedArea: {
        padding: '24px',
        borderTop: '1px solid #1e293b',
        textAlign: 'center',
        background: 'rgba(15,23,42,0.9)',
    },
    completedBadge: {
        fontSize: 24,
        fontWeight: 700,
        color: '#22c55e',
        marginBottom: 8,
    },
}
