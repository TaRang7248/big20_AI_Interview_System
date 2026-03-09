import React, { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { jobsApi } from '../../services/api'

function StatusBadge({ status }) {
    const map = {
        PUBLISHED: { label: '모집중', cls: 'badge-published' },
        DRAFT: { label: '초안', cls: 'badge-draft' },
        CLOSED: { label: '마감', cls: 'badge-closed' },
    }
    const { label, cls } = map[status] || { label: status, cls: '' }
    return <span className={`badge ${cls}`}>{label}</span>
}

export default function AdminPostings() {
    const [jobs, setJobs] = useState([])
    const [loading, setLoading] = useState(true)
    const navigate = useNavigate()

    useEffect(() => {
        jobsApi.list()
            .then(res => setJobs(res.data))
            .catch(console.error)
            .finally(() => setLoading(false))
    }, [])

    if (loading) return <div className="loading"><div className="spinner" />공고 불러오는 중...</div>

    return (
        <div>
            <div className="page-header flex justify-between items-center">
                <div>
                    <h1 className="page-title">공고 관리</h1>
                    <p className="page-subtitle">전체 채용 공고를 관리합니다.</p>
                </div>
                <Link to="/admin/postings/new" className="btn btn-primary">➕ 공고 등록</Link>
            </div>

            {/* Stats summary */}
            <div className="card-grid" style={{ marginBottom: 24 }}>
                {[
                    { label: '전체', value: jobs.length, icon: '📋', color: 'var(--accent-1)' },
                    { label: '모집중', value: jobs.filter(j => j.status === 'PUBLISHED').length, icon: '🟢', color: 'var(--success)' },
                    { label: '초안', value: jobs.filter(j => j.status === 'DRAFT').length, icon: '📝', color: 'var(--warning)' },
                    { label: '마감', value: jobs.filter(j => j.status === 'CLOSED').length, icon: '🔒', color: 'var(--text-muted)' },
                ].map(s => (
                    <div className="stat-card" key={s.label}>
                        <div className="stat-icon" style={{ background: 'var(--glass)', color: s.color, fontSize: 20 }}>{s.icon}</div>
                        <div>
                            <div className="stat-value">{s.value}</div>
                            <div className="stat-label">{s.label}</div>
                        </div>
                    </div>
                ))}
            </div>

            {jobs.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-icon">📋</div>
                    <p>등록된 공고가 없습니다.</p>
                </div>
            ) : (
                <div className="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>공고명</th>
                                <th>상태</th>
                                <th>지원자</th>
                                <th>합격</th>
                                <th>불합격</th>
                                <th>마감일</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            {jobs.map(job => (
                                <tr key={job.job_id} onClick={() => navigate(`/admin/postings/${job.job_id}`)}>
                                    <td style={{ fontWeight: 600 }}>{job.title}</td>
                                    <td><StatusBadge status={job.status} /></td>
                                    <td>{job.stats?.total_applicants ?? '-'}</td>
                                    <td style={{ color: 'var(--success)' }}>{job.stats?.pass_count ?? '-'}</td>
                                    <td style={{ color: 'var(--danger)' }}>{job.stats?.fail_count ?? '-'}</td>
                                    <td style={{ color: 'var(--text-muted)' }}>{job.deadline || '-'}</td>
                                    <td onClick={e => e.stopPropagation()}>
                                        <div className="flex gap-2">
                                            <Link
                                                to={`/admin/postings/${job.job_id}/edit`}
                                                className="btn btn-secondary"
                                                style={{ padding: '6px 12px', fontSize: 12 }}
                                            >
                                                수정
                                            </Link>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    )
}
