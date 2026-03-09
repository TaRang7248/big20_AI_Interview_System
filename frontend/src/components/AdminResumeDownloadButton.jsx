/**
 * AdminResumeDownloadButton - Admin resume download with mandatory access_reason_code (Section 46)
 *
 * Contracts:
 * - access_reason_code is REQUIRED before the request is sent
 * - No download request is made if reason code is empty
 * - trace_id is generated and sent to server for audit log linkage
 * - Shows audit confirmation after successful download
 */

import React, { useState } from 'react'
import TracedButton from './TracedButton'
import ErrorBanner from './ErrorBanner'
import { createTraceId, ActionTrace } from '../lib/traceId'

const REASON_OPTIONS = [
    { value: '', label: '접근 사유 선택 (필수)' },
    { value: 'HIRING_REVIEW', label: '채용 검토' },
    { value: 'COMPLIANCE_AUDIT', label: '컴플라이언스 감사' },
    { value: 'SUPPORT_INVESTIGATION', label: '지원 조사' },
    { value: 'LEGAL_REQUEST', label: '법적 요청' },
    { value: 'QUALITY_ASSURANCE', label: '품질 보증' },
]

export default function AdminResumeDownloadButton({ candidateUserId }) {
    const [showDialog, setShowDialog] = useState(false)
    const [reasonCode, setReasonCode] = useState('')
    const [error, setError] = useState(null)
    const [auditConfirmed, setAuditConfirmed] = useState(null)

    const handleOpenDialog = () => {
        setShowDialog(true)
        setReasonCode('')
        setError(null)
        setAuditConfirmed(null)
    }

    const handleDownload = async (traceId) => {
        // Section 46: Frontend enforces non-empty reason code BEFORE sending request
        if (!reasonCode) {
            setError({ error_code: 'E_FORBIDDEN', trace_id: traceId, message: '접근 사유 코드를 선택해야 다운로드가 가능합니다.' })
            return
        }

        ActionTrace.trigger(traceId, 'admin:resume:download')

        const url = `/api/v1/resume/admin-download?` +
            `candidate_user_id=${encodeURIComponent(candidateUserId)}` +
            `&access_reason_code=${encodeURIComponent(reasonCode)}` +
            `&trace_id=${encodeURIComponent(traceId)}`

        const token = localStorage.getItem('imh_token')
        try {
            const res = await fetch(url, {
                headers: {
                    Authorization: `Bearer ${token}`,
                    'X-Trace-Id': traceId,
                },
            })

            if (!res.ok) {
                const data = await res.json().catch(() => ({}))
                setError({
                    error_code: data.error_code || (res.status === 400 ? 'E_CAPABILITY_SIGNATURE_INVALID' : 'E_FORBIDDEN'),
                    trace_id: traceId,
                    message: data.detail || '다운로드에 실패했습니다.',
                })
                return
            }

            // Trigger browser download
            const blob = await res.blob()
            const a = document.createElement('a')
            a.href = URL.createObjectURL(blob)
            a.download = `resume_${candidateUserId}`
            document.body.appendChild(a)
            a.click()
            document.body.removeChild(a)

            setAuditConfirmed({ traceId, reasonCode })
            setShowDialog(false)
            ActionTrace.stateApplied(traceId, 'AuditLog')
        } catch (err) {
            setError({ error_code: 'E_NETWORK', trace_id: traceId, message: '네트워크 오류가 발생했습니다.' })
        }
    }

    return (
        <>
            <TracedButton
                id={`resume-download-btn-${candidateUserId}`}
                onClick={async () => handleOpenDialog()}
                actionName="admin:open-resume-dialog"
                variant="ghost"
                style={{ fontSize: 13, padding: '6px 14px' }}
            >
                📥 이력서 다운로드
            </TracedButton>

            {/* Audit confirmation badge */}
            {auditConfirmed && (
                <div style={{ fontSize: 11, color: '#22c55e', marginTop: 4 }}>
                    ✅ Audit 기록 완료 (Ref: {auditConfirmed.traceId.slice(0, 12)}...)
                </div>
            )}

            {/* Dialog overlay */}
            {showDialog && (
                <div style={styles.overlay} onClick={(e) => e.target === e.currentTarget && setShowDialog(false)}>
                    <div style={styles.dialog}>
                        <h3 style={{ color: '#f1f5f9', marginBottom: 8, fontSize: 18 }}>이력서 다운로드</h3>
                        <p style={{ color: '#94a3b8', fontSize: 14, marginBottom: 20 }}>
                            이 다운로드는 <strong>보안 감사 로그에 기록</strong>됩니다. 접근 사유를 반드시 선택하세요.
                        </p>

                        <ErrorBanner error={error} onDismiss={() => setError(null)} />

                        <div style={{ marginBottom: 20 }}>
                            <label style={styles.label}>접근 사유 코드 (필수)</label>
                            <select
                                id="access-reason-select"
                                value={reasonCode}
                                onChange={e => setReasonCode(e.target.value)}
                                style={styles.select}
                            >
                                {REASON_OPTIONS.map(opt => (
                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                ))}
                            </select>
                        </div>

                        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
                            <button
                                onClick={() => setShowDialog(false)}
                                style={styles.cancelBtn}
                            >
                                취소
                            </button>
                            <TracedButton
                                id="confirm-download-btn"
                                onClick={handleDownload}
                                actionName="admin:resume:confirm-download"
                                disabled={!reasonCode}
                                style={{ padding: '10px 24px' }}
                            >
                                감사 로그 기록 후 다운로드
                            </TracedButton>
                        </div>
                    </div>
                </div>
            )}
        </>
    )
}

const styles = {
    overlay: {
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        backdropFilter: 'blur(4px)',
    },
    dialog: {
        background: '#1e293b',
        border: '1px solid #334155',
        borderRadius: 16,
        padding: 32,
        width: '100%',
        maxWidth: 480,
        boxShadow: '0 24px 64px rgba(0,0,0,0.5)',
    },
    label: {
        display: 'block',
        fontSize: 13,
        fontWeight: 600,
        color: '#94a3b8',
        marginBottom: 8,
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
    },
    select: {
        width: '100%',
        padding: '12px 16px',
        background: '#0f172a',
        border: '1px solid #334155',
        borderRadius: 8,
        color: '#f1f5f9',
        fontSize: 14,
        cursor: 'pointer',
        outline: 'none',
    },
    cancelBtn: {
        padding: '10px 20px',
        background: 'transparent',
        border: '1px solid #374151',
        borderRadius: 8,
        color: '#9ca3af',
        cursor: 'pointer',
        fontSize: 14,
    },
}
