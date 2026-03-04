/**
 * VideoInterviewSession — Slice B: Video/Multimodal Integration (TASK-FRONT-001)
 *
 * Contracts enforced:
 * - Authority Pull 2-Step Protocol: Step 1 (GET /sessions/{id}) REQUIRED;
 *   Step 2 = GET /sessions/{id}/multimodal/projection (Endpoint Flex Rule)
 * - Pull-In-Flight SSE Suppression: isPullLocked from store gates ALL SSE application
 * - Projection Full-Overwrite: setFromProjection (deep replace, no merge)
 * - Capability Drift Freeze: VIDEO/WEBRTC/BLIND_MODE locked to session snapshot; no live overwrite
 * - Initial Hydration Guard: video mutation DOM blocked until first valid projection
 * - Multimodal Null Safety: video_enabled ≠ question exists; question DOM only if snapshot provides it
 * - Terminal Race Guard: ABORTED/DECIDED/EVALUATED → WebRTC teardown + AbortController
 * - No-Template Fallback: no placeholder question text; error overlay + authority pull
 * - SAFE_MODE: all mutation DOM removed; navigation to Home still allowed
 * - Blind Mode: question text DOM removed (not hidden); aria-live also cleared
 * - GPU 429 UX: countdown banner; manual retry only (auto-resend forbidden)
 */

import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useSessionStore } from '../../stores/sessionStore'
import { useCapabilityStore } from '../../stores/capabilityStore'
import { useSSEProjection, SSE_STATUS } from '../../hooks/useSSEProjection'
import ErrorBanner from '../../components/ErrorBanner'
import GPUQueueBanner from '../../components/GPUQueueBanner'
import { createTraceId, ActionTrace } from '../../lib/traceId'

const MULTIMODAL_BASE = '/api/v1/sessions'
const TERMINAL_STATUSES = new Set(['ABORTED', 'DECIDED', 'EVALUATED'])

// Capability Drift Freeze: read once from snapshot; never re-read live policy
// These fields are hydrated by hydrateFromSession(session) on authority pull only.
function getTokenHeader() {
    return { Authorization: `Bearer ${localStorage.getItem('imh_token')}` }
}

export default function VideoInterviewSession() {
    const { interviewId } = useParams()
    const navigate = useNavigate()

    // ── SSE STALE banner state ─────────────────────────────────────────────
    const [isStaleBanner, setIsStaleBanner] = useState(false)
    const [hydrated, setHydrated] = useState(false)          // Initial Hydration Guard gate
    const [sttPartial, setSttPartial] = useState('')          // Ephemeral STT — never persisted
    const [webrtcState, setWebrtcState] = useState('idle')    // idle | connecting | connected | failed
    const [gpuQueue, setGpuQueue] = useState(null)            // 429 GPU queue data

    // WebRTC refs
    const pcRef = useRef(null)
    const localStreamRef = useRef(null)
    const localVideoRef = useRef(null)
    const remoteVideoRef = useRef(null)
    const abortControllerRef = useRef(null)   // Terminal Race Guard
    const chatBottomRef = useRef(null)

    // ── Store selectors ────────────────────────────────────────────────────
    const {
        status, currentPhase, currentQuestion, messages,
        isPullLocked, isSafeMode,
        lastAppliedSeq, lastSnapshotHash,
        isLoading, local_pending, error,
        beginPull, setFromProjection, pullFailed,
        applySSEEvent, setLocalPending, setError, reset,
        canMutate,
    } = useSessionStore()

    // Capability Drift Freeze: capabilities frozen to session snapshot (hydrateFromSession called once in pull)
    const {
        video_enabled, webrtc_enabled, blind_mode, ai_question_text_visible,
        hydrateFromSession, resetSession,
    } = useCapabilityStore()

    const isTerminal = TERMINAL_STATUSES.has(status)

    // ── Teardown WebRTC + pending requests ─────────────────────────────────
    const teardownWebRTC = useCallback(() => {
        pcRef.current?.close()
        pcRef.current = null
        localStreamRef.current?.getTracks().forEach(t => t.stop())
        localStreamRef.current = null
        setWebrtcState('idle')
    }, [])

    // ── Authority Pull: 2-Step Protocol ────────────────────────────────────
    const performAuthorityPull = useCallback(async () => {
        const traceId = createTraceId()
        ActionTrace.trigger(traceId, 'video-session:authority-pull')
        beginPull()   // → isPullLocked=true, SAFE_MODE entry

        // Terminal Race Guard: cancel any in-flight request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
            abortControllerRef.current = null
        }

        try {
            // Step 1: PG Authority Snapshot (REQUIRED)
            const sessionRes = await fetch(`/api/v1/interviews/${interviewId}`, {
                headers: { ...getTokenHeader() },
            })
            if (!sessionRes.ok) {
                const errData = await sessionRes.json().catch(() => ({}))
                // 409 E_SESSION_TERMINAL → redirect immediately
                if (sessionRes.status === 409) {
                    navigate(`/candidate/result/${interviewId}`)
                    return
                }
                throw { error_code: errData.error_code || 'E_PULL_FAILED', trace_id: traceId, status: sessionRes.status }
            }
            const session = await sessionRes.json()
            ActionTrace.stateApplied(traceId, 'Step1:success')

            // Capability Drift Freeze: hydrate capabilities from snapshot ONCE per pull
            // This is the only point where capabilities are set; never overwritten by live policy
            hydrateFromSession(session)

            // Step 2 (Endpoint Flex Rule): multimodal/projection if exists; SSE fallback otherwise
            let projectionData = null
            try {
                const projRes = await fetch(`${MULTIMODAL_BASE}/${interviewId}/multimodal/projection`, {
                    headers: { ...getTokenHeader() },
                })
                if (projRes.ok) {
                    projectionData = await projRes.json()
                    ActionTrace.stateApplied(traceId, 'Step2:multimodal-projection')
                }
                // 404/empty → fall through to SSE hydrate (handled by initial hydration guard)
            } catch {
                // Step 2 endpoint unavailable → SSE first valid event will hydrate (no error)
            }

            // Merge Step 1 + Step 2 into projection — full overwrite, no merge
            const projection = {
                sessionId: interviewId,
                jobId: session.job_id,
                jobTitle: session.job_title,
                status: session.status,
                currentPhase: session.current_phase ?? projectionData?.current_phase ?? null,
                phaseIndex: session.phase_index ?? 0,
                totalPhases: session.total_phases ?? 0,
                turnCount: session.turn_count ?? 0,
                messages: projectionData?.messages ?? session.messages ?? [],
                // Multimodal Null Safety: only set currentQuestion if server provides it
                currentQuestion: projectionData?.current_question ?? session.current_question ?? null,
                snapshot_hash: projectionData?.snapshot_hash ?? session.snapshot_hash ?? null,
            }

            setFromProjection(projection)   // Full deep-replace; unlocks isPullLocked
            setHydrated(true)
            ActionTrace.stateApplied(traceId, 'Step2:success')
        } catch (err) {
            const normalizedError = err.error_code ? err : {
                error_code: 'E_PULL_FAILED',
                trace_id: traceId,
                session_id: interviewId,
                event_seq: lastAppliedSeq || 'N/A',
                snapshot_hash: lastSnapshotHash || 'N/A',
                message: '세션 정보를 불러오지 못했습니다.',
            }
            pullFailed(normalizedError)  // → isSafeMode=true
        }
    }, [interviewId, beginPull, setFromProjection, pullFailed, hydrateFromSession,
        lastAppliedSeq, lastSnapshotHash, navigate])

    // ── Initial load & cleanup ─────────────────────────────────────────────
    useEffect(() => {
        performAuthorityPull()
        return () => {
            reset()
            resetSession()       // Reset capability freeze to defaults
            teardownWebRTC()
            if (abortControllerRef.current) {
                abortControllerRef.current.abort()
            }
        }
    }, [interviewId])  // eslint-disable-line react-hooks/exhaustive-deps

    // ── SSE Event Handler ─────────────────────────────────────────────────
    const handleSSEEvent = useCallback((data) => {
        // VIDEO-specific event types (ephemeral, never in projection store)
        if (data.type === 'stt_partial') {
            setSttPartial(data.text || '')
            return
        }
        if (data.type === 'stt_final_ack') {
            setSttPartial('')
            return
        }
        if (data.type === 'webrtc_state') {
            setWebrtcState(data.state || 'idle')
            return
        }

        // Projection event — applySSEEvent handles Pull Lock check + seq dedup
        const applied = useSessionStore.getState().applySSEEvent(data)
        if (applied) setHydrated(true)
    }, [])

    const { sseStatus, sseError } = useSSEProjection(interviewId, {
        isPullLocked,
        lastAppliedSeq,
        onAuthorityPull: performAuthorityPull,
        onEvent: handleSSEEvent,
        onStaleModeChange: setIsStaleBanner,
    })

    // ── Terminal: Tear down WebRTC immediately ─────────────────────────────
    useEffect(() => {
        if (isTerminal) {
            teardownWebRTC()
            setSttPartial('')
            // Cancel any pending mutation requests
            if (abortControllerRef.current) {
                abortControllerRef.current.abort()
                abortControllerRef.current = null
            }
        }
    }, [isTerminal, teardownWebRTC])

    // ── Capability gate: redirect to TEXT if not VIDEO mode ───────────────
    // Only redirect after hydration (not before Step 1 completes)
    useEffect(() => {
        if (hydrated && !video_enabled) {
            navigate(`/candidate/interview/${interviewId}`, { replace: true })
        }
    }, [hydrated, video_enabled, interviewId, navigate])

    // ── WebRTC Start (Capability Drift Freeze: only if snapshot says webrtc_enabled) ──
    const startWebRTC = useCallback(async () => {
        // Guard: snapshot-locked capability check (not live policy)
        if (!webrtc_enabled) return
        if (!canMutate) return          // Pull Lock / SAFE_MODE / Terminal
        if (webrtcState !== 'idle') return

        setWebrtcState('connecting')
        const traceId = createTraceId()
        ActionTrace.trigger(traceId, 'webrtc:start')

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
            localStreamRef.current = stream
            if (localVideoRef.current) localVideoRef.current.srcObject = stream

            const pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] })
            pcRef.current = pc
            stream.getTracks().forEach(t => pc.addTrack(t, stream))

            pc.ontrack = (event) => {
                if (remoteVideoRef.current && event.streams[0]) {
                    remoteVideoRef.current.srcObject = event.streams[0]
                }
            }

            const offer = await pc.createOffer()
            await pc.setLocalDescription(offer)

            // Wait for ICE gather (no Trickle ICE)
            await new Promise((resolve) => {
                if (pc.iceGatheringState === 'complete') { resolve(); return }
                pc.addEventListener('icegatheringstatechange', () => {
                    if (pc.iceGatheringState === 'complete') resolve()
                })
                setTimeout(resolve, 5000)
            })

            const res = await fetch(`${MULTIMODAL_BASE}/${interviewId}/multimodal/webrtc/offer`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-Trace-Id': traceId, ...getTokenHeader() },
                body: JSON.stringify({ sdp: pc.localDescription.sdp, type: pc.localDescription.type }),
            })

            if (res.status === 429) {
                // GPU 429: always visible/active (not gated); countdown banner shown
                // Auto-resend is FORBIDDEN; user must manually retry
                const errData = await res.json().catch(() => ({}))
                const retryAfter = res.headers.get('Retry-After')
                setGpuQueue({ trace_id: traceId, detail: errData.detail, retryAfter: retryAfter ? parseInt(retryAfter) : 30 })
                setWebrtcState('idle')
                teardownWebRTC()
                return
            }

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}))
                throw { error_code: errData.error_code || 'E_WEBRTC_FAILED', trace_id: traceId, message: `WebRTC 신호 실패: ${res.status}` }
            }

            const answer = await res.json()
            await pc.setRemoteDescription({ sdp: answer.sdp, type: answer.type })
            setWebrtcState('connected')
            ActionTrace.stateApplied(traceId, 'WebRTC:connected')

            pc.onconnectionstatechange = () => {
                if (pc.connectionState === 'failed' || pc.connectionState === 'closed') {
                    setWebrtcState('failed')
                } else if (pc.connectionState === 'connected') {
                    setWebrtcState('connected')
                }
            }
        } catch (err) {
            setWebrtcState('failed')
            setError({
                ...(err.error_code ? err : { error_code: 'E_WEBRTC_FAILED', trace_id: err.trace_id || traceId }),
                message: err.message || 'WebRTC 연결 실패', session_id: interviewId
            })
        }
    }, [interviewId, webrtc_enabled, canMutate, webrtcState, teardownWebRTC, setError])

    // Auto-start WebRTC only when: snapshot says webrtc_enabled, hydrated, canMutate, not terminal
    useEffect(() => {
        if (hydrated && webrtc_enabled && canMutate && webrtcState === 'idle') {
            startWebRTC()
        }
    }, [hydrated, webrtc_enabled, canMutate, webrtcState])  // eslint-disable-line react-hooks/exhaustive-deps

    // Auto-scroll
    useEffect(() => {
        chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages, sttPartial])

    // ── Loading: Step 1 in progress ───────────────────────────────────────
    if (isLoading && !hydrated) {
        return (
            <div style={styles.fullPage}>
                <div style={styles.centeredContent}>
                    <div style={styles.spinner} />
                    <p style={{ color: '#94a3b8', marginTop: 16 }}>VIDEO 면접 세션 로딩 중...</p>
                </div>
            </div>
        )
    }

    // ── SAFE_MODE: authority pull failed / offline ────────────────────────
    if (isSafeMode) {
        return (
            <div style={styles.fullPage}>
                <div style={styles.centeredContent}>
                    <div style={styles.safeModeBadge}>🔒 오프라인 – 읽기 전용</div>
                    <p style={{ color: '#94a3b8', marginTop: 12, textAlign: 'center', maxWidth: 360 }}>
                        서버와 연결이 끊겼습니다. 영상 입력이 비활성화됩니다.
                    </p>
                    {error && (
                        <p style={{ color: '#64748b', fontSize: 12, marginTop: 8, fontFamily: 'monospace' }}>
                            {error.error_code} · {error.trace_id || 'N/A'}
                        </p>
                    )}
                    {/* SAFE_MODE: navigation allowed */}
                    <button onClick={() => navigate('/')} style={styles.safeNavBtn}>홈으로 이동</button>
                </div>
            </div>
        )
    }

    return (
        <div style={styles.fullPage}>
            {/* GPU Queue Banner (always visible/active when 429; not capability-gated) */}
            {gpuQueue && (
                <GPUQueueBanner
                    errorData={gpuQueue}
                    onRetry={async () => {
                        setGpuQueue(null)
                        setWebrtcState('idle')
                        // Manual retry only (auto-resend forbidden)
                        // User clicked "retry" — startWebRTC fires from useEffect on webrtcState change
                    }}
                    onCancel={() => {
                        setGpuQueue(null)
                        navigate(-1)
                    }}
                />
            )}

            {/* Header */}
            <div style={styles.header}>
                <div>
                    <h1 style={styles.headerTitle}>🎬 {currentQuestion ? '면접 진행 중' : 'VIDEO 면접'}</h1>
                    <div style={styles.badges}>
                        <span style={{ ...styles.badge, background: 'rgba(239,68,68,0.15)', color: '#f87171', border: '1px solid rgba(239,68,68,0.3)' }}>
                            VIDEO 모드
                        </span>
                        {/* Blind Mode badge — only from snapshot capability */}
                        {blind_mode && (
                            <span style={{ ...styles.badge, background: 'rgba(168,85,247,0.15)', color: '#c084fc', border: '1px solid rgba(168,85,247,0.3)' }}>
                                🙈 블라인드 모드
                            </span>
                        )}
                        <span style={{ ...styles.badge, ...(sseStatus === SSE_STATUS.LIVE ? styles.sseLive : styles.sseStale) }}>
                            {sseStatus === SSE_STATUS.LIVE ? `● LIVE` : `● ${sseStatus}`}
                        </span>
                        <span style={{ ...styles.badge, background: webrtcState === 'connected' ? 'rgba(34,197,94,0.15)' : 'rgba(245,158,11,0.15)', color: webrtcState === 'connected' ? '#22c55e' : '#f59e0b', border: '1px solid transparent' }}>
                            WebRTC: {webrtcState}
                        </span>
                    </div>
                </div>
                <span style={styles.phaseBadge}>{currentPhase || '준비 중'}</span>
            </div>

            {/* STALE / Pull Lock banners */}
            {isStaleBanner && (
                <div style={styles.staleBanner}>📡 연결 불안정 – 재연결 중... (영상 입력 비활성화)</div>
            )}
            {isPullLocked && (
                <div style={styles.syncBanner}>🔄 최신 서버 상태 동기화 중...</div>
            )}

            {/* Error Banner (with observability tags) */}
            <ErrorBanner error={error || sseError} onDismiss={() => setError(null)} />

            {/* Main content */}
            <div style={styles.mainContent}>
                {/* Video panels — snapshot-locked capability gate (DOM removed if webrtc_enabled=false) */}
                {webrtc_enabled && (
                    <div style={styles.videoPanels}>
                        <div style={styles.videoPanel}>
                            <div style={styles.videoLabel}>나</div>
                            <video ref={localVideoRef} autoPlay muted playsInline style={styles.video} />
                        </div>
                        <div style={styles.videoPanel}>
                            <div style={styles.videoLabel}>면접관 (AI)</div>
                            <video ref={remoteVideoRef} autoPlay playsInline style={styles.video} />
                            {webrtcState !== 'connected' && (
                                <div style={styles.videoPlaceholder}>
                                    {webrtcState === 'connecting' ? '연결 중...' : 'AI 면접관 대기 중'}
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Question area */}
                <div style={styles.questionArea}>
                    {/* Initial Hydration Guard + Phase Transition Freeze:
                        question DOM only mounts when snapshot provides currentQuestion
                        Blind Mode: DOM removed entirely (not hidden) */}
                    {hydrated && currentQuestion && !blind_mode && (
                        <div style={styles.questionCard}>
                            <div style={styles.questionLabel}>면접 질문</div>
                            <div style={styles.questionText}>{currentQuestion}</div>
                        </div>
                    )}
                    {/* Blind Mode is active: aria-live also cleared */}
                    {blind_mode && (
                        <div aria-live="off" style={{ display: 'none' }} />
                    )}

                    {/* STT partial (ephemeral — never persisted, not from store) */}
                    {sttPartial && (
                        <div style={styles.sttCaption}>
                            <span style={{ fontSize: 16 }}>🎤</span>
                            <span style={{ color: '#f1f5f9', fontSize: 14, flex: 1 }}>{sttPartial}</span>
                            <span style={{ fontSize: 11, color: '#64748b', fontStyle: 'italic' }}>(실시간 자막 — 저장되지 않음)</span>
                        </div>
                    )}

                    {/* Terminal state — all mutation DOM REMOVED */}
                    {isTerminal && (
                        <div style={styles.completedArea}>
                            <div style={styles.completedBadge}>
                                {status === 'ABORTED' ? '🚫 면접 중단' : '✅ VIDEO 면접 완료'}
                            </div>
                            <p style={{ color: '#94a3b8', marginBottom: 16 }}>
                                {status === 'ABORTED' ? '면접이 중단되었습니다.' : '수고하셨습니다. 평가가 처리됩니다.'}
                            </p>
                            <button
                                id="view-result-btn-video"
                                onClick={() => navigate(`/candidate/result/${interviewId}`)}
                                style={styles.resultBtn}
                            >
                                결과 확인하기
                            </button>
                        </div>
                    )}

                    {/* Active: status area — no text submission (voice only in VIDEO mode) */}
                    {!isTerminal && hydrated && (
                        <div style={styles.statusArea}>
                            <p style={{ color: '#64748b', fontSize: 14 }}>
                                {webrtcState === 'connected'
                                    ? '🔴 녹화 중 — 음성으로 답변하세요.'
                                    : webrtcState === 'connecting'
                                        ? '카메라 및 마이크 연결 중...'
                                        : '영상 연결 대기 중...'}
                            </p>
                            {/* WebRTC failed: manual retry only */}
                            {webrtcState === 'failed' && canMutate && (
                                <button
                                    id="retry-webrtc-btn"
                                    onClick={() => setWebrtcState('idle')}
                                    style={styles.retryWebrtcBtn}
                                >
                                    WebRTC 수동 재연결
                                </button>
                            )}
                        </div>
                    )}

                    {/* No hydration yet */}
                    {!hydrated && !isSafeMode && (
                        <div style={{ textAlign: 'center', padding: '40px 0' }}>
                            <div style={styles.spinner} />
                            <p style={{ color: '#475569', marginTop: 12 }}>서버에서 면접 세션을 받아오는 중...</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}

const styles = {
    fullPage: {
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #0a0f1e 0%, #0f172a 100%)',
        display: 'flex',
        flexDirection: 'column',
    },
    centeredContent: {
        flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
    },
    spinner: {
        width: 44, height: 44,
        border: '4px solid rgba(239,68,68,0.2)', borderTopColor: '#ef4444',
        borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto',
    },
    safeModeBadge: {
        background: 'rgba(239,68,68,0.15)', border: '1px solid #ef4444',
        color: '#fca5a5', padding: '12px 24px', borderRadius: 8, fontWeight: 700, fontSize: 18,
    },
    safeNavBtn: {
        marginTop: 20, padding: '10px 28px',
        background: 'rgba(59,130,246,0.1)', border: '1px solid #3b82f6',
        borderRadius: 6, color: '#60a5fa', cursor: 'pointer', fontSize: 15,
    },
    staleBanner: {
        background: 'rgba(234,179,8,0.15)', border: '1px solid rgba(234,179,8,0.4)',
        color: '#fde047', padding: '8px 24px', fontSize: 13, textAlign: 'center',
    },
    syncBanner: {
        background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.3)',
        color: '#93c5fd', padding: '8px 24px', fontSize: 13, textAlign: 'center',
    },
    header: {
        padding: '16px 24px', borderBottom: '1px solid #1e293b',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        background: 'rgba(10,15,30,0.9)', backdropFilter: 'blur(12px)',
        position: 'sticky', top: 0, zIndex: 10,
    },
    headerTitle: { color: '#f1f5f9', fontSize: 18, fontWeight: 700, margin: '0 0 6px' },
    badges: { display: 'flex', gap: 8, flexWrap: 'wrap' },
    badge: { padding: '2px 10px', borderRadius: 99, fontSize: 12, fontWeight: 600 },
    sseLive: { color: '#22c55e', background: 'rgba(34,197,94,0.1)' },
    sseStale: { color: '#f59e0b', background: 'rgba(245,158,11,0.1)' },
    phaseBadge: {
        background: 'rgba(239,68,68,0.15)', color: '#f87171',
        padding: '4px 14px', borderRadius: 99, fontSize: 13,
        border: '1px solid rgba(239,68,68,0.3)', whiteSpace: 'nowrap',
    },
    mainContent: { flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' },
    videoPanels: { display: 'flex', gap: 12, padding: '16px 24px', background: '#000' },
    videoPanel: {
        flex: 1, position: 'relative', borderRadius: 12, overflow: 'hidden',
        background: '#0a0a0a', border: '1px solid #1e293b', minHeight: 200,
    },
    videoLabel: {
        position: 'absolute', top: 8, left: 8, zIndex: 2,
        background: 'rgba(0,0,0,0.6)', color: '#fff', padding: '2px 8px', borderRadius: 4, fontSize: 12,
    },
    video: { width: '100%', height: '100%', objectFit: 'cover', display: 'block' },
    videoPlaceholder: {
        position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
        justifyContent: 'center', color: '#64748b', fontSize: 14,
    },
    questionArea: { flex: 1, padding: '20px 24px', overflowY: 'auto' },
    questionCard: {
        background: '#1e293b', border: '1px solid #334155', borderRadius: 12, padding: 20, marginBottom: 16,
    },
    questionLabel: { fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 },
    questionText: { color: '#f1f5f9', fontSize: 16, fontWeight: 600, lineHeight: 1.6 },
    sttCaption: {
        background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
        borderRadius: 8, padding: '10px 16px', marginBottom: 16,
        display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
    },
    statusArea: { textAlign: 'center', padding: '32px 0' },
    retryWebrtcBtn: {
        marginTop: 12, padding: '10px 24px',
        background: 'rgba(245,158,11,0.1)', border: '1px solid #f59e0b',
        borderRadius: 8, color: '#f59e0b', cursor: 'pointer', fontSize: 14,
    },
    completedArea: { textAlign: 'center', padding: '32px' },
    completedBadge: { fontSize: 22, fontWeight: 700, color: '#22c55e', marginBottom: 8 },
    resultBtn: {
        padding: '12px 32px',
        background: 'linear-gradient(135deg, #1d4ed8, #4338ca)',
        border: 'none', borderRadius: 8, color: '#fff', fontWeight: 600, fontSize: 15, cursor: 'pointer',
    },
}
