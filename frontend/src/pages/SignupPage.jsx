import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authApi } from '../services/api'

export default function SignupPage() {
    const navigate = useNavigate()
    const [form, setForm] = useState({
        username: '', password: '', confirmPassword: '',
        name: '', birth_date: '', gender: '', email: '',
        address: '', phone: '', user_type: 'CANDIDATE',
    })
    const [usernameStatus, setUsernameStatus] = useState(null) // null | 'ok' | 'taken' | 'checking'
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)

    function handleChange(e) {
        const { name, value } = e.target
        setForm(f => ({ ...f, [name]: value }))
        if (name === 'username') setUsernameStatus(null)
    }

    async function checkUsername() {
        if (!form.username) return
        setUsernameStatus('checking')
        try {
            const res = await authApi.checkUsername(form.username)
            setUsernameStatus(res.data.available ? 'ok' : 'taken')
        } catch {
            setUsernameStatus(null)
        }
    }

    async function handleSubmit(e) {
        e.preventDefault()
        if (!form.username || !form.password || !form.name) {
            setError('아이디, 비밀번호, 이름은 필수 입력 항목입니다.')
            return
        }
        if (form.password !== form.confirmPassword) {
            setError('비밀번호가 일치하지 않습니다.')
            return
        }
        if (usernameStatus === 'taken') {
            setError('이미 사용 중인 아이디입니다.')
            return
        }
        setLoading(true)
        setError('')
        try {
            await authApi.signup({
                username: form.username,
                password: form.password,
                name: form.name,
                birth_date: form.birth_date || null,
                gender: form.gender || null,
                email: form.email || null,
                address: form.address || null,
                phone: form.phone || null,
                user_type: form.user_type,
            })
            navigate('/login')
        } catch (err) {
            setError(err.response?.data?.detail || '회원가입 중 오류가 발생했습니다.')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="auth-layout">
            <div className="auth-card" style={{ maxWidth: 560 }}>
                <div className="auth-logo">
                    <h1>IMH</h1>
                    <p>신규 회원가입</p>
                </div>

                <form onSubmit={handleSubmit}>
                    {error && <div className="alert alert-error">{error}</div>}

                    {/* User type */}
                    <div className="form-group">
                        <label className="form-label">회원 유형</label>
                        <select
                            name="user_type"
                            className="form-select"
                            value={form.user_type}
                            onChange={handleChange}
                        >
                            <option value="CANDIDATE">면접자</option>
                            <option value="ADMIN">관리자</option>
                        </select>
                    </div>

                    {/* Username + check */}
                    <div className="form-group">
                        <label className="form-label">아이디</label>
                        <div className="flex gap-2">
                            <input
                                name="username"
                                className="form-input flex-1"
                                type="text"
                                placeholder="사용할 아이디"
                                value={form.username}
                                onChange={handleChange}
                            />
                            <button
                                type="button"
                                className="btn btn-secondary"
                                onClick={checkUsername}
                                style={{ whiteSpace: 'nowrap' }}
                            >
                                중복확인
                            </button>
                        </div>
                        {usernameStatus === 'ok' && (
                            <div style={{ color: 'var(--success)', fontSize: 12, marginTop: 4 }}>✓ 사용 가능한 아이디입니다.</div>
                        )}
                        {usernameStatus === 'taken' && (
                            <div style={{ color: 'var(--danger)', fontSize: 12, marginTop: 4 }}>✗ 이미 사용 중인 아이디입니다.</div>
                        )}
                        {usernameStatus === 'checking' && (
                            <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>확인 중...</div>
                        )}
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label className="form-label">비밀번호</label>
                            <input
                                name="password"
                                className="form-input"
                                type="password"
                                placeholder="6자 이상"
                                value={form.password}
                                onChange={handleChange}
                            />
                        </div>
                        <div className="form-group">
                            <label className="form-label">비밀번호 확인</label>
                            <input
                                name="confirmPassword"
                                className="form-input"
                                type="password"
                                placeholder="비밀번호 재입력"
                                value={form.confirmPassword}
                                onChange={handleChange}
                            />
                        </div>
                    </div>

                    {/* Personal info */}
                    <div className="form-row">
                        <div className="form-group">
                            <label className="form-label">이름</label>
                            <input
                                name="name"
                                className="form-input"
                                type="text"
                                placeholder="실명"
                                value={form.name}
                                onChange={handleChange}
                            />
                        </div>
                        <div className="form-group">
                            <label className="form-label">생년월일</label>
                            <input
                                name="birth_date"
                                className="form-input"
                                type="date"
                                value={form.birth_date}
                                onChange={handleChange}
                            />
                        </div>
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label className="form-label">성별</label>
                            <select
                                name="gender"
                                className="form-select"
                                value={form.gender}
                                onChange={handleChange}
                            >
                                <option value="">선택</option>
                                <option value="M">남성</option>
                                <option value="F">여성</option>
                                <option value="O">기타</option>
                            </select>
                        </div>
                        <div className="form-group">
                            <label className="form-label">전화번호</label>
                            <input
                                name="phone"
                                className="form-input"
                                type="tel"
                                placeholder="010-0000-0000"
                                value={form.phone}
                                onChange={handleChange}
                            />
                        </div>
                    </div>

                    <div className="form-group">
                        <label className="form-label">이메일</label>
                        <input
                            name="email"
                            className="form-input"
                            type="email"
                            placeholder="example@email.com"
                            value={form.email}
                            onChange={handleChange}
                        />
                    </div>

                    <div className="form-group">
                        <label className="form-label">주소</label>
                        <input
                            name="address"
                            className="form-input"
                            type="text"
                            placeholder="거주지 주소"
                            value={form.address}
                            onChange={handleChange}
                        />
                    </div>

                    <button
                        type="submit"
                        className="btn btn-primary btn-full"
                        disabled={loading}
                    >
                        {loading ? '가입 중...' : '회원가입'}
                    </button>
                </form>

                <div style={{ textAlign: 'center', marginTop: '20px', fontSize: '13px', color: 'var(--text-muted)' }}>
                    이미 계정이 있으신가요?{' '}
                    <Link to="/login" style={{ color: 'var(--accent-1)', fontWeight: 600 }}>로그인</Link>
                </div>
            </div>
        </div>
    )
}
