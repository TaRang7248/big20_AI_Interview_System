/**
 * AuthContext - Thin bridge between Zustand AuthStore and React component tree.
 * (Sections 44, B - FRONT-TASK-01)
 *
 * Provides React hooks for UI components using the Zustand store underneath.
 * No business logic here - pure state delegation.
 */

import React, { createContext, useContext, useCallback } from 'react'
import { authApi } from '../services/api'
import { useAuthStore } from '../stores/authStore'
import { createTraceId, ActionTrace } from '../lib/traceId'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
    const { user, token, setSession, clearSession, setLoading, setError } = useAuthStore()

    const login = useCallback(async (username, password) => {
        const traceId = createTraceId()
        ActionTrace.trigger(traceId, 'auth:login')
        setLoading(true)
        try {
            const res = await authApi.login({ username, password })
            const { token, refresh_token, user_id, name, user_type, email, phone } = res.data
            const userData = { user_id, name, user_type, email, phone }
            setSession(token, userData, refresh_token)  // Section 44: persist refresh_token
            ActionTrace.stateApplied(traceId, 'AuthStore')
            return userData
        } catch (err) {
            const error = err.error_code ? err : { error_code: 'E_UNKNOWN', trace_id: traceId, message: '로그인에 실패했습니다.' }
            setError(error)
            throw error
        }
    }, [setSession, setLoading, setError])

    const logout = useCallback(() => {
        clearSession()
    }, [clearSession])

    const isAdmin = user?.user_type === 'ADMIN'
    const isCandidate = user?.user_type === 'CANDIDATE'

    return (
        <AuthContext.Provider value={{ user, token, isAdmin, isCandidate, login, logout }}>
            {children}
        </AuthContext.Provider>
    )
}

export function useAuth() {
    const ctx = useContext(AuthContext)
    if (!ctx) throw new Error('useAuth must be used within AuthProvider')
    return ctx
}
