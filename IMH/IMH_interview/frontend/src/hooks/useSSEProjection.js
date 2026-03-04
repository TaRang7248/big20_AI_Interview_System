/**
 * useSSEProjection — SSE Projection Hook (TASK-FRONT-001)
 *
 * Contracts enforced:
 * - Pull-In-Flight SSE Suppression: SSE events during authority pull are discarded (not buffered)
 * - event_seq inversion detected → discard event + trigger authority pull
 * - event_seq gap detected → trigger authority pull (event still processed)
 * - SSE reconnect first-event validation vs snapshot seq
 * - STALE state: heartbeat loss > 2x interval → disconnect mutations
 * - 3 consecutive drops on reconnect → authority pull fallback
 * - snapshot_hash dedup applied before calling onEvent (Idempotent Apply Rule)
 *
 * Usage:
 *   const { sseStatus, lastSeq, sseError } = useSSEProjection(sessionId, {
 *     isPullLocked,         // from sessionStore: suppress events during pull
 *     lastAppliedSeq,       // from sessionStore: for inversion guard
 *     onAuthorityPull,      // callback → triggers beginPull + fetches Step 1 + Step 2
 *     onEvent,              // callback → called with validated projection data
 *     onStaleModeChange,    // callback(isStale: boolean)
 *   })
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { createTraceId, ActionTrace } from '../lib/traceId'

const SSE_BASE_URL = '/api/v1/sessions'
const MAX_RECONNECT_DELAY_MS = 30000
const GAP_THRESHOLD = 1                // seq jump > 1 → authority pull
const CONSECUTIVE_DROP_LIMIT = 3       // consecutive drops → authority pull fallback
const HEARTBEAT_INTERVAL_MS = 15000    // Server heartbeat interval
const STALE_MULTIPLIER = 2             // STALE after 2x missed heartbeats

// SSE connection state machine values
export const SSE_STATUS = {
    CONNECTING: 'CONNECTING',
    LIVE: 'LIVE',
    STALE: 'STALE',
    SAFE_MODE: 'SAFE_MODE',
    RESYNCING: 'RESYNCING',
}

export function useSSEProjection(sessionId, {
    isPullLocked = false,
    lastAppliedSeq = 0,
    onAuthorityPull,
    onEvent,
    onStaleModeChange,
} = {}) {
    const [sseStatus, setSseStatus] = useState(SSE_STATUS.CONNECTING)
    const [lastSeq, setLastSeq] = useState(0)
    const [sseError, setSseError] = useState(null)

    const lastSeqRef = useRef(lastAppliedSeq)  // Kept in sync from store
    const isPullLockedRef = useRef(isPullLocked)
    const eventSourceRef = useRef(null)
    const reconnectDelayRef = useRef(1000)
    const reconnectTimerRef = useRef(null)
    const mountedRef = useRef(true)
    const consecutiveDropsRef = useRef(0)
    const heartbeatTimerRef = useRef(null)
    const isFirstEventAfterReconnectRef = useRef(true)

    // Keep refs in sync with latest props (closure safety)
    useEffect(() => { isPullLockedRef.current = isPullLocked }, [isPullLocked])
    useEffect(() => { lastSeqRef.current = lastAppliedSeq }, [lastAppliedSeq])

    // ─── Reset heartbeat timer ──────────────────────────────────────────────
    const resetHeartbeat = useCallback(() => {
        clearTimeout(heartbeatTimerRef.current)
        heartbeatTimerRef.current = setTimeout(() => {
            if (!mountedRef.current) return
            // Heartbeat lost > 2x interval → STALE
            setSseStatus(SSE_STATUS.STALE)
            onStaleModeChange?.(true)
        }, HEARTBEAT_INTERVAL_MS * STALE_MULTIPLIER)
    }, [onStaleModeChange])

    // ─── Trigger Authority Pull (shared by all pull trigger paths) ───────────
    const triggerAuthorityPull = useCallback(() => {
        const traceId = createTraceId()
        ActionTrace.trigger(traceId, `sse:authority-pull:${sessionId}`)
        setSseStatus(SSE_STATUS.RESYNCING)
        onAuthorityPull?.(sessionId)
    }, [sessionId, onAuthorityPull])

    // ─── Connect SSE ─────────────────────────────────────────────────────────
    const connectSSE = useCallback(() => {
        if (!sessionId || !mountedRef.current) return

        // Use last applied seq for reconnect resume
        const lastEventId = lastSeqRef.current > 0 ? lastSeqRef.current : null
        const url = `${SSE_BASE_URL}/${sessionId}/multimodal/stream` +
            (lastEventId ? `?lastEventId=${lastEventId}` : '')

        const traceId = createTraceId()
        ActionTrace.trigger(traceId, `sse:connect:${sessionId}`)

        setSseStatus(SSE_STATUS.CONNECTING)
        isFirstEventAfterReconnectRef.current = true

        const es = new EventSource(url)
        eventSourceRef.current = es

        // ── projection event handler ─────────────────────────────────────────
        es.addEventListener('projection', (event) => {
            consecutiveDropsRef.current = 0
            resetHeartbeat()

            // ── Pull-In-Flight SSE Suppression Rule ────────────────────────
            // If authority pull is in progress: discard WITHOUT buffering.
            if (isPullLockedRef.current) {
                ActionTrace.trigger(traceId, `sse:suppressed_during_pull:${sessionId}`)
                return
            }

            try {
                const data = JSON.parse(event.data)
                const receivedSeq = data.event_seq

                // ── Heartbeat event ────────────────────────────────────────
                if (data.type === 'heartbeat') {
                    setSseStatus(SSE_STATUS.LIVE)
                    onStaleModeChange?.(false)
                    return
                }

                if (typeof receivedSeq === 'number') {
                    // ── First-event-after-reconnect validation ─────────────
                    if (isFirstEventAfterReconnectRef.current) {
                        isFirstEventAfterReconnectRef.current = false
                        if (receivedSeq <= lastSeqRef.current) {
                            // First event is stale → authority pull
                            ActionTrace.error(traceId, 'E_SSE_FIRST_EVENT_STALE',
                                `First event after reconnect: seq=${receivedSeq} <= last_applied=${lastSeqRef.current}`)
                            triggerAuthorityPull()
                            return
                        }
                    }

                    // ── Inversion guard ────────────────────────────────────
                    if (receivedSeq <= lastSeqRef.current) {
                        ActionTrace.error(traceId, 'E_SSE_SEQUENCE_INVERSION',
                            `seq=${receivedSeq} <= last_applied=${lastSeqRef.current}`)
                        triggerAuthorityPull()
                        return  // Discard
                    }

                    // ── Gap guard ──────────────────────────────────────────
                    if (receivedSeq - lastSeqRef.current > GAP_THRESHOLD) {
                        ActionTrace.trigger(traceId, `sse:gap:${lastSeqRef.current}->${receivedSeq}`)
                        triggerAuthorityPull()
                        // Process event after pull is initiated (valid future event)
                    }

                    lastSeqRef.current = receivedSeq
                    setLastSeq(receivedSeq)
                } else {
                    // No seq in payload — pass through without inversion check
                    isFirstEventAfterReconnectRef.current = false
                }

                setSseStatus(SSE_STATUS.LIVE)
                onStaleModeChange?.(false)
                onEvent?.(data)
                ActionTrace.stateApplied(traceId, `SSE:seq=${receivedSeq ?? 'n/a'}`)
            } catch (parseErr) {
                console.error('[SSE] Failed to parse event data:', parseErr)
            }
        })

        // ── heartbeat event ──────────────────────────────────────────────────
        es.addEventListener('heartbeat', () => {
            consecutiveDropsRef.current = 0
            resetHeartbeat()
            setSseStatus(SSE_STATUS.LIVE)
            onStaleModeChange?.(false)
        })

        es.onopen = () => {
            if (!mountedRef.current) return
            setSseStatus(SSE_STATUS.LIVE)
            setSseError(null)
            reconnectDelayRef.current = 1000
            consecutiveDropsRef.current = 0
            onStaleModeChange?.(false)
            resetHeartbeat()
            ActionTrace.apiResponse(traceId, 200)
        }

        es.onerror = () => {
            if (!mountedRef.current) return
            clearTimeout(heartbeatTimerRef.current)
            setSseStatus(SSE_STATUS.STALE)
            es.close()

            consecutiveDropsRef.current += 1

            // 3 consecutive drops → authority pull fallback
            if (consecutiveDropsRef.current >= CONSECUTIVE_DROP_LIMIT) {
                ActionTrace.trigger(traceId, `sse:fallback_pull:drops=${consecutiveDropsRef.current}`)
                triggerAuthorityPull()
                consecutiveDropsRef.current = 0
            }

            const delay = Math.min(reconnectDelayRef.current, MAX_RECONNECT_DELAY_MS)
            reconnectDelayRef.current = Math.min(delay * 2, MAX_RECONNECT_DELAY_MS)

            setSseError({ error_code: 'E_NETWORK', message: `SSE 연결 끊김. ${delay / 1000}초 후 재연결...` })
            ActionTrace.error(traceId, 'E_NETWORK', `SSE drop #${consecutiveDropsRef.current}`)
            reconnectTimerRef.current = setTimeout(() => {
                if (mountedRef.current) connectSSE()
            }, delay)
        }
    }, [sessionId, triggerAuthorityPull, onEvent, onStaleModeChange, resetHeartbeat])

    // ─── Lifecycle ───────────────────────────────────────────────────────────
    // session_id change: fully tear down and re-subscribe (Cross-Tab / Multi-Session Isolation)
    useEffect(() => {
        mountedRef.current = true
        connectSSE()
        return () => {
            mountedRef.current = false
            clearTimeout(reconnectTimerRef.current)
            clearTimeout(heartbeatTimerRef.current)
            if (eventSourceRef.current) {
                eventSourceRef.current.close()
                eventSourceRef.current = null
            }
        }
    }, [connectSSE])  // connectSSE is stable while sessionId is stable

    return { sseStatus, lastSeq, sseError }
}
