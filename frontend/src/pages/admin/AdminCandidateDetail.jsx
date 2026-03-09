/**
 * AdminCandidateDetail — Slice D: Admin Result View (TASK-FRONT-001)
 *
 * Contracts enforced:
 * - Authority Pull 2-Step on every mount; candidate store is NOT reused
 * - Admin Authority Boundary: evaluation_input_hash and audit_link shown ONLY here
 * - Role change: store reset + authority pull (enforced by PrivateRoute adminOnly in App.jsx)
 * - No optimistic update; no auto-retry; no candidate projection sharing
 * - Error format: RAW error_code + trace_id
 * - Observability: Copy for Support in all error states
 * - AdminAuditTimeline: rendered only in admin view
 * - AdminDecisionOverride: rendered only if admin has override capability (server-provided field)
 */

import React, { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import AdminAuditTimeline from './AdminAuditTimeline'
import AdminDecisionOverride from './AdminDecisionOverride'
import AdminResumeDownloadButton from '../../components/AdminResumeDownloadButton'
import { createTraceId, ActionTrace } from '../../lib/traceId'
import {
    Chart as ChartJS, RadialLinearScale, PointElement,
    LineElement, Filler, Tooltip, Legend,
} from 'chart.js'
import { Radar } from 'react-chartjs-2'

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend)

function getTokenHeader() {
    return { Authorization: `Bearer ${localStorage.getItem('imh_token')}` }
}

function buildSupportPayload({ sessionId, traceId, snapshotHash }) {
    return [
        `session_id: ${sessionId || 'N/A'}`,
        `trace_id: ${traceId || 'N/A'}`,
        `snapshot_hash: ${snapshotHash || 'N/A'}`,
    ].join('\n')
}

export default function AdminCandidateDetail() {
    const { postingId, userId } = useParams()
    const navigate = useNavigate()
    const [data, setData] = useState(null)           // Admin-only projection (isolated from candidate store)
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState(null)
    const [copyHashDone, setCopyHashDone] = useState(false)
    const [copySupportDone, setCopySupportDone] = useState(false)
    const [activeTab, setActiveTab] = useState('result') // 'result' | 'audit'
    const traceIdRef = useRef(null)
    const snapshotHashRef = useRef(null)

    // ── Authority Pull: Step 1 — fetch candidate detail (admin API)
    // NOTE: this is a separate admin-only API; never reuses candidate store or projection
    const performPull = useCallback(async () => {
        const traceId = createTraceId()
        traceIdRef.current = traceId
        ActionTrace.trigger(traceId, 'admin:candidate-detail:pull')
        setIsLoading(true)
        setError(null)

        try {
            // Admin endpoint — completely separate from candidate /sessions endpoint
            const res = await fetch(`/api/v1/jobs/${postingId}/candidates/${userId}`, {
                headers: { ...getTokenHeader() },
            })

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}))
                // 403: role boundary — redirect to admin home
                if (res.status === 403) {
                    navigate('/admin/postings')
                    return
                }
                throw {
                    error_code: errData.error_code || 'E_ADMIN_PULL_FAILED',
                    trace_id: errData.trace_id || traceId,
                    status: res.status,
                    message: errData.detail || '지원자 정보를 불러오지 못했습니다.',
                }
            }

            const payload = await res.json()
            snapshotHashRef.current = payload.snapshot_hash ?? null
            setData(payload)
            ActionTrace.stateApplied(traceId, 'admin:candidate-detail:success')
        } catch (err) {
            setError(err.error_code ? err : {
                error_code: 'E_ADMIN_PULL_FAILED',
                trace_id: traceId,
                message: '지원자 정보를 불러오지 못했습니다.',
            })
        } finally {
            setIsLoading(false)
        }
    }, [postingId, userId, navigate])

    useEffect(() => {
        performPull()
        return () => {
            // No candidate store to reset — admin view is independent
            setData(null)
        }
    }, [postingId, userId])  // eslint-disable-line react-hooks/exhaustive-deps

    const copyHash = () => {
        navigator.clipboard?.writeText(data?.evaluation?.evaluation_input_hash ?? '').then(() => {
            setCopyHashDone(true)
            setTimeout(() => setCopyHashDone(false), 1500)
        })
    }

    const copySupport = () => {
        navigator.clipboard?.writeText(buildSupportPayload({
            sessionId: data?.session_id || userId,
            traceId: traceIdRef.current,
            snapshotHash: snapshotHashRef.current,
        })).then(() => {
            setCopySupportDone(true)
            setTimeout(() => setCopySupportDone(false), 1500)
        })
    }

    if (isLoading) {
        return (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '40vh' }}>
                <div style={s.spinner} />
                <p style={{ color: '#64748b', marginTop: 12 }}>지원자 정보 로딩 중...</p>
            </div>
        )
    }

    if (error) {
        return (
            <div style={s.errorPage}>
                <p style={{ fontFamily: 'monospace', color: '#f87171', fontSize: 14 }}>
                    {error.error_code} · {error.trace_id || 'N/A'}
                </p>
                {error.message && <p style={{ color: '#94a3b8', fontSize: 13 }}>{error.message}</p>}
                <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                    <button onClick={performPull} style={s.smallBtn}>재시도</button>
                    <button onClick={copySupport} style={s.smallBtnGhost}>
                        {copySupportDone ? '✓ 복사됨' : 'Copy for Support'}
                    </button>
                </div>
            </div>
        )
    }

    if (!data) return null

    const user = data.user || {}
    const evalData = data.evaluation   // Admin-only full evaluation data
    const isPass = evalData?.decision === 'PASS'
    const sessionId = data.session_id ?? data.interview_id ?? null
    // can_override: server-provided admin capability flag (snapshot-frozen)
    const canOverride = data.can_override === true

    const radarData = evalData ? {
        labels: ['기술 역량', '문제 해결', '의사소통', '비언어적'],
        datasets: [{
            label: '점수',
            data: [evalData.tech_score, evalData.problem_score, evalData.comm_score, evalData.nonverbal_score],
            backgroundColor: 'rgba(99,102,241,0.2)',
            borderColor: '#6366F1',
            borderWidth: 2,
            pointBackgroundColor: '#6366F1',
        }],
    } : null

    const radarOptions = {
        plugins: { legend: { display: false } },
        scales: {
            r: {
                min: 0, max: 100,
                ticks: { color: '#6B7280', font: { size: 10 } },
                grid: { color: 'rgba(255,255,255,0.06)' },
                pointLabels: { color: '#9CA3AF', font: { size: 11 } },
                angleLines: { color: 'rgba(255,255,255,0.06)' },
            },
        },
    }

    return (
        <div>
            {/* Breadcrumb */}
            <div style={s.breadcrumb}>
                <Link to="/admin/postings" style={s.breadLink}>공고 관리</Link>
                {' / '}
                <Link to={`/admin/postings/${postingId}`} style={s.breadLink}>공고 상세</Link>
                {' / '}
                <span style={{ color: '#f1f5f9' }}>{user.name}</span>
            </div>
            <div style={s.pageHeader}>
                <h1 style={s.pageTitle}>{user.name} 지원자 상세</h1>
                <button onClick={copySupport} style={s.smallBtnGhost}>
                    {copySupportDone ? '✓ 복사됨' : 'Copy for Support'}
                </button>
            </div>

            {/* Tabs: Result | Audit */}
            <div style={s.tabRow}>
                <button
                    id="tab-result"
                    onClick={() => setActiveTab('result')}
                    style={{ ...s.tab, ...(activeTab === 'result' ? s.tabActive : {}) }}
                >
                    결과 상세
                </button>
                {sessionId && (
                    <button
                        id="tab-audit"
                        onClick={() => setActiveTab('audit')}
                        style={{ ...s.tab, ...(activeTab === 'audit' ? s.tabActive : {}) }}
                    >
                        Audit Timeline
                    </button>
                )}
            </div>

            {/* ── Result Tab ──────────────────────────────────────── */}
            {activeTab === 'result' && (
                <div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 24 }}>
                        {/* User bio */}
                        <div className="card">
                            <div style={s.cardLabel}>지원자 정보</div>
                            {[
                                ['이름', user.name],
                                ['생년월일', user.birth_date],
                                ['성별', user.gender === 'M' ? '남성' : user.gender === 'F' ? '여성' : user.gender],
                                ['이메일', user.email],
                                ['전화', user.phone],
                                ['주소', user.address],
                            ].map(([k, v]) => v ? (
                                <div key={k} style={s.infoRow}>
                                    <span style={s.infoKey}>{k}</span>
                                    <span style={s.infoVal}>{v}</span>
                                </div>
                            ) : null)}
                        </div>

                        {/* Resume + decision */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                            {data.resume && (
                                <div className="card">
                                    <div style={s.cardLabel}>이력서</div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                        <span style={{ fontSize: 28 }}>📎</span>
                                        <div style={{ flex: 1 }}>
                                            <div style={{ fontWeight: 600, fontSize: 14 }}>{data.resume.file_name}</div>
                                            <div style={{ fontSize: 12, color: '#64748b' }}>
                                                {new Date(data.resume.uploaded_at).toLocaleDateString('ko-KR')} 업로드
                                            </div>
                                        </div>
                                        <AdminResumeDownloadButton candidateUserId={userId} />
                                    </div>
                                </div>
                            )}

                            {evalData && (
                                <div style={{
                                    padding: 24, borderRadius: 12,
                                    background: isPass ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)',
                                    border: `1px solid ${isPass ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)'}`,
                                }}>
                                    <div style={{ fontSize: 40, textAlign: 'center' }}>{isPass ? '🎉' : '😔'}</div>
                                    <div style={{ fontSize: 22, fontWeight: 700, textAlign: 'center', color: isPass ? '#22c55e' : '#ef4444', marginTop: 8 }}>
                                        {isPass ? '합격' : '불합격'}
                                    </div>
                                    {evalData.summary && (
                                        <p style={{ color: '#94a3b8', fontSize: 13, marginTop: 8, textAlign: 'center' }}>{evalData.summary}</p>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Scores + Radar */}
                    {evalData && (
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 24, marginBottom: 24 }}>
                            <div className="score-grid">
                                {[
                                    ['기술 역량', evalData.tech_score],
                                    ['문제 해결', evalData.problem_score],
                                    ['의사소통', evalData.comm_score],
                                    ['비언어적', evalData.nonverbal_score],
                                ].map(([label, val]) => (
                                    <div className="score-item" key={label}>
                                        <div className="score-value">{val?.toFixed(1) ?? '-'}</div>
                                        <div className="score-name">{label}</div>
                                    </div>
                                ))}
                            </div>
                            <div className="chart-container">
                                <div className="chart-title">역량 레이더</div>
                                {radarData && <Radar data={radarData} options={radarOptions} />}
                            </div>
                        </div>
                    )}

                    {/* ── Admin-Only fields (evaluation_input_hash + audit link) ── */}
                    {/* Admin Authority Boundary: this block MUST NOT appear in candidate view */}
                    {evalData?.evaluation_input_hash && (
                        <div style={s.adminHashBox}>
                            <div style={s.cardLabel}>
                                🔐 Admin-Only: Evaluation Input Hash
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                <code style={s.hashCode}>{evalData.evaluation_input_hash}</code>
                                <button
                                    id="copy-eval-hash-btn"
                                    onClick={copyHash}
                                    style={s.smallBtn}
                                >
                                    {copyHashDone ? '✓ 복사됨' : '복사'}
                                </button>
                                {sessionId && (
                                    <button
                                        onClick={() => setActiveTab('audit')}
                                        style={s.smallBtnGhost}
                                    >
                                        Audit 바로가기 ↓
                                    </button>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Decision Override — Admin-only, capability gated */}
                    {sessionId && canOverride && evalData && (
                        <div style={s.overrideSection}>
                            <div style={s.cardLabel}>결정 Override (Admin 전용)</div>
                            <AdminDecisionOverride
                                sessionId={sessionId}
                                currentDecision={evalData.decision}
                                onSuccess={performPull}  // Re-pull on success (no optimistic update)
                            />
                        </div>
                    )}

                    {/* Chat history */}
                    {data.chat_history?.length > 0 && (
                        <div className="card" style={{ marginTop: 24 }}>
                            <div style={s.cardLabel}>면접 대화 기록</div>
                            <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                                <div className="chat-container" style={{ padding: 0 }}>
                                    {data.chat_history.map((msg, idx) => (
                                        <div
                                            key={idx}
                                            style={{ display: 'flex', flexDirection: 'column', alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start' }}
                                        >
                                            <div className="chat-label">
                                                {msg.role === 'ai' ? '🤖 AI 면접관' : '🙋 지원자'}
                                                {msg.phase && <span style={{ marginLeft: 6, fontSize: 9, color: '#6366f1' }}>[{msg.phase}]</span>}
                                            </div>
                                            <div className={`chat-bubble ${msg.role}`}>{msg.content}</div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* ── Audit Tab ────────────────────────────────────────── */}
            {activeTab === 'audit' && sessionId && (
                <div style={{ marginTop: 16 }}>
                    <AdminAuditTimeline sessionId={sessionId} />
                </div>
            )}
        </div>
    )
}

const s = {
    spinner: {
        width: 36, height: 36,
        border: '3px solid rgba(99,102,241,0.2)', borderTopColor: '#6366f1',
        borderRadius: '50%', animation: 'spin 0.8s linear infinite',
    },
    errorPage: { padding: '32px 0', textAlign: 'center' },
    breadcrumb: { fontSize: 12, color: '#64748b', marginBottom: 4 },
    breadLink: { color: '#64748b', textDecoration: 'none' },
    pageHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 },
    pageTitle: { fontSize: 22, fontWeight: 700, color: '#f1f5f9', margin: 0 },
    tabRow: { display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid #1e293b' },
    tab: {
        padding: '8px 20px', background: 'transparent', border: 'none',
        borderBottom: '2px solid transparent', color: '#64748b',
        cursor: 'pointer', fontSize: 14, fontWeight: 600, marginBottom: -1,
    },
    tabActive: { borderBottomColor: '#6366f1', color: '#a5b4fc' },
    cardLabel: { fontSize: 12, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 },
    infoRow: { display: 'flex', marginBottom: 8, fontSize: 13 },
    infoKey: { color: '#64748b', minWidth: 70 },
    infoVal: { color: '#f1f5f9', wordBreak: 'break-all' },
    adminHashBox: {
        background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.25)',
        borderRadius: 10, padding: '12px 16px', marginBottom: 16,
    },
    hashCode: { fontSize: 12, color: '#a5b4fc', fontFamily: 'monospace', wordBreak: 'break-all', flex: 1 },
    overrideSection: {
        background: 'rgba(245,158,11,0.05)', border: '1px solid rgba(245,158,11,0.2)',
        borderRadius: 10, padding: '12px 16px', marginBottom: 16,
    },
    smallBtn: {
        padding: '5px 12px', background: 'rgba(99,102,241,0.15)',
        border: '1px solid rgba(99,102,241,0.3)', borderRadius: 6,
        color: '#a5b4fc', cursor: 'pointer', fontSize: 12, whiteSpace: 'nowrap',
    },
    smallBtnGhost: {
        padding: '5px 12px', background: 'transparent',
        border: '1px solid #334155', borderRadius: 6,
        color: '#64748b', cursor: 'pointer', fontSize: 12, whiteSpace: 'nowrap',
    },
}
