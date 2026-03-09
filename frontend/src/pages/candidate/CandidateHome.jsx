import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { interviewsApi } from '../../services/api'

function formatDate(d) {
    if (!d) return '-'
    return new Date(d).toLocaleDateString('ko-KR', { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function CandidateHome() {
    const [interviews, setInterviews] = useState([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        interviewsApi.list()
            .then(res => setInterviews(res.data))
            .catch(console.error)
            .finally(() => setLoading(false))
    }, [])

    if (loading) {
        return <div className="loading"><div className="spinner" />면접 기록 불러오는 중...</div>
    }

    return (
        <div>
            <div className="page-header flex justify-between items-center">
                <div>
                    <h1 className="page-title">내 면접 기록</h1>
                    <p className="page-subtitle">지금까지 응시한 면접 이력과 결과를 확인하세요.</p>
                </div>
                <Link to="/candidate/postings" className="btn btn-primary">
                    ➕ 면접 신청
                </Link>
            </div>

            {interviews.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-icon">📋</div>
                    <p>아직 면접 기록이 없습니다.</p>
                    <Link to="/candidate/postings" className="btn btn-primary" style={{ marginTop: 16, display: 'inline-flex' }}>
                        채용 공고 보러가기
                    </Link>
                </div>
            ) : (
                <div className="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>공고명</th>
                                <th>응시일</th>
                                <th>상태</th>
                                <th>합/불합</th>
                                <th>기술</th>
                                <th>문제해결</th>
                                <th>의사소통</th>
                                <th>비언적</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            {interviews.map(iv => (
                                <tr key={iv.session_id}>
                                    <td style={{ fontWeight: 600 }}>{iv.job_title || iv.job_id}</td>
                                    <td style={{ color: 'var(--text-muted)' }}>{formatDate(iv.created_at)}</td>
                                    <td>
                                        <span className={`badge badge-${iv.status?.toLowerCase()}`}>
                                            {iv.status === 'EVALUATED' ? '평가완료' :
                                                iv.status === 'COMPLETED' ? '완료' :
                                                    iv.status === 'IN_PROGRESS' ? '진행중' : iv.status}
                                        </span>
                                    </td>
                                    <td>
                                        {iv.decision ? (
                                            <span className={`badge badge-${iv.decision.toLowerCase()}`}>
                                                {iv.decision === 'PASS' ? '합격' : '불합격'}
                                            </span>
                                        ) : '-'}
                                    </td>
                                    <td>{iv.tech_score != null ? `${iv.tech_score}점` : '-'}</td>
                                    <td>{iv.problem_score != null ? `${iv.problem_score}점` : '-'}</td>
                                    <td>{iv.comm_score != null ? `${iv.comm_score}점` : '-'}</td>
                                    <td>{iv.nonverbal_score != null ? `${iv.nonverbal_score}점` : '-'}</td>
                                    <td>
                                        {(iv.status === 'EVALUATED' || iv.status === 'COMPLETED') && (
                                            <Link
                                                to={`/candidate/result/${iv.session_id}`}
                                                className="btn btn-secondary"
                                                style={{ padding: '6px 12px', fontSize: 12 }}
                                            >
                                                결과보기
                                            </Link>
                                        )}
                                        {iv.status === 'IN_PROGRESS' && (
                                            <Link
                                                to={`/candidate/interview/${iv.session_id}`}
                                                className="btn btn-primary"
                                                style={{ padding: '6px 12px', fontSize: 12 }}
                                            >
                                                계속하기
                                            </Link>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Summary stats */}
            {interviews.length > 0 && (
                <div className="card-grid" style={{ marginTop: 24 }}>
                    <div className="stat-card">
                        <div className="stat-icon" style={{ background: 'rgba(99,102,241,0.15)', color: 'var(--accent-1)' }}>📋</div>
                        <div>
                            <div className="stat-value">{interviews.length}</div>
                            <div className="stat-label">총 면접 횟수</div>
                        </div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-icon" style={{ background: 'rgba(16,185,129,0.15)', color: 'var(--success)' }}>✅</div>
                        <div>
                            <div className="stat-value">{interviews.filter(i => i.decision === 'PASS').length}</div>
                            <div className="stat-label">합격</div>
                        </div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-icon" style={{ background: 'rgba(239,68,68,0.15)', color: 'var(--danger)' }}>❌</div>
                        <div>
                            <div className="stat-value">{interviews.filter(i => i.decision === 'FAIL').length}</div>
                            <div className="stat-label">불합격</div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
