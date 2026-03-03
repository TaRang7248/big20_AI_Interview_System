/**
 * InterviewResult - Evaluation Result View (Section 39, 63 - FRONT-TASK-01)
 *
 * Contracts:
 * - Section 39/63: Result is read-only. No mutation buttons rendered.
 * - Section 9.4: Status from server only
 * - Section 25: Async evaluation notice; re-entry auto-syncs
 */

import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { interviewsApi } from '../../services/api'
import ErrorBanner from '../../components/ErrorBanner'
import TracedButton from '../../components/TracedButton'
import { createTraceId, ActionTrace } from '../../lib/traceId'

const POLLING_INTERVAL_MS = 5000 // Poll every 5s while IN_PROGRESS

export default function InterviewResult() {
    const { interviewId } = useParams()
    const navigate = useNavigate()
    const [result, setResult] = useState(null)
    const [sessionStatus, setSessionStatus] = useState(null)
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState(null)
    const pollingRef = React.useRef(null)

    async function fetchResult(trace) {
        const traceId = trace || createTraceId()
        try {
            const res = await interviewsApi.getResult(interviewId)
            const data = res.data
            setSessionStatus(data.status)

            if (data.status === 'EVALUATED' && data.evaluation) {
                setResult(data)
                clearInterval(pollingRef.current) // Stop polling once done
            }
        } catch (err) {
            setError(err.error_code ? err : { error_code: 'E_UNKNOWN', trace_id: traceId, message: '결과를 불러오지 못했습니다.' })
        } finally {
            setIsLoading(false)
        }
    }

    // Initial load + polling while result is pending (Section 25.1: async visibility)
    useEffect(() => {
        fetchResult()
        // Start polling if not yet evaluated
        pollingRef.current = setInterval(() => {
            if (sessionStatus !== 'EVALUATED') {
                fetchResult()
            }
        }, POLLING_INTERVAL_MS)

        return () => clearInterval(pollingRef.current)
    }, [interviewId])

    const decision = result?.evaluation?.decision
    const scores = result?.evaluation?.scores
    const summary = result?.evaluation?.summary

    const isCompleted = sessionStatus === 'EVALUATED'

    return (
        <div style={styles.page}>
            <ErrorBanner error={error} onDismiss={() => setError(null)} />

            {isLoading ? (
                <div style={styles.centerBox}>
                    <div style={styles.spinner} />
                    <p style={{ color: '#64748b', marginTop: 16 }}>결과를 불러오는 중...</p>
                </div>
            ) : !isCompleted ? (
                /* Section 25.1: Async guidance while evaluation is processing */
                <div style={styles.pendingCard}>
                    <div style={styles.pendingIcon}>⏳</div>
                    <h2 style={{ color: '#f1f5f9', marginBottom: 8 }}>평가 처리 중</h2>
                    <p style={{ color: '#94a3b8', textAlign: 'center', maxWidth: 400 }}>
                        AI가 면접 내용을 분석하고 있습니다. 이 페이지에서 이동하셔도 평가는 계속 진행됩니다.
                        완료되면 자동으로 표시됩니다.
                    </p>
                    <div style={styles.pulseDot} />
                </div>
            ) : (
                /* Section 39/63: Read-only result view - NO mutation buttons */
                <div style={styles.resultCard}>
                    <div style={{ textAlign: 'center', marginBottom: 32 }}>
                        <div style={{
                            ...styles.decisionBadge,
                            background: decision === 'PASS' ? 'linear-gradient(135deg, #16a34a, #22c55e)' : 'linear-gradient(135deg, #dc2626, #ef4444)',
                        }}>
                            {decision === 'PASS' ? '✅ 합격' : '❌ 불합격'}
                        </div>
                        <p style={{ color: '#94a3b8', marginTop: 12, fontSize: 14 }}>
                            {result?.job_title || '면접 결과'}
                        </p>
                    </div>

                    {/* Summary */}
                    {summary && (
                        <div style={styles.summaryBox}>
                            <h3 style={styles.sectionTitle}>종합 평가</h3>
                            <p style={{ color: '#cbd5e1', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{summary}</p>
                        </div>
                    )}

                    {/* Scores */}
                    {scores && (
                        <div style={styles.scoresGrid}>
                            <ScoreItem label="기술 역량" score={scores.tech} />
                            <ScoreItem label="문제 해결" score={scores.problem} />
                            <ScoreItem label="의사 소통" score={scores.comm} />
                            <ScoreItem label="태도/비언어" score={scores.nonverbal} />
                        </div>
                    )}

                    {/* Navigation only – no re-evaluation or retry buttons (Section 39) */}
                    <div style={{ marginTop: 24, display: 'flex', gap: 12, justifyContent: 'center' }}>
                        <TracedButton
                            id="back-to-home-btn"
                            onClick={async () => navigate('/candidate/home')}
                            actionName="result:back-home"
                            variant="ghost"
                        >
                            홈으로
                        </TracedButton>
                        <TracedButton
                            id="view-postings-btn"
                            onClick={async () => navigate('/candidate/postings')}
                            actionName="result:view-postings"
                        >
                            다른 공고 보기
                        </TracedButton>
                    </div>
                </div>
            )}
        </div>
    )
}

function ScoreItem({ label, score }) {
    const pct = Math.min(100, Math.max(0, score || 0))
    const color = pct >= 70 ? '#22c55e' : pct >= 50 ? '#f59e0b' : '#ef4444'
    return (
        <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ color: '#94a3b8', fontSize: 14 }}>{label}</span>
                <span style={{ color, fontWeight: 700, fontSize: 14 }}>{pct.toFixed(0)}점</span>
            </div>
            <div style={{ background: '#1e293b', borderRadius: 99, height: 8, overflow: 'hidden' }}>
                <div style={{ width: `${pct}%`, background: color, height: '100%', borderRadius: 99, transition: 'width 0.8s ease' }} />
            </div>
        </div>
    )
}

const styles = {
    page: {
        minHeight: '80vh',
        padding: '32px 24px',
        maxWidth: 640,
        margin: '0 auto',
    },
    centerBox: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '60vh',
    },
    spinner: {
        width: 48,
        height: 48,
        border: '4px solid rgba(59,130,246,0.2)',
        borderTopColor: '#3b82f6',
        borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
    },
    pendingCard: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '60vh',
    },
    pendingIcon: {
        fontSize: 64,
        marginBottom: 16,
        animation: 'pulse 2s ease-in-out infinite',
    },
    pulseDot: {
        width: 10,
        height: 10,
        background: '#3b82f6',
        borderRadius: '50%',
        marginTop: 24,
        animation: 'pulse 1.5s ease-in-out infinite',
    },
    resultCard: {
        background: '#1e293b',
        borderRadius: 16,
        padding: 32,
        border: '1px solid #334155',
    },
    decisionBadge: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        padding: '12px 32px',
        borderRadius: 12,
        fontSize: 22,
        fontWeight: 800,
        color: '#fff',
    },
    summaryBox: {
        background: '#0f172a',
        borderRadius: 10,
        padding: '16px 20px',
        marginBottom: 24,
        border: '1px solid #1e293b',
    },
    sectionTitle: {
        color: '#94a3b8',
        fontSize: 13,
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.1em',
        marginBottom: 12,
        marginTop: 0,
    },
    scoresGrid: {
        marginTop: 8,
    },
}
