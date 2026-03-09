import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { jobsApi } from '../../services/api'
import AdminInterviewPolicyPanel from './AdminInterviewPolicyPanel'

export default function AdminPostingNew() {
    const navigate = useNavigate()
    const [form, setForm] = useState({
        title: '', company: '', description: '', location: '',
        headcount: '', deadline: '', tags: '',
        // AI Policy fields (Frozen at Publish)
        total_question_limit: 10,
        question_timeout_sec: 120,
        mode: 'ACTUAL',
        persona: 'professional',
        evaluation_weights: { job: 40, comm: 30, attitude: 30 },
        fixed_questions: [],
        wiring_resume_q_enabled: true,
        wiring_rag_enabled: true,
        wiring_multimodal_enabled: true,
    })
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')

    function handleChange(e) {
        const { name, value } = e.target
        setForm(f => ({ ...f, [name]: value }))
    }

    async function handleSubmit(e) {
        e.preventDefault()
        if (!form.title) { setError('공고 제목은 필수입니다.'); return }
        if (!form.description || form.description.length < 10) {
            setError('공고 설명은 10자 이상 입력해야 합니다.'); return
        }
        setLoading(true)
        setError('')
        try {
            const payload = {
                ...form,
                headcount: form.headcount ? parseInt(form.headcount) : null,
                total_question_limit: parseInt(form.total_question_limit),
                question_timeout_sec: parseInt(form.question_timeout_sec),
                tags: form.tags ? form.tags.split(',').map(t => t.trim()).filter(Boolean) : [],
            }
            await jobsApi.create(payload)
            navigate('/admin/postings')
        } catch (err) {
            setError(err.response?.data?.detail || '공고 등록 중 오류가 발생했습니다.')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div>
            <div className="page-header">
                <h1 className="page-title">신규 공고 등록</h1>
                <p className="page-subtitle">새로운 채용 공고를 작성합니다.</p>
            </div>

            <div style={{ maxWidth: 680 }}>
                <form onSubmit={handleSubmit} className="card">
                    {error && <div className="alert alert-error">{error}</div>}

                    {/* ── 공고 입력 정보 (게시 후 수정 지양) ── */}
                    <div style={{ marginBottom: 8 }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 14 }}>
                            📋 공고 기본 정보
                        </div>
                    </div>

                    <div className="form-group">
                        <label className="form-label">공고 제목 <span style={{ color: 'var(--danger)' }}>*</span></label>
                        <input name="title" className="form-input" placeholder="직무명/공고 제목" value={form.title} onChange={handleChange} />
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label className="form-label">회사명</label>
                            <input name="company" className="form-input" placeholder="회사명" value={form.company} onChange={handleChange} />
                        </div>
                        <div className="form-group">
                            <label className="form-label">근무지</label>
                            <input name="location" className="form-input" placeholder="서울 강남구" value={form.location} onChange={handleChange} />
                        </div>
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label className="form-label">채용 인원</label>
                            <input name="headcount" className="form-input" type="number" min="1" placeholder="명" value={form.headcount} onChange={handleChange} />
                        </div>
                        <div className="form-group">
                            <label className="form-label">지원 마감일</label>
                            <input name="deadline" className="form-input" type="date" value={form.deadline} onChange={handleChange} />
                        </div>
                    </div>

                    <div className="form-group">
                        <label className="form-label">공고 설명 <span style={{ color: 'var(--danger)' }}>*</span></label>
                        <textarea
                            name="description"
                            className="form-input"
                            style={{ minHeight: 100, resize: 'vertical' }}
                            placeholder="직무 설명, 자격 요건 등 (LLM 질문 생성에 활용됩니다)"
                            value={form.description}
                            onChange={handleChange}
                        />
                    </div>

                    <div className="form-group">
                        <label className="form-label">태그 (쉼표로 구분)</label>
                        <input name="tags" className="form-input" placeholder="Python, React, 경력 3년" value={form.tags} onChange={handleChange} />
                    </div>

                    {/* ── AI 정책 설정 (Frozen at Publish) ── */}
                    <AdminInterviewPolicyPanel
                        form={form}
                        onChange={handleChange}
                        isLocked={false}
                    />

                    <div className="flex gap-4" style={{ marginTop: 24 }}>
                        <button type="button" className="btn btn-secondary flex-1" onClick={() => navigate('/admin/postings')}>
                            취소
                        </button>
                        <button type="submit" className="btn btn-primary flex-1" disabled={loading}>
                            {loading ? '등록 중...' : '공고 등록'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}
