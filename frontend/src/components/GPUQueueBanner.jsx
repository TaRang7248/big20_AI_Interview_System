/**
 * GPUQueueBanner — Phase 3 (Section 3-5: GPU Queue 429 UX)
 *
 * Displayed when server returns HTTP 429 (E_GPU_QUEUE_LIMIT).
 * Shows:
 * - Queue status message
 * - 30-second countdown before auto-retry
 * - Cancel option
 *
 * Contract:
 * - Only shown for VIDEO mode 429 errors
 * - TEXT mode is never affected by GPU queue
 * - Auto-retry fires onRetry callback with new trace_id
 */

import React, { useState, useEffect, useCallback } from 'react'
import { createTraceId, ActionTrace } from '../lib/traceId'

const RETRY_DELAY_SEC = 30

export default function GPUQueueBanner({ onRetry, onCancel, errorData }) {
    const [countdown, setCountdown] = useState(RETRY_DELAY_SEC)
    const [retrying, setRetrying] = useState(false)

    // Count down from RETRY_DELAY_SEC then auto-retry
    useEffect(() => {
        if (countdown <= 0) {
            handleRetry()
            return
        }
        const timer = setTimeout(() => setCountdown(c => c - 1), 1000)
        return () => clearTimeout(timer)
    }, [countdown])

    const handleRetry = useCallback(async () => {
        if (retrying) return
        setRetrying(true)
        const traceId = createTraceId()
        ActionTrace.trigger(traceId, 'gpu-queue:retry')
        await onRetry?.(traceId)
        setRetrying(false)
        setCountdown(RETRY_DELAY_SEC)
    }, [onRetry, retrying])

    const handleManualRetry = () => {
        setCountdown(0)
    }

    return (
        <div style={styles.overlay}>
            <div style={styles.banner}>
                <div style={styles.iconRow}>
                    <span style={styles.icon}>⏳</span>
                    <span style={styles.title}>GPU 대기열 가득 참</span>
                </div>

                <p style={styles.message}>
                    현재 최대 동시 VIDEO 면접 세션 수에 도달했습니다.
                    <br />
                    <span style={styles.note}>잠시 후 자동으로 재시도합니다. (TEXT 면접은 영향 없음)</span>
                </p>

                {errorData?.trace_id && (
                    <div style={styles.traceRow}>
                        <span style={styles.traceLabel}>Trace ID:</span>
                        <code style={styles.traceId}>{errorData.trace_id}</code>
                    </div>
                )}

                <div style={styles.countdownRow}>
                    <div style={styles.countdownCircle}>
                        <span style={styles.countdownNum}>{countdown}</span>
                        <span style={styles.countdownSec}>초</span>
                    </div>
                    <span style={styles.countdownLabel}>후 자동 재시도</span>
                </div>

                <div style={styles.actions}>
                    <button
                        onClick={handleManualRetry}
                        style={styles.retryBtn}
                        disabled={retrying}
                    >
                        {retrying ? '재시도 중...' : '지금 재시도'}
                    </button>
                    <button
                        onClick={onCancel}
                        style={styles.cancelBtn}
                    >
                        취소
                    </button>
                </div>
            </div>
        </div>
    )
}

const styles = {
    overlay: {
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.75)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        backdropFilter: 'blur(6px)',
    },
    banner: {
        background: 'linear-gradient(135deg, #1e293b, #0f172a)',
        border: '1px solid rgba(245,158,11,0.4)',
        borderRadius: 16,
        padding: '32px 40px',
        maxWidth: 440,
        width: '90vw',
        textAlign: 'center',
        boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
    },
    iconRow: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 12,
        marginBottom: 16,
    },
    icon: { fontSize: 32 },
    title: {
        fontSize: 20,
        fontWeight: 700,
        color: '#f59e0b',
    },
    message: {
        color: '#94a3b8',
        fontSize: 15,
        lineHeight: 1.6,
        marginBottom: 20,
    },
    note: {
        fontSize: 13,
        color: '#64748b',
    },
    traceRow: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        marginBottom: 16,
        padding: '8px 12px',
        background: 'rgba(15,23,42,0.8)',
        borderRadius: 8,
    },
    traceLabel: { fontSize: 11, color: '#64748b' },
    traceId: { fontSize: 11, color: '#f59e0b', fontFamily: 'monospace' },
    countdownRow: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 12,
        marginBottom: 24,
    },
    countdownCircle: {
        width: 64,
        height: 64,
        borderRadius: '50%',
        background: 'rgba(245,158,11,0.1)',
        border: '2px solid rgba(245,158,11,0.4)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
    },
    countdownNum: { fontSize: 22, fontWeight: 700, color: '#f59e0b', lineHeight: 1 },
    countdownSec: { fontSize: 10, color: '#92400e' },
    countdownLabel: { color: '#94a3b8', fontSize: 14 },
    actions: { display: 'flex', gap: 12, justifyContent: 'center' },
    retryBtn: {
        padding: '10px 24px',
        background: 'linear-gradient(135deg, #d97706, #b45309)',
        border: 'none',
        borderRadius: 8,
        color: '#fff',
        fontWeight: 600,
        cursor: 'pointer',
        fontSize: 14,
    },
    cancelBtn: {
        padding: '10px 24px',
        background: 'transparent',
        border: '1px solid #334155',
        borderRadius: 8,
        color: '#94a3b8',
        cursor: 'pointer',
        fontSize: 14,
    },
}
