/**
 * AuthStore (Section B: State Determinism Rules, Section 44)
 *
 * Rules:
 * - No optimistic updates for auth state
 * - Store cleared on 401 or logout event
 * - isAdmin / isCandidate derived from server-provided user_type
 */

import { create } from 'zustand'

const AUTH_TOKEN_KEY = 'imh_token'
const AUTH_REFRESH_KEY = 'imh_refresh_token'
const AUTH_USER_KEY = 'imh_user'

function loadUserFromStorage() {
    try {
        const raw = localStorage.getItem(AUTH_USER_KEY)
        return raw ? JSON.parse(raw) : null
    } catch {
        return null
    }
}

export const useAuthStore = create((set, get) => ({
    user: loadUserFromStorage(),
    token: localStorage.getItem(AUTH_TOKEN_KEY) || null,
    isLoading: false,
    error: null,

    // Derived
    get isAdmin() { return get().user?.user_type === 'ADMIN' },
    get isCandidate() { return get().user?.user_type === 'CANDIDATE' },
    get isAuthenticated() { return !!get().user },

    setSession: (token, user, refreshToken) => {
        localStorage.setItem(AUTH_TOKEN_KEY, token)
        localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user))
        if (refreshToken) localStorage.setItem(AUTH_REFRESH_KEY, refreshToken)
        set({ token, user, error: null })
    },

    clearSession: () => {
        localStorage.removeItem(AUTH_TOKEN_KEY)
        localStorage.removeItem(AUTH_REFRESH_KEY)
        localStorage.removeItem(AUTH_USER_KEY)
        set({ token: null, user: null, error: null })
    },

    setLoading: (isLoading) => set({ isLoading }),
    setError: (error) => set({ error, isLoading: false }),
}))

// Listen for global 401 auth clear event from API interceptor
window.addEventListener('imh:auth:logout', () => {
    useAuthStore.getState().clearSession()
})
