import React, { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { jobsApi } from '../../services/api'
import AdminResumeDownloadButton from '../../components/AdminResumeDownloadButton'
import {
    Chart as ChartJS, RadialLinearScale, PointElement,
    LineElement, Filler, Tooltip, Legend,
} from 'chart.js'
import { Radar } from 'react-chartjs-2'

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend)

export default function AdminCandidateDetail() {
    const { postingId, userId } = useParams()
    const [data, setData] = useState(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        jobsApi.getCandidateDetail(postingId, userId)
            .then(res => setData(res.data))
            .catch(console.error)
            .finally(() => setLoading(false))
    }, [postingId, userId])

    if (loading) return <div className="loading"><div className="spinner" /></div>
    if (!data) return <div className="empty-state"><p>데이터를 찾을 수 없습니다.</p></div>

    const user = data.user || {}
    const evalData = data.evaluation
    const isPass = evalData?.decision === 'PASS'

    const radarData = evalData ? {
        labels: ['기술 역량', '문제 해결', '의사소통', '비언어적'],
        datasets: [{
            label: '점수',
            data: [evalData.tech_score, evalData.problem_score, evalData.comm_score, evalData.nonverbal_score],
            backgroundColor: 'rgba(99,102,241,0.2)',
            borderColor: '#6366F1',
            borderWidth: 2,
            pointBackgroundColor: '#6366F1',
        }]
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
            }
        }
    }

    return (
        <div>
            <div className="page-header">
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
                    <Link to="/admin/postings" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>공고 관리</Link>
                    {' / '}
                    <Link to={`/admin/postings/${postingId}`} style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>공고 상세</Link>
                    {' / '}
                    <span style={{ color: 'var(--text-primary)' }}>{user.name}</span>
                </div>
                <h1 className="page-title">{user.name} 지원자 상세</h1>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 24 }}>
                {/* User bio */}
                <div className="card">
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 16, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        지원자 정보
                    </div>
                    {[
                        ['이름', user.name],
                        ['생년월일', user.birth_date],
                        ['성별', user.gender === 'M' ? '남성' : user.gender === 'F' ? '여성' : user.gender],
                        ['이메일', user.email],
                        ['전화', user.phone],
                        ['주소', user.address],
                    ].map(([k, v]) => v ? (
                        <div key={k} className="flex" style={{ marginBottom: 10, fontSize: 14 }}>
                            <span style={{ color: 'var(--text-muted)', minWidth: 70 }}>{k}</span>
                            <span style={{ color: 'var(--text-primary)', wordBreak: 'break-all' }}>{v}</span>
                        </div>
                    ) : null)}
                </div>

                {/* Resume & decision */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    {data.resume && (
                        <div className="card">
                            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                이력서
                            </div>
                            <div className="flex items-center gap-4">
                                <span style={{ fontSize: 28 }}>📎</span>
                                <div style={{ flex: 1 }}>
                                    <div style={{ fontWeight: 600, fontSize: 14 }}>{data.resume.file_name}</div>
                                    <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                                        {new Date(data.resume.uploaded_at).toLocaleDateString('ko-KR')} 업로드
                                    </div>
                                </div>
                                {/* Section 46: Admin download requires access_reason_code */}
                                <AdminResumeDownloadButton candidateUserId={userId} />
                            </div>
                        </div>
                    )}

                    {evalData && (
                        <div className={`result-decision ${isPass ? 'pass' : 'fail'}`} style={{ padding: 24 }}>
                            <div className="decision-emoji" style={{ fontSize: 40 }}>{isPass ? '🎉' : '😔'}</div>
                            <div className={`decision-text ${isPass ? 'pass' : 'fail'}`} style={{ fontSize: 24 }}>
                                {isPass ? '합격' : '불합격'}
                            </div>
                            <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 8 }}>{evalData.summary}</p>
                        </div>
                    )}
                </div>
            </div>

            {/* Scores + radar */}
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

            {/* Chat history */}
            {data.chat_history && data.chat_history.length > 0 && (
                <div className="card">
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 16, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        면접 대화 기록
                    </div>
                    <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                        <div className="chat-container" style={{ padding: 0 }}>
                            {data.chat_history.map((msg, idx) => (
                                <div
                                    key={idx}
                                    style={{ display: 'flex', flexDirection: 'column', alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start' }}
                                >
                                    <div className="chat-label">
                                        {msg.role === 'ai' ? '🤖 AI 면접관' : '🙋 지원자'}
                                        {msg.phase && <span style={{ marginLeft: 6, fontSize: 9, color: 'var(--accent-1)' }}>[{msg.phase}]</span>}
                                    </div>
                                    <div className={`chat-bubble ${msg.role}`}>
                                        {msg.content}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
