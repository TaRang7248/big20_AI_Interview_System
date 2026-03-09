import React, { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { jobsApi } from '../../services/api'
import {
    Chart as ChartJS, ArcElement, Tooltip, Legend,
} from 'chart.js'
import { Doughnut } from 'react-chartjs-2'

ChartJS.register(ArcElement, Tooltip, Legend)

export default function AdminPostingDetail() {
    const { postingId } = useParams()
    const navigate = useNavigate()
    const [job, setJob] = useState(null)
    const [candidates, setCandidates] = useState([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        Promise.all([
            jobsApi.get(postingId),
            jobsApi.listCandidates(postingId),
        ])
            .then(([jobRes, candidatesRes]) => {
                setJob(jobRes.data)
                setCandidates(candidatesRes.data)
            })
            .catch(console.error)
            .finally(() => setLoading(false))
    }, [postingId])

    if (loading) return <div className="loading"><div className="spinner" /></div>
    if (!job) return <div className="empty-state"><p>공고를 찾을 수 없습니다.</p></div>

    const pass = job.stats?.pass_count || 0
    const fail = job.stats?.fail_count || 0
    const total = job.stats?.total_applicants || 0

    const pieData = {
        labels: ['합격', '불합격', '평가 전'],
        datasets: [{
            data: [pass, fail, Math.max(0, total - pass - fail)],
            backgroundColor: ['rgba(16,185,129,0.8)', 'rgba(239,68,68,0.8)', 'rgba(107,114,128,0.4)'],
            borderWidth: 0,
        }]
    }

    const pieOptions = {
        plugins: {
            legend: { position: 'bottom', labels: { color: '#9CA3AF', font: { size: 12 }, padding: 16 } },
        },
        cutout: '65%',
    }

    return (
        <div>
            <div className="page-header flex justify-between items-center">
                <div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
                        <Link to="/admin/postings" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>공고 관리</Link>
                        {' / '}
                        <span style={{ color: 'var(--text-primary)' }}>{job.title}</span>
                    </div>
                    <h1 className="page-title">{job.title}</h1>
                    <p className="page-subtitle">{job.company || ''} {job.location ? `• ${job.location}` : ''}</p>
                </div>
                <Link to={`/admin/postings/${postingId}/edit`} className="btn btn-secondary">✏️ 수정</Link>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 24, marginBottom: 24 }}>
                {/* Stats row */}
                <div className="card-grid" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
                    <div className="stat-card">
                        <div className="stat-icon" style={{ background: 'rgba(99,102,241,0.15)', color: 'var(--accent-1)' }}>👥</div>
                        <div><div className="stat-value">{total}</div><div className="stat-label">지원자</div></div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-icon" style={{ background: 'rgba(16,185,129,0.15)', color: 'var(--success)' }}>✅</div>
                        <div><div className="stat-value">{pass}</div><div className="stat-label">합격</div></div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-icon" style={{ background: 'rgba(239,68,68,0.15)', color: 'var(--danger)' }}>❌</div>
                        <div><div className="stat-value">{fail}</div><div className="stat-label">불합격</div></div>
                    </div>
                </div>

                {/* Pie chart */}
                <div className="chart-container" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    <div className="chart-title">합격률</div>
                    {total > 0 ? (
                        <Doughnut data={pieData} options={pieOptions} />
                    ) : (
                        <div style={{ color: 'var(--text-muted)', fontSize: 13, textAlign: 'center', paddingTop: 40 }}>
                            아직 지원자가 없습니다
                        </div>
                    )}
                </div>
            </div>

            {/* Candidates table */}
            <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>지원자 목록</h2>
            {candidates.length === 0 ? (
                <div className="empty-state"><p>아직 지원자가 없습니다.</p></div>
            ) : (
                <div className="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>이름</th>
                                <th>면접 상태</th>
                                <th>결과</th>
                                <th>기술</th>
                                <th>문제해결</th>
                                <th>의사소통</th>
                                <th>비언어적</th>
                                <th>지원일</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            {candidates.map(c => (
                                <tr key={c.session_id} onClick={() => navigate(`/admin/postings/${postingId}/candidates/${c.user_id}`)}>
                                    <td style={{ fontWeight: 600 }}>{c.name}</td>
                                    <td>
                                        <span className={`badge badge-${c.interview_status?.toLowerCase()}`}>
                                            {c.interview_status === 'EVALUATED' ? '평가완료' :
                                                c.interview_status === 'COMPLETED' ? '완료' :
                                                    c.interview_status === 'IN_PROGRESS' ? '진행중' : c.interview_status}
                                        </span>
                                    </td>
                                    <td>
                                        {c.decision
                                            ? <span className={`badge badge-${c.decision.toLowerCase()}`}>{c.decision === 'PASS' ? '합격' : '불합격'}</span>
                                            : <span className="text-muted">-</span>
                                        }
                                    </td>
                                    <td>{c.tech_score?.toFixed(1) ?? '-'}</td>
                                    <td>{c.problem_score?.toFixed(1) ?? '-'}</td>
                                    <td>{c.comm_score?.toFixed(1) ?? '-'}</td>
                                    <td>{c.nonverbal_score?.toFixed(1) ?? '-'}</td>
                                    <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                                        {c.applied_at ? new Date(c.applied_at).toLocaleDateString('ko-KR') : '-'}
                                    </td>
                                    <td onClick={e => e.stopPropagation()}>
                                        <Link
                                            to={`/admin/postings/${postingId}/candidates/${c.user_id}`}
                                            className="btn btn-secondary"
                                            style={{ padding: '6px 12px', fontSize: 12 }}
                                        >
                                            상세보기
                                        </Link>
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
