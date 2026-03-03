/**
 * TracedButton - Mutation button with rapid-click guard (Sections 23, 42)
 *
 * Implements the Section 23.1 Button Lifecycle:
 * 1. UI Trigger Log (trace_id)
 * 2. Enter pending state (block concurrent clicks)
 * 3. Execute action
 * 4. Release pending state on completion
 *
 * trace_id is shared with the API via header injection in api.js.
 */

import React, { useState, useCallback, useRef } from 'react'
import { createTraceId, ActionTrace } from '../lib/traceId'

export default function TracedButton({
    onClick,         // async (traceId) => void
    actionName,      // human-readable name for tracing
    children,
    disabled = false,
    style = {},
    variant = 'primary',  // 'primary' | 'danger' | 'ghost'
    type = 'button',
    id,
}) {
    const [isPending, setIsPending] = useState(false)
    const pendingTraceId = useRef(null)

    const handleClick = useCallback(async () => {
        if (isPending || disabled) return

        // Section 42: same trace_id reuse if already pending
        if (pendingTraceId.current) return

        const traceId = createTraceId()
        pendingTraceId.current = traceId

        ActionTrace.trigger(traceId, actionName || 'button:click')
        setIsPending(true)

        try {
            await onClick(traceId)
        } finally {
            setIsPending(false)
            pendingTraceId.current = null
        }
    }, [isPending, disabled, onClick, actionName])

    const isDisabled = disabled || isPending

    const baseStyle = {
        padding: '10px 20px',
        borderRadius: 8,
        border: 'none',
        fontWeight: 600,
        fontSize: 14,
        cursor: isDisabled ? 'not-allowed' : 'pointer',
        opacity: isDisabled ? 0.6 : 1,
        transition: 'all 0.15s ease',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        ...style,
    }

    const variantStyle = {
        primary: { background: 'linear-gradient(135deg, #3b82f6, #6366f1)', color: '#fff' },
        danger: { background: 'linear-gradient(135deg, #ef4444, #dc2626)', color: '#fff' },
        ghost: { background: 'transparent', color: '#9ca3af', border: '1px solid #374151' },
    }[variant] || variantStyle.primary

    return (
        <button
            id={id}
            type={type}
            onClick={handleClick}
            disabled={isDisabled}
            style={{ ...baseStyle, ...variantStyle }}
        >
            {isPending ? (
                <>
                    <span className="spinner" style={{ width: 16, height: 16, border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.7s linear infinite', display: 'inline-block' }} />
                    처리 중...
                </>
            ) : children}
        </button>
    )
}
