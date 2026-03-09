import React, { useState } from 'react'
import { authApi } from '../services/api'
import { useAuth } from '../contexts/AuthContext'

export default function AccountPage() {
    const { user } = useAuth()
    const [form, setForm] = useState({
        current_password: '',
        phone: '',
        email: '',
    })
    const [success, setSuccess] = useState('')
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)

    async function handleSubmit(e) {
        e.preventDefault()
        if (!form.current_password) {
            setError('현재 비밀번호를 입력해주세요.')
            return
        }
        setLoading(true)
        setError('')
        setSuccess('')
        try {
            await authApi.updateAccount({
                current_password: form.current_password,
                phone: form.phone || undefined,
                email: form.email || undefined,
            })
            setSuccess('정보가 성공적으로 업데이트되었습니다.')
            setForm(f => ({ ...f, current_password: '' }))
        } catch (err) {
            setError(err.response?.data?.detail || '업데이트 중 오류가 발생했습니다.')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div>
            <div className="page-header">
                <h1 className="page-title">회원정보 수정</h1>
                <p className="page-subtitle">전화번호와 이메일을 변경할 수 있습니다.</p>
            </div>

            <div style={{ maxWidth: 480 }}>
                <div className="card">
                    <div style={{ marginBottom: 24 }}>
                        <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 4 }}>현재 계정</div>
                        <div style={{ fontWeight: 700, fontSize: 18 }}>{user?.name}</div>
                        <div style={{ fontSize: 13, color: 'var(--accent-1)' }}>
                            {user?.user_type === 'ADMIN' ? '관리자' : '면접자'}
                        </div>
                    </div>

                    <form onSubmit={handleSubmit}>
                        {error && <div className="alert alert-error">{error}</div>}
                        {success && <div className="alert alert-success">{success}</div>}

                        <div className="form-group">
                            <label className="form-label">현재 비밀번호 (변경 확인용)</label>
                            <input
                                className="form-input"
                                type="password"
                                placeholder="현재 비밀번호"
                                value={form.current_password}
                                onChange={e => setForm(f => ({ ...f, current_password: e.target.value }))}
                            />
                        </div>

                        <div className="form-group">
                            <label className="form-label">새 전화번호</label>
                            <input
                                className="form-input"
                                type="tel"
                                placeholder="010-0000-0000 (변경하지 않으면 빈칸)"
                                value={form.phone}
                                onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
                            />
                        </div>

                        <div className="form-group">
                            <label className="form-label">새 이메일</label>
                            <input
                                className="form-input"
                                type="email"
                                placeholder="example@email.com (변경하지 않으면 빈칸)"
                                value={form.email}
                                onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                            />
                        </div>

                        <button
                            type="submit"
                            className="btn btn-primary btn-full"
                            disabled={loading}
                        >
                            {loading ? '업데이트 중...' : '변경사항 저장'}
                        </button>
                    </form>
                </div>
            </div>
        </div>
    )
}
