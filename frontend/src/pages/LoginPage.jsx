import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function LoginPage() {
    const { login } = useAuth()
    const navigate = useNavigate()
    const [form, setForm] = useState({ username: '', password: '' })
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)

    async function handleSubmit(e) {
        e.preventDefault()
        if (!form.username || !form.password) {
            setError('아이디와 비밀번호를 입력해주세요.')
            return
        }
        setLoading(true)
        setError('')
        try {
            const user = await login(form.username, form.password)
            navigate(user.user_type === 'ADMIN' ? '/admin/postings' : '/candidate/home')
        } catch (err) {
            const msg = err.message || err.response?.data?.detail || '아이디 또는 비밀번호가 일치하지 않습니다.'
            setError(msg)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="auth-layout">
            <div className="auth-card">
                <div className="auth-logo">
                    <h1>IMH</h1>
                    <p>AI 면접 시뮬레이션 시스템</p>
                </div>

                <form onSubmit={handleSubmit}>
                    {error && <div className="alert alert-error">{error}</div>}

                    <div className="form-group">
                        <label className="form-label">아이디</label>
                        <input
                            id="login-username"
                            className="form-input"
                            type="text"
                            placeholder="아이디를 입력하세요"
                            value={form.username}
                            onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                            autoComplete="username"
                        />
                    </div>

                    <div className="form-group">
                        <label className="form-label">비밀번호</label>
                        <input
                            id="login-password"
                            className="form-input"
                            type="password"
                            placeholder="비밀번호를 입력하세요"
                            value={form.password}
                            onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                            autoComplete="current-password"
                        />
                    </div>

                    <button
                        id="login-submit"
                        type="submit"
                        className="btn btn-primary btn-full"
                        disabled={loading}
                    >
                        {loading ? '로그인 중...' : '로그인'}
                    </button>
                </form>

                <div style={{ textAlign: 'center', marginTop: '24px', fontSize: '13px', color: 'var(--text-muted)' }}>
                    계정이 없으신가요?{' '}
                    <Link to="/signup" style={{ color: 'var(--accent-1)', fontWeight: 600 }}>
                        회원가입
                    </Link>
                </div>
                <div style={{ textAlign: 'center', marginTop: '8px', fontSize: '12px', color: 'var(--text-muted)' }}>
                    <span style={{ cursor: 'pointer', textDecoration: 'underline' }}>
                        아이디/비밀번호 찾기
                    </span>
                </div>
            </div>
        </div>
    )
}
