/**
 * AdminDecisionOverride — Slice D: Decision Override UI (TASK-FRONT-001)
 *
 * Contracts enforced:
 * - No optimistic update: success is confirmed only by audit/projection refresh
 * - Error format: RAW error_code + trace_id (no user-friendly rewrite)
 * - Confirm modal before submission (audit log reminder included)
 * - Admin Authority Boundary: this component must never be rendered in candidate view
 * - On success: caller provides onSuccess() which triggers authority pull + audit refresh
 */

import React, { useState, useCallback, useRef } from 'react'
import { createTraceId, ActionTrace } from '../../lib/traceId'

function getTokenHeader() {
    return {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('imh_token')}`,
    }
}

const OVERRIDE_OPTIONS = [
    { value: 'PASS', label: '합격으로 변경 (PASS)' },
    { value: 'FAIL', label: '불합격으로 변경 (FAIL)' },
]

export default function AdminDecisionOverride({ sessionId, currentDecision, onSuccess }) {
    const [showModal, setShowModal] = useState(false)
    const [selectedDecision, setSelectedDecision] = useState('')
    const [reason, setReason] = useState('')
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [error, setError] = useState(null)
    const [copyDone, setCopyDone] = useState(false)
    const traceIdRef = useRef(null)

    const openModal = (decision) => {
        setSelectedDecision(decision)
        setError(null)
        setReason('')
        setShowModal(true)
    }

    const handleSubmit = useCallback(async () => {
        if (!selectedDecision || !reason.trim() || isSubmitting) return

        const traceId = createTraceId()
        traceIdRef.current = traceId
        ActionTrace.trigger(traceId, 'admin:decision-override')
        setIsSubmitting(true)
        setError(null)

        try {
            const res = await fetch(`/api/v1/interviews/${sessionId}/decision/override`, {
                method: 'POST',
                headers: { ...getTokenHeader(), 'X-Trace-Id': traceId },
                body: JSON.stringify({
                    decision: selectedDecision,
                    override_reason: reason.trim(),
                }),
            })

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}))
                throw {
                    error_code: errData.error_code || 'E_OVERRIDE_FAILED',
                    trace_id: errData.trace_id || traceId,
                    status: res.status,
                    message: errData.detail || errData.message || 'Override 처리에 실패했습니다.',
                }
            }

            ActionTrace.stateApplied(traceId, 'override:success')
            setShowModal(false)
            setReason('')
            // Success is confirmed by authority pull + audit refresh — NOT optimistically
            onSuccess?.()
        } catch (err) {
            setError(err.error_code ? err : { error_code: 'E_OVERRIDE_FAILED', trace_id: traceId, message: String(err.message || err) })
        } finally {
            setIsSubmitting(false)
        }
    }, [sessionId, selectedDecision, reason, isSubmitting, onSuccess])

    const copySupport = () => {
        const payload = [
            `session_id: ${sessionId}`,
            `trace_id: ${traceIdRef.current || 'N/A'}`,
            `error: ${error?.error_code || 'N/A'}`,
        ].join('\n')
        navigator.clipboard?.writeText(payload).then(() => {
            setCopyDone(true)
            setTimeout(() => setCopyDone(false), 1500)
        })
    }

    return (
        <div>
            {/* Override Trigger Buttons */}
            <div style={s.btnRow}>
                {OVERRIDE_OPTIONS.filter(opt => opt.value !== currentDecision).map(opt => (
                    <button key={opt.value} onClick={() => openModal(opt.value)} style={s.overrideBtn}>
                        ✏️ {opt.label}
                    </button>
                ))}
            </div>

            {/* Confirm Modal */}
            {showModal && (
                <div style={s.modalOverlay}>
                    <div style={s.modal}>
                        <h3 style={s.modalTitle}>결정 Override 확인</h3>
                        <div style={s.warningBox}>
                            <p style={{ color: '#fde047', margin: 0, fontSize: 13 }}>
                                ⚠️ 이 작업은 감사 로그에 기록됩니다.<br />
                                되돌리기 정책은 서버 정책에 따릅니다.
                            </p>
                        </div>

                        <div style={s.fieldGroup}>
                            <label style={s.label}>변경할 결정</label>
                            <div style={s.decisionBadge}>
                                {selectedDecision === 'PASS' ? '✅ 합격 (PASS)' : '❌ 불합격 (FAIL)'}
                            </div>
                        </div>

                        <div style={s.fieldGroup}>
                            <label style={s.label}>Override 사유 (필수)</label>
                            <textarea
                                id="override-reason-input"
                                value={reason}
                                onChange={e => setReason(e.target.value)}
                                placeholder="Override 사유를 입력하세요 (감사 로그에 기록됨)"
                                style={s.textarea}
                                rows={3}
                                disabled={isSubmitting}
                            />
                        </div>

                        {/* RAW error display on failure */}
                        {error && (
                            <div style={s.errorBox}>
                                <p style={{ fontFamily: 'monospace', color: '#f87171', fontSize: 12, margin: 0 }}>
                                    {error.error_code} · {error.trace_id || 'N/A'}
                                </p>
                                {error.message && (
                                    <p style={{ color: '#94a3b8', fontSize: 12, margin: '4px 0 0' }}>{error.message}</p>
                                )}
                                <button onClick={copySupport} style={s.smallBtnGhost}>
                                    {copyDone ? '✓ 복사됨' : 'Copy for Support'}
                                </button>
                            </div>
                        )}

                        <div style={s.modalActions}>
                            <button
                                onClick={() => { setShowModal(false); setError(null) }}
                                style={s.cancelBtn}
                                disabled={isSubmitting}
                            >
                                취소
                            </button>
                            <button
                                id="confirm-override-btn"
                                onClick={handleSubmit}
                                style={s.confirmBtn}
                                disabled={!reason.trim() || isSubmitting}
                            >
                                {isSubmitting ? '처리 중...' : '확인 (감사 로그 기록)'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}

const s = {
    btnRow: { display: 'flex', gap: 8, flexWrap: 'wrap' },
    overrideBtn: {
        padding: '8px 16px',
        background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.4)',
        borderRadius: 8, color: '#f59e0b', cursor: 'pointer', fontSize: 13, fontWeight: 600,
    },
    modalOverlay: {
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999,
        backdropFilter: 'blur(4px)',
    },
    modal: {
        background: '#1e293b', border: '1px solid #334155', borderRadius: 16,
        padding: 32, maxWidth: 480, width: '90vw',
        boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
    },
    modalTitle: { color: '#f1f5f9', fontSize: 18, fontWeight: 700, marginTop: 0, marginBottom: 16 },
    warningBox: {
        background: 'rgba(234,179,8,0.08)', border: '1px solid rgba(234,179,8,0.3)',
        borderRadius: 8, padding: '10px 14px', marginBottom: 20,
    },
    fieldGroup: { marginBottom: 16 },
    label: { display: 'block', color: '#64748b', fontSize: 12, fontWeight: 600, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' },
    decisionBadge: { color: '#f1f5f9', fontWeight: 700, fontSize: 15 },
    textarea: {
        width: '100%', padding: '8px 12px',
        background: '#0f172a', border: '1px solid #334155', borderRadius: 6,
        color: '#f1f5f9', fontSize: 13, resize: 'vertical', outline: 'none',
        fontFamily: 'inherit', boxSizing: 'border-box',
    },
    errorBox: {
        background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)',
        borderRadius: 8, padding: '10px 14px', marginBottom: 16,
    },
    smallBtnGhost: {
        marginTop: 8, padding: '4px 10px', background: 'transparent',
        border: '1px solid #334155', borderRadius: 4, color: '#64748b', cursor: 'pointer', fontSize: 11,
    },
    modalActions: { display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 8 },
    cancelBtn: {
        padding: '10px 20px', background: 'transparent',
        border: '1px solid #334155', borderRadius: 8, color: '#94a3b8', cursor: 'pointer', fontSize: 14,
    },
    confirmBtn: {
        padding: '10px 20px',
        background: 'linear-gradient(135deg, #d97706, #b45309)',
        border: 'none', borderRadius: 8, color: '#fff', fontWeight: 600,
        cursor: 'pointer', fontSize: 14,
    },
}
