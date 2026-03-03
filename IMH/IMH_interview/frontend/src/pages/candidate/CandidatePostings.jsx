/**
 * CandidatePostings - Job listings with traced interview creation (Sections 23, 42 - FRONT-TASK-01)
 *
 * Upgraded from basic alert-based error to ErrorBanner + TracedButton.
 * Interview creation uses trace_id lifecycle.
 * DeviceCheck route maintained for existing compatibility.
 */

import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { jobsApi, interviewsApi } from '../../services/api'
import ErrorBanner from '../../components/ErrorBanner'
import TracedButton from '../../components/TracedButton'

function StatusBadge({ status }) {
    const map = {
        PUBLISHED: { label: '모집중', color: '#22c55e', bg: 'rgba(34,197,94,0.12)' },
        DRAFT: { label: '준비중', color: '#94a3b8', bg: 'rgba(148,163,184,0.12)' },
        CLOSED: { label: '마감', color: '#ef4444', bg: 'rgba(239,68,68,0.12)' },
    }
    const { label, color, bg } = map[status] || { label: status, color: '#94a3b8', bg: 'rgba(0,0,0,0.1)' }
    return (
        <span style={{ fontSize: 11, fontWeight: 700, padding: '4px 10px', borderRadius: 99, background: bg, color }}>
            {label}
        </span>
    )
}

export default function CandidatePostings() {
    const [jobs, setJobs] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const navigate = useNavigate()

    useEffect(() => {
        jobsApi.list()
            .then(res => setJobs(res.data))
            .catch(err => setError(err.error_code ? err : { error_code: 'E_UNKNOWN', message: '공고를 불러오지 못했습니다.' }))
            .finally(() => setLoading(false))
    }, [])

    // Section 23.1: Traced button lifecycle for interview creation
    async function handleApply(job, traceId) {
        if (job.status !== 'PUBLISHED') return
        try {
            const res = await interviewsApi.create(job.job_id)
            const { session_id } = res.data
            // Navigate to interview directly (device-check removed for MVP TEXT mode)
            navigate(`/candidate/interview/${session_id}`)
        } catch (err) {
            setError(err.error_code ? err : { error_code: 'E_UNKNOWN', trace_id: traceId, message: '면접 신청 중 오류가 발생했습니다.' })
        }
    }

    if (loading) {
        return (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}>
                <div style={{ width: 40, height: 40, border: '3px solid rgba(59,130,246,0.2)', borderTopColor: '#3b82f6', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
            </div>
        )
    }

    return (
        <div>
            <div className="page-header">
                <h1 className="page-title">채용 공고</h1>
                <p className="page-subtitle">현재 모집 중인 채용 공고를 확인하고 면접을 신청하세요.</p>
            </div>

            <ErrorBanner error={error} onDismiss={() => setError(null)} />

            {jobs.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-icon">📋</div>
                    <p>현재 등록된 공고가 없습니다.</p>
                </div>
            ) : (
                <div className="card-grid">
                    {jobs.map(job => (
                        <div key={job.job_id} className="card" style={{ cursor: 'default' }}>
                            <div className="flex justify-between items-center mb-4">
                                <StatusBadge status={job.status} />
                                {job.deadline && (
                                    <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>~{job.deadline}</span>
                                )}
                            </div>

                            <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>{job.title}</h3>
                            {job.company && <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 4 }}>🏢 {job.company}</div>}
                            {job.location && <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 4 }}>📍 {job.location}</div>}
                            {job.headcount && <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12 }}>👥 {job.headcount}명 채용</div>}

                            {job.description && (
                                <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16, display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                                    {job.description}
                                </p>
                            )}

                            {job.tags && job.tags.length > 0 && (
                                <div className="flex gap-2" style={{ flexWrap: 'wrap', marginBottom: 16 }}>
                                    {job.tags.map(tag => (
                                        <span key={tag} style={{ fontSize: 11, padding: '3px 8px', background: 'var(--glass)', border: '1px solid var(--glass-border)', borderRadius: 100, color: 'var(--text-muted)' }}>
                                            {tag}
                                        </span>
                                    ))}
                                </div>
                            )}

                            {/* TracedButton with rapid-click guard per Section 42 */}
                            <TracedButton
                                id={`apply-btn-${job.job_id}`}
                                onClick={(traceId) => handleApply(job, traceId)}
                                actionName={`jobs:apply:${job.job_id}`}
                                disabled={job.status !== 'PUBLISHED'}
                                style={{ width: '100%', justifyContent: 'center', padding: '11px' }}
                            >
                                {job.status === 'PUBLISHED' ? '면접 신청하기' :
                                    job.status === 'CLOSED' ? '마감된 공고' : '모집 전'}
                            </TracedButton>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
