/**
 * Core API Service Layer with Trace-ID & Error Code Contract (Sections 2.2, 23, 44, 79)
 *
 * Rules:
 * - Every mutation generates a trace_id via X-Trace-Id header
 * - All errors are normalized to { error_code, trace_id, message }
 * - 401s try to refresh token first; on refresh failure → global logout
 * - 409s are treated as "already processed" (success for mutations)
 */

import axios from 'axios'
import { createTraceId, ActionTrace } from '../lib/traceId'
import { httpStatusToErrorCode, getErrorMessage, ERROR_CODES } from '../lib/errorCodes'

const api = axios.create({
    baseURL: '/api/v1',
    headers: { 'Content-Type': 'application/json' },
    timeout: 15000, // 15s max (Section 2.3: 10s watchdog warning, 15s abort)
})

// ─── Internal: Token Refresh State ─────────────────────────────────────────
let _isRefreshing = false
let _refreshQueue = []  // [{resolve, reject}] — queued requests during refresh

function _processRefreshQueue(newToken) {
    _refreshQueue.forEach(({ resolve }) => resolve(newToken))
    _refreshQueue = []
}

async function _doRefresh() {
    const refreshToken = localStorage.getItem('imh_refresh_token')
    if (!refreshToken) throw new Error('No refresh token')

    const res = await axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken })
    const { token, refresh_token: newRefresh } = res.data
    localStorage.setItem('imh_token', token)
    if (newRefresh) localStorage.setItem('imh_refresh_token', newRefresh)
    return token
}

function _globalLogout() {
    localStorage.removeItem('imh_token')
    localStorage.removeItem('imh_refresh_token')
    localStorage.removeItem('imh_user')
    window.dispatchEvent(new CustomEvent('imh:auth:logout'))
    window.location.href = '/login'
}

// ─── Request Interceptor: Inject Auth Token + Trace ID ─────────────────────
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('imh_token')
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }

    // Inject trace_id per Section 2.2
    if (!config.headers['X-Trace-Id']) {
        const traceId = createTraceId()
        config.headers['X-Trace-Id'] = traceId
        config._traceId = traceId
        ActionTrace.apiStart(traceId, config.method?.toUpperCase(), config.url)
    }

    return config
})

// ─── Response Interceptor: Normalize Errors + JWT Refresh (Section 44) ─────
api.interceptors.response.use(
    (res) => {
        const traceId = res.config._traceId
        if (traceId) {
            ActionTrace.apiResponse(traceId, res.status)
        }
        return res
    },
    async (err) => {
        const traceId = err.config?._traceId || 'unknown'
        const status = err.response?.status
        const originalRequest = err.config

        // ─── 401: Try Token Refresh Before Global Logout (Section 44) ────
        if (status === 401 && !originalRequest._retryAfterRefresh) {
            originalRequest._retryAfterRefresh = true

            if (_isRefreshing) {
                // Queue this request — will retry with new token after refresh completes
                return new Promise((resolve, reject) => {
                    _refreshQueue.push({ resolve, reject })
                }).then((newToken) => {
                    originalRequest.headers.Authorization = `Bearer ${newToken}`
                    return api(originalRequest)
                })
            }

            _isRefreshing = true
            try {
                const newToken = await _doRefresh()
                _processRefreshQueue(newToken)
                originalRequest.headers.Authorization = `Bearer ${newToken}`
                return api(originalRequest)  // Retry original request with new token
            } catch (refreshErr) {
                // Refresh failed → Global Logout
                _refreshQueue.forEach(({ reject }) => reject(refreshErr))
                _refreshQueue = []
                ActionTrace.error(traceId, ERROR_CODES.E_AUTH_REFRESH_FAILED, 'Token refresh failed → global logout')
                _globalLogout()
                return Promise.reject(normalizeError(err, traceId))
            } finally {
                _isRefreshing = false
            }
        }

        return Promise.reject(normalizeError(err, traceId))
    }
)

// ─── Normalize error into contract shape ────────────────────────────────────
function normalizeError(err, traceId) {
    const status = err.response?.status
    const serverData = err.response?.data || {}

    // Use server-provided error_code if available, else derive from HTTP status
    const errorCode =
        err.response?.headers?.['x-error-code'] ||
        serverData.error_code ||
        httpStatusToErrorCode(status)

    const normalized = {
        error_code: errorCode,
        trace_id: serverData.trace_id || traceId,
        message: serverData.detail || serverData.message || getErrorMessage(errorCode),
        status,
    }

    ActionTrace.error(traceId, errorCode, normalized.message)
    return normalized
}

// ─── Auth API ────────────────────────────────────────────────────────────────
export const authApi = {
    login: (data) => api.post('/auth/login', data),
    signup: (data) => api.post('/auth/signup', data),
    me: () => api.get('/auth/me'),
    updateAccount: (data) => api.patch('/auth/account', data),
    logout: () => api.post('/auth/logout'),
    refresh: (refreshToken) => api.post('/auth/refresh', { refresh_token: refreshToken }),
}

// ─── Jobs API ────────────────────────────────────────────────────────────────
export const jobsApi = {
    list: (params) => api.get('/jobs', { params }),
    get: (jobId) => api.get(`/jobs/${jobId}`),
    create: (data) => api.post('/jobs', data),
    update: (jobId, data) => api.patch(`/jobs/${jobId}`, data),
    publish: (jobId) => api.post(`/jobs/${jobId}/publish`),   // Phase 2-1
    close: (jobId) => api.post(`/jobs/${jobId}/close`),       // Phase 2-1
    listCandidates: (jobId) => api.get(`/jobs/${jobId}/candidates`),
    getCandidateDetail: (jobId, userId) => api.get(`/jobs/${jobId}/candidates/${userId}`),
}

// ─── Interviews API ──────────────────────────────────────────────────────────
export const interviewsApi = {
    list: () => api.get('/interviews'),
    create: (jobId) => api.post('/interviews', { job_id: jobId }),
    get: (id) => api.get(`/interviews/${id}`),
    getChat: (id) => api.get(`/interviews/${id}/chat`),
    sendChat: (id, content) => api.post(`/interviews/${id}/chat`, { content }),
    getResult: (id) => api.get(`/interviews/${id}/result`),
}

// ─── Resume API ──────────────────────────────────────────────────────────────
export const resumeApi = {
    upload: (formData) => api.post('/resume/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    }),
    get: () => api.get('/resume'),
    download: () => api.get('/resume/download', { responseType: 'blob' }),
    auditHistory: (resumeId) => api.get(`/resume/${resumeId}/audit-history`),
}

// ─── Health API ──────────────────────────────────────────────────────────────
export const healthApi = {
    check: () => api.get('/health'),
}

export default api
