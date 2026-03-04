import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'

// Common pages
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import AccountPage from './pages/AccountPage'

// Candidate pages
import CandidateHome from './pages/candidate/CandidateHome'
import CandidatePostings from './pages/candidate/CandidatePostings'
import CandidateResume from './pages/candidate/CandidateResume'
import DeviceCheck from './pages/candidate/DeviceCheck'
import InterviewSession from './pages/candidate/InterviewSession'
import InterviewResult from './pages/candidate/InterviewResult'
import VideoInterviewSession from './pages/candidate/VideoInterviewSession'  // Phase 3

// Admin pages
import AdminPostings from './pages/admin/AdminPostings'
import AdminPostingNew from './pages/admin/AdminPostingNew'
import AdminPostingEdit from './pages/admin/AdminPostingEdit'
import AdminPostingDetail from './pages/admin/AdminPostingDetail'
import AdminCandidateDetail from './pages/admin/AdminCandidateDetail'
import AdminJobStats from './pages/admin/AdminJobStats'

// Layout
import AppLayout from './components/AppLayout'

function PrivateRoute({ children, adminOnly = false }) {
    const { user, isAdmin } = useAuth()
    if (!user) return <Navigate to="/login" replace />
    if (adminOnly && !isAdmin) return <Navigate to="/candidate/home" replace />
    return children
}

function PublicRoute({ children }) {
    const { user, isAdmin } = useAuth()
    if (user) {
        return <Navigate to={isAdmin ? '/admin/postings' : '/candidate/home'} replace />
    }
    return children
}

function AppRoutes() {
    return (
        <Routes>
            {/* Public */}
            <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
            <Route path="/signup" element={<PublicRoute><SignupPage /></PublicRoute>} />

            {/* Protected common */}
            <Route path="/account" element={<PrivateRoute><AppLayout><AccountPage /></AppLayout></PrivateRoute>} />

            {/* Candidate routes */}
            <Route path="/candidate/home" element={<PrivateRoute><AppLayout><CandidateHome /></AppLayout></PrivateRoute>} />
            <Route path="/candidate/postings" element={<PrivateRoute><AppLayout><CandidatePostings /></AppLayout></PrivateRoute>} />
            <Route path="/candidate/resume" element={<PrivateRoute><AppLayout><CandidateResume /></AppLayout></PrivateRoute>} />
            <Route path="/candidate/device-check" element={<PrivateRoute><AppLayout><DeviceCheck /></AppLayout></PrivateRoute>} />
            <Route path="/candidate/interview/:interviewId" element={<PrivateRoute><InterviewSession /></PrivateRoute>} />
            {/* Phase 3: VIDEO mode — capability gate redirect handled in VideoInterviewSession */}
            <Route path="/candidate/interview/:interviewId/video" element={<PrivateRoute><VideoInterviewSession /></PrivateRoute>} />
            <Route path="/candidate/result/:interviewId" element={<PrivateRoute><AppLayout><InterviewResult /></AppLayout></PrivateRoute>} />

            {/* Admin routes */}
            <Route path="/admin/postings" element={<PrivateRoute adminOnly><AppLayout><AdminPostings /></AppLayout></PrivateRoute>} />
            <Route path="/admin/postings/new" element={<PrivateRoute adminOnly><AppLayout><AdminPostingNew /></AppLayout></PrivateRoute>} />
            <Route path="/admin/postings/:postingId/edit" element={<PrivateRoute adminOnly><AppLayout><AdminPostingEdit /></AppLayout></PrivateRoute>} />
            <Route path="/admin/postings/:postingId" element={<PrivateRoute adminOnly><AppLayout><AdminPostingDetail /></AppLayout></PrivateRoute>} />
            <Route path="/admin/postings/:postingId/candidates/:userId" element={<PrivateRoute adminOnly><AppLayout><AdminCandidateDetail /></AppLayout></PrivateRoute>} />
            {/* Slice E: Stats Dashboard (Stats Snapshot Drift Guard — independent from session projection) */}
            <Route path="/admin/jobs/:jobId/stats" element={<PrivateRoute adminOnly><AppLayout><AdminJobStats /></AppLayout></PrivateRoute>} />

            {/* Default redirect */}
            <Route path="/" element={<Navigate to="/login" replace />} />
            <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
    )
}

export default function App() {
    return (
        <BrowserRouter>
            <AuthProvider>
                <AppRoutes />
            </AuthProvider>
        </BrowserRouter>
    )
}
