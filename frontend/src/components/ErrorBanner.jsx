/**
 * ErrorBanner - Standard error display component (Section 23, 79)
 *
 * Displays: user-facing message + Reference Code (trace_id) for support.
 * Never exposes raw server error details to the user.
 */

import React from 'react'

export default function ErrorBanner({ error, onDismiss }) {
    if (!error) return null

    const { message, trace_id, error_code } = error

    return (
        <div
            style={{
                background: 'linear-gradient(135deg, #2d1b1b, #3d2020)',
                border: '1px solid #ef4444',
                borderRadius: 8,
                padding: '12px 16px',
                marginBottom: 16,
                display: 'flex',
                alignItems: 'flex-start',
                gap: 12,
            }}
            role="alert"
        >
            <span style={{ fontSize: 20, flexShrink: 0 }}>⚠️</span>
            <div style={{ flex: 1 }}>
                <p style={{ color: '#fca5a5', margin: 0, fontWeight: 600, fontSize: 15 }}>
                    요청 처리 실패
                </p>
                <p style={{ color: '#f87171', margin: '4px 0 0', fontSize: 14 }}>
                    {message || '알 수 없는 오류가 발생했습니다.'}
                </p>
                {trace_id && (
                    <p style={{ color: '#6b7280', margin: '6px 0 0', fontSize: 12, fontFamily: 'monospace' }}>
                        참조 코드: {trace_id}
                    </p>
                )}
            </div>
            {onDismiss && (
                <button
                    onClick={onDismiss}
                    style={{ background: 'none', border: 'none', color: '#9ca3af', cursor: 'pointer', fontSize: 18, padding: 0 }}
                    aria-label="오류 닫기"
                >
                    ×
                </button>
            )}
        </div>
    )
}
