/**
 * useSSEProjection - SSE hook with event_seq inversion guard (Section 37, C contract)
 *
 * PRIMARY MODE: SSE is the primary projection source.
 * Polling is the fallback when SSE fails to connect or drops 3+ consecutive times.
 *
 * Contracts:
 * - event_seq in every event payload; inversion → authority pull + discard
 * - Gap (event_seq jump > GAP_THRESHOLD) → authority pull, then resume
 * - 3 consecutive connection drops → fallback polling authority pull
 * - Reconnect via Last-Event-ID on disconnect
 * - Authority pull uses `onAuthorityPull(sessionId)` callback
 *
 * Usage:
 *   const { connected, lastSeq, sseError } = useSSEProjection(sessionId, onAuthorityPull, onEvent)
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { createTraceId, ActionTrace } from '../lib/traceId'

const SSE_BASE_URL = '/api/v1/sessions'
const MAX_RECONNECT_DELAY_MS = 30000
const GAP_THRESHOLD = 1            // If seq jump > this, trigger authority pull
const CONSECUTIVE_DROP_LIMIT = 3   // 3 consecutive drops → fallback authority pull

export function useSSEProjection(sessionId, onAuthorityPull, onEvent) {
    const [connected, setConnected] = useState(false)
    const [lastSeq, setLastSeq] = useState(0)
    const [sseError, setSseError] = useState(null)

    const lastSeqRef = useRef(0)
    const eventSourceRef = useRef(null)
    const reconnectDelayRef = useRef(1000)
    const reconnectTimerRef = useRef(null)
    const mountedRef = useRef(true)
    const consecutiveDropsRef = useRef(0)  // Section 37: 3-drop fallback counter

    const triggerAuthorityPull = useCallback(() => {
        const traceId = createTraceId()
        ActionTrace.trigger(traceId, `sse:authority-pull:${sessionId}`)
        onAuthorityPull?.(sessionId)
    }, [sessionId, onAuthorityPull])

    const connectSSE = useCallback(() => {
        if (!sessionId || !mountedRef.current) return

        const lastEventId = lastSeqRef.current > 0 ? lastSeqRef.current : null
        const url = `${SSE_BASE_URL}/${sessionId}/multimodal/stream` +
            (lastEventId ? `?lastEventId=${lastEventId}` : '')

        const traceId = createTraceId()
        ActionTrace.trigger(traceId, `sse:connect:${sessionId}`)

        const es = new EventSource(url)
        eventSourceRef.current = es

        es.addEventListener('projection', (event) => {
            // Reset drop counter on any successful event
            consecutiveDropsRef.current = 0

            try {
                const data = JSON.parse(event.data)
                const receivedSeq = data.event_seq

                if (typeof receivedSeq !== 'number') {
                    // No seq in payload — skip inversion check, deliver raw
                    onEvent?.(data)
                    return
                }

                // ─── Inversion Guard (Section 37 / SSE Contract) ──────────────────
                if (receivedSeq <= lastSeqRef.current) {
                    ActionTrace.error(
                        traceId,
                        'E_SSE_SEQUENCE_INVERSION',
                        `event_seq=${receivedSeq} <= last_seen=${lastSeqRef.current}. Discarding + authority pull.`
                    )
                    console.warn(
                        `[SSE] Inversion detected: received seq=${receivedSeq}, last_seen=${lastSeqRef.current}. Authority pull triggered.`
                    )
                    triggerAuthorityPull()
                    return  // Discard the out-of-order event
                }

                // ─── Gap Guard ────────────────────────────────────────────────────
                if (receivedSeq - lastSeqRef.current > GAP_THRESHOLD) {
                    console.warn(
                        `[SSE] Gap detected: expected next=${lastSeqRef.current + 1}, got=${receivedSeq}. Authority pull triggered.`
                    )
                    triggerAuthorityPull()
                    // Do NOT return — process this event after pull (it's a valid future event)
                }

                // Update last seen seq
                lastSeqRef.current = receivedSeq
                setLastSeq(receivedSeq)

                // Deliver event to consumer
                onEvent?.(data)
                ActionTrace.stateApplied(traceId, `SSE:seq=${receivedSeq}`)
            } catch (parseErr) {
                console.error('[SSE] Failed to parse event data:', parseErr)
            }
        })

        es.onopen = () => {
            if (!mountedRef.current) return
            setConnected(true)
            setSseError(null)
            reconnectDelayRef.current = 1000  // Reset backoff on success
            consecutiveDropsRef.current = 0   // Reset drop counter on successful connect
            ActionTrace.apiResponse(traceId, 200)
        }

        es.onerror = (err) => {
            if (!mountedRef.current) return
            setConnected(false)
            es.close()

            // Count consecutive drops
            consecutiveDropsRef.current += 1

            // Section 37: 3 consecutive drops → authority pull fallback
            if (consecutiveDropsRef.current >= CONSECUTIVE_DROP_LIMIT) {
                console.warn(
                    `[SSE] ${consecutiveDropsRef.current} consecutive drops. Triggering authority pull fallback.`
                )
                triggerAuthorityPull()
                consecutiveDropsRef.current = 0  // Reset after fallback
            }

            // Exponential backoff reconnect
            const delay = Math.min(reconnectDelayRef.current, MAX_RECONNECT_DELAY_MS)
            reconnectDelayRef.current = Math.min(delay * 2, MAX_RECONNECT_DELAY_MS)

            ActionTrace.error(traceId, 'E_NETWORK', `SSE drop #${consecutiveDropsRef.current}, reconnecting in ${delay}ms`)
            setSseError({
                error_code: 'E_NETWORK',
                message: `SSE 연결 끊김. ${delay / 1000}초 후 재연결...`
            })

            reconnectTimerRef.current = setTimeout(() => {
                if (mountedRef.current) connectSSE()
            }, delay)
        }
    }, [sessionId, triggerAuthorityPull, onEvent])

    useEffect(() => {
        mountedRef.current = true
        connectSSE()

        return () => {
            mountedRef.current = false
            clearTimeout(reconnectTimerRef.current)
            if (eventSourceRef.current) {
                eventSourceRef.current.close()
                eventSourceRef.current = null
            }
        }
    }, [connectSSE])

    return { connected, lastSeq, sseError }
}
