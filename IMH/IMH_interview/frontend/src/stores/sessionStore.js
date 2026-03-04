/**
 * SessionStore / ProjectionStore (TASK-FRONT-001)
 *
 * Single source of truth for interview projection state.
 * Contracts:
 * - ONLY server projection updates this store (no local business logic)
 * - Pull Lock prevents SSE events and UI mutations during Authority Pull
 * - SAFE_MODE: all mutation DOM removed; only navigation to Home/New Session allowed
 * - No partial merge: Full deep-replace on every projection overwrite
 * - No optimistic updates
 * - Phase/Status are always server enum values
 * - lastAppliedSeq + lastSnapshotHash prevent duplicate SSE re-application
 */

import { create } from 'zustand'

const TERMINAL_STATUSES = new Set(['ABORTED', 'DECIDED', 'EVALUATED'])

const INITIAL_SESSION = {
    // ── Identity ─────────────────────────────────────────────────────────────
    sessionId: null,
    jobId: null,
    jobTitle: null,

    // ── Server enums ─────────────────────────────────────────────────────────
    status: null,       // IN_PROGRESS | COMPLETED | ABORTED | EVALUATED | DECIDED
    currentPhase: null, // Server-provided current phase label
    phaseIndex: 0,
    totalPhases: 0,
    turnCount: 0,

    // ── Projection data ───────────────────────────────────────────────────────
    messages: [],       // Full chat history (synced from server)
    currentQuestion: null, // Section 1 / Initial Hydration Guard: null until server provides
    result: null,       // Evaluation result (when available; ephemeral, not persisted)

    // ── SSE sequence tracking (Idempotent Apply Rule) ─────────────────────────
    lastAppliedSeq: 0,       // event_seq of last applied SSE event
    lastSnapshotHash: null,  // snapshot_hash of last overwrite (no re-render if same)

    // ── Authority Pull state machine ──────────────────────────────────────────
    isPullLocked: false,    // True during Authority Pull (Pull-In-Flight SSE suppression)
    isSafeMode: false,      // True when offline/pull-failed; mutations removed from DOM
    pullFailCount: 0,       // How many consecutive pull failures

    // ── UI-only flags (NOT business state) ───────────────────────────────────
    isLoading: false,
    local_pending: false,   // UI convenience flag: prevents double-click ONLY
    error: null,            // { error_code, trace_id, message, session_id?, event_seq?, snapshot_hash? }
    lastSyncedAt: null,
}

export const useSessionStore = create((set, get) => ({
    ...INITIAL_SESSION,

    // ─── Authority Pull: Begin (lock + kill mutations) ─────────────────────────
    // Called before Step 1 of the Authority Pull 2-Step Protocol.
    beginPull: () => set({
        isPullLocked: true,
        local_pending: false,   // Force clear — never true during pull
        isLoading: true,
        error: null,
    }),

    // ─── Authority Pull: Full Overwrite (no partial merge) ────────────────────
    // Called when Step 1+2 succeed. Deep-replaces entire store.
    // snapshot_hash check: skip overwrite if same hash (idempotent).
    setFromProjection: (projection) => {
        const currentHash = get().lastSnapshotHash
        const incomingHash = projection.snapshot_hash ?? null

        if (incomingHash && incomingHash === currentHash) {
            // Same snapshot — no re-render needed (SSE Idempotent Apply Rule)
            set({ isPullLocked: false, isLoading: false, isSafeMode: false, pullFailCount: 0 })
            return
        }

        // Full deep-replace — no merge
        set({
            ...INITIAL_SESSION,          // Reset all derived fields first
            ...projection,               // Overwrite with server authoritative data
            lastSnapshotHash: incomingHash,
            isPullLocked: false,
            isSafeMode: false,
            pullFailCount: 0,
            isLoading: false,
            local_pending: false,
            error: null,
            lastSyncedAt: new Date().toISOString(),
        })
    },

    // ─── Authority Pull: Failure → SAFE_MODE ──────────────────────────────────
    pullFailed: (error) => set((s) => ({
        isPullLocked: false,
        isSafeMode: true,
        isLoading: false,
        local_pending: false,
        pullFailCount: s.pullFailCount + 1,
        error: error || { error_code: 'E_PULL_FAILED', trace_id: null, message: 'Authority Pull 실패 – 오프라인 모드' },
    })),

    // ─── SSE Event Apply (with idempotent guard) ──────────────────────────────
    // Returns false if event was suppressed (pull locked, seq inversion, or duplicate hash).
    applySSEEvent: (data) => {
        const state = get()

        // 1. Pull Lock: suppress all SSE events during Authority Pull
        if (state.isPullLocked) return false

        // 2. Sequence inversion or already-seen event
        const receivedSeq = data.event_seq
        if (typeof receivedSeq === 'number' && receivedSeq <= state.lastAppliedSeq) {
            return false // Discard; caller should also handle authority pull if inverted
        }

        // 3. Same snapshot hash — no re-render
        const incomingHash = data.snapshot_hash ?? null
        if (incomingHash && incomingHash === state.lastSnapshotHash) {
            if (typeof receivedSeq === 'number') {
                set({ lastAppliedSeq: receivedSeq })
            }
            return false
        }

        // Apply: full overwrite from SSE projection (same contract as authority pull)
        set({
            ...INITIAL_SESSION,
            ...data,
            lastAppliedSeq: typeof receivedSeq === 'number' ? receivedSeq : state.lastAppliedSeq,
            lastSnapshotHash: incomingHash ?? state.lastSnapshotHash,
            isPullLocked: false,
            isSafeMode: false,
            isLoading: false,
            local_pending: false,
            error: null,
            lastSyncedAt: new Date().toISOString(),
        })

        // If SSE reports a terminal status: immediately ensure local_pending cleared
        if (TERMINAL_STATUSES.has(data.status)) {
            set({ local_pending: false })
        }

        return true
    },

    // ─── SAFE_MODE Exit (requires pull success + heartbeat restore) ────────────
    // exitSafeMode is called only by the authority pull success path (setFromProjection).
    // Direct SSE reconnection alone MUST NOT call this.

    // ─── UI flag: local_pending (double-click guard only) ────────────────────
    // Guard: never set true if terminal state or SAFE_MODE.
    setLocalPending: (value) => set((s) => {
        if (value && (s.isSafeMode || TERMINAL_STATUSES.has(s.status))) return {}
        return { local_pending: value }
    }),

    // ─── Error ───────────────────────────────────────────────────────────────
    setError: (error) => set({ error, isLoading: false, local_pending: false }),

    // ─── Loading ─────────────────────────────────────────────────────────────
    setLoading: (isLoading) => set({ isLoading }),

    // ─── Reset for session change / navigation away ──────────────────────────
    // session_id change must always call reset() before new pull.
    reset: () => set({ ...INITIAL_SESSION }),

    // ─── Convenience: is terminal? ────────────────────────────────────────────
    get isTerminal() { return TERMINAL_STATUSES.has(get().status) },

    // ─── Convenience: can mutate? ─────────────────────────────────────────────
    // All mutation DOM decisions should flow through this.
    get canMutate() {
        const s = get()
        return !s.isPullLocked && !s.isSafeMode && !TERMINAL_STATUSES.has(s.status)
    },
}))
