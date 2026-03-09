import React from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

function NavItem({ to, icon, label }) {
    return (
        <NavLink
            to={to}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
        >
            <span>{icon}</span>
            <span>{label}</span>
        </NavLink>
    )
}

export default function AppLayout({ children }) {
    const { user, logout, isAdmin } = useAuth()
    const navigate = useNavigate()

    function handleLogout() {
        logout()
        navigate('/login')
    }

    return (
        <div className="app-layout">
            <aside className="sidebar">
                <div className="sidebar-logo">
                    <h2>IMH</h2>
                    <span>AI 면접 시스템</span>
                </div>

                <nav className="sidebar-nav">
                    {isAdmin ? (
                        <div className="nav-section">
                            <div className="nav-section-label">관리자</div>
                            <NavItem to="/admin/postings" icon="📋" label="공고 관리" />
                            <NavItem to="/admin/postings/new" icon="➕" label="공고 등록" />
                        </div>
                    ) : (
                        <div className="nav-section">
                            <div className="nav-section-label">면접자</div>
                            <NavItem to="/candidate/home" icon="🏠" label="내 면접 기록" />
                            <NavItem to="/candidate/postings" icon="📋" label="채용 공고" />
                            <NavItem to="/candidate/resume" icon="📄" label="이력서" />
                            <NavItem to="/candidate/device-check" icon="🎥" label="환경 테스트" />
                        </div>
                    )}

                    <div className="nav-section" style={{ marginTop: 'auto' }}>
                        <div className="nav-section-label">계정</div>
                        <NavItem to="/account" icon="👤" label="회원정보 수정" />
                        <button className="nav-item" onClick={handleLogout}>
                            <span>🚪</span>
                            <span>로그아웃</span>
                        </button>
                    </div>
                </nav>

                <div style={{ padding: '16px 24px', borderTop: '1px solid var(--glass-border)' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                        {user?.name || user?.user_id}
                    </div>
                    <div style={{
                        fontSize: '10px',
                        color: 'var(--accent-1)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.1em',
                        marginTop: '2px'
                    }}>
                        {user?.user_type === 'ADMIN' ? '관리자' : '면접자'}
                    </div>
                </div>
            </aside>

            <main className="main-content">
                {children}
            </main>
        </div>
    )
}
