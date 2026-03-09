import React, { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { jobsApi } from '../../services/api'
import AdminInterviewPolicyPanel from './AdminInterviewPolicyPanel'

export default function AdminPostingEdit() {
    const { postingId } = useParams()
    const navigate = useNavigate()
    const [form, setForm] = useState(null)
    const [jobStatus, setJobStatus] = useState('DRAFT')  // Track published status
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState('')
    const [confirmAction, setConfirmAction] = useState(null)  // null | 'PUBLISH' | 'CLOSE'

    // Policy is Frozen at Publish: PUBLISHED / CLOSED → lock all AI policy fields
    const isPolicyFrozen = jobStatus === 'PUBLISHED' || jobStatus === 'CLOSED'

    useEffect(() => {
        jobsApi.get(postingId)
            .then(res => {
                const j = res.data
                const snap = j.policy || {}
                setJobStatus(j.status || 'DRAFT')
                setForm({
                    // ── Operational Metadata (always editable) ──────────────────────────
                    title: j.title || '',
                    description: j.description || '',
                    location: j.location || '',
                    headcount: j.headcount || '',
                    deadline: j.deadline || '',
                    tags: Array.isArray(j.tags) ? j.tags.join(', ') : '',
                    // ── AI Policy fields (Frozen at Publish → read-only) ─────────────
                    total_question_limit: snap.total_question_limit ?? 10,
                    question_timeout_sec: snap.question_timeout_sec ?? 120,
                    mode: snap.mode ?? 'ACTUAL',
                    persona: snap.persona ?? 'professional',
                    evaluation_weights: snap.evaluation_weights ?? { job: 40, comm: 30, attitude: 30 },
                    fixed_questions: snap.fixed_questions ?? [],
                    wiring_resume_q_enabled: snap.wiring_resume_q_enabled !== false,
                    wiring_rag_enabled: snap.wiring_rag_enabled !== false,
                    wiring_multimodal_enabled: snap.wiring_multimodal_enabled !== false,
                })
            })
            .catch(() => navigate('/admin/postings'))
            .finally(() => setLoading(false))
    }, [postingId])

    function handleChange(e) {
        const { name, value } = e.target
        setForm(f => ({ ...f, [name]: value }))
    }

    async function handleSubmit(e) {
        e.preventDefault()
        setSaving(true)
        setError('')
        try {
            // Only send Operational Metadata on update (AI Policy fields are frozen)
            const metadataPayload = {
                title: form.title,
                description: form.description,
                location: form.location,
                headcount: form.headcount ? parseInt(form.headcount) : null,
                deadline: form.deadline,
                tags: form.tags ? form.tags.split(',').map(t => t.trim()).filter(Boolean) : [],
            }
            await jobsApi.update(postingId, metadataPayload)
            navigate(`/admin/postings/${postingId}`)
        } catch (err) {
            setError(err.response?.data?.detail || '수정 중 오류가 발생했습니다.')
        } finally {
            setSaving(false)
        }
    }

    async function handleAction(action) {
        // 2-step inline confirmation: first click sets confirmAction, second click executes
        if (confirmAction !== action) {
            setConfirmAction(action)
            return
        }
        setConfirmAction(null)
        setSaving(true)
        try {
            if (action === 'PUBLISH') {
                await jobsApi.publish(postingId)
            } else if (action === 'CLOSE') {
                await jobsApi.close(postingId)
            }
            navigate(`/admin/postings/${postingId}`)
        } catch (err) {
            setError(err.message || err.response?.data?.detail || '오류가 발생했습니다.')
        } finally {
            setSaving(false)
        }
    }

    if (loading || !form) return <div className="loading"><div className="spinner" /></div>

    return (
        <div>
            <div className="page-header">
                <h1 className="page-title">공고 수정</h1>
                <p className="page-subtitle">
                    채용 공고 정보를 수정합니다.
                    {isPolicyFrozen && (
                        <span style={{
                            marginLeft: 10, fontSize: 13,
                            padding: '2px 10px', borderRadius: 99,
                            background: 'rgba(239,68,68,0.12)', color: '#f87171',
                            border: '1px solid rgba(239,68,68,0.3)', fontWeight: 600,
                        }}>
                            🔒 AI 정책 동결 중 ({jobStatus})
                        </span>
                    )}
                </p>
            </div>

            <div style={{ maxWidth: 680 }}>
                <form onSubmit={handleSubmit} className="card">
                    {error && <div className="alert alert-error">{error}</div>}

                    {/* ── Operational Metadata (always editable) ── */}
                    <div style={{ marginBottom: 8 }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 14 }}>
                            📋 공고 기본 정보 (상태 무관 수정 가능)
                        </div>
                    </div>

                    <div className="form-group">
                        <label className="form-label">공고 제목</label>
                        <input name="title" className="form-input" value={form.title} onChange={handleChange} />
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label className="form-label">근무지</label>
                            <input name="location" className="form-input" value={form.location} onChange={handleChange} />
                        </div>
                        <div className="form-group">
                            <label className="form-label">채용 인원</label>
                            <input name="headcount" className="form-input" type="number" value={form.headcount} onChange={handleChange} />
                        </div>
                    </div>

                    <div className="form-group">
                        <label className="form-label">마감일</label>
                        <input name="deadline" className="form-input" type="date" value={form.deadline} onChange={handleChange} />
                    </div>

                    <div className="form-group">
                        <label className="form-label">공고 설명</label>
                        <textarea
                            name="description"
                            className="form-input"
                            style={{ minHeight: 120, resize: 'vertical' }}
                            value={form.description}
                            onChange={handleChange}
                        />
                    </div>

                    <div className="form-group">
                        <label className="form-label">태그</label>
                        <input name="tags" className="form-input" value={form.tags} onChange={handleChange} />
                    </div>

                    {/* ── AI Policy Panel (Frozen when Published/Closed) ── */}
                    <AdminInterviewPolicyPanel
                        form={form}
                        onChange={handleChange}
                        isLocked={isPolicyFrozen}
                    />

                    <div className="flex gap-4" style={{ marginBottom: 16, marginTop: 24 }}>
                        <button type="button" className="btn btn-secondary flex-1" onClick={() => navigate(`/admin/postings/${postingId}`)}>취소</button>
                        <button type="submit" className="btn btn-primary flex-1" disabled={saving}>{saving ? '저장 중...' : '저장'}</button>
                    </div>
                </form>

                {/* ── Status Actions ── */}
                <div className="card" style={{ marginTop: 16 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12, color: 'var(--text-secondary)' }}>
                        공고 상태 변경
                        <span style={{ marginLeft: 8, fontSize: 11, color: '#64748b' }}>
                            현재: {jobStatus}
                        </span>
                    </div>
                    {isPolicyFrozen && (
                        <div style={{
                            background: 'rgba(234,179,8,0.08)', border: '1px solid rgba(234,179,8,0.25)',
                            borderRadius: 8, padding: '8px 12px', marginBottom: 12,
                            fontSize: 12, color: '#fde047',
                        }}>
                            ⚠️ 게시 후에는 AI 면접 정책(질문 수, 가중치, 페르소나 등)을 변경할 수 없습니다.
                        </div>
                    )}
                    <div className="flex gap-4">
                        <button
                            className="btn btn-success flex-1"
                            onClick={() => handleAction('PUBLISH')}
                            disabled={saving || jobStatus !== 'DRAFT'}
                            style={confirmAction === 'PUBLISH' ? { background: '#f59e0b', borderColor: '#f59e0b' } : {}}
                        >
                            {confirmAction === 'PUBLISH' ? '⚠️ 정말 게시합니까? (다시 클릭)' : '✅ 게시 (PUBLISH)'}
                        </button>
                        <button
                            className="btn btn-danger flex-1"
                            onClick={() => handleAction('CLOSE')}
                            disabled={saving || jobStatus !== 'PUBLISHED'}
                            style={confirmAction === 'CLOSE' ? { background: '#f59e0b', borderColor: '#f59e0b' } : {}}
                        >
                            {confirmAction === 'CLOSE' ? '⚠️ 정말 마감합니까? (다시 클릭)' : '🔒 조기 마감 (CLOSE)'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}
