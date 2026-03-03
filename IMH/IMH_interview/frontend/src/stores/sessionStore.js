/**
 * SessionStore / ProjectionStore (Sections B, 27 - FRONT-TASK-01)
 *
 * This is the ProjectionStore - the single source of truth for interview state.
 * Rules:
 * - Only server responses update this store (no local business logic)
 * - Re-entry to a session forces a full authority pull and overwrites this store
 * - No optimistic updates
 * - Phase/Status are always server enum values
 */

import { create } from 'zustand'

const INITIAL_SESSION = {
    sessionId: null,
    jobId: null,
    jobTitle: null,
    status: null,          // IN_PROGRESS | COMPLETED | ABORTED | EVALUATED
    currentPhase: null,    // Server-provided current phase label
    phaseIndex: 0,
    totalPhases: 0,
    turnCount: 0,
    messages: [],          // Full chat history (synced from server)
    result: null,          // Evaluation result (when available)
    isLoading: false,
    isPendingMutation: false, // Section 42: Rapid click guard
    error: null,           // { error_code, trace_id, message }
    lastSyncedAt: null,
}

export const useSessionStore = create((set, get) => ({
    ...INITIAL_SESSION,

    // ─── Authority Pull: Full overwrite from server (Section 27) ─────────────
    setFromProjection: (projection) => {
        set({
            ...projection,
            lastSyncedAt: new Date().toISOString(),
            error: null,
            isLoading: false,
        })
    },

    // ─── Set loading state ────────────────────────────────────────────────────
    setLoading: (isLoading) => set({ isLoading }),

    // ─── Section 42: Mutation pending state (rapid click guard) ───────────────
    setPendingMutation: (isPendingMutation) => set({ isPendingMutation }),

    // ─── Set error ──────────────────────────────────────────────────────────
    setError: (error) => set({ error, isLoading: false, isPendingMutation: false }),

    // ─── Append a message to the local message list ───────────────────────────
    // NOTE: This is only used for optimistic UI display of user-submitted answers
    // before the server projection overwrite arrives. No business state is derived.
    appendMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),

    // ─── Set result (read-only after COMPLETED, Section 39/63) ───────────────
    setResult: (result) => set({ result }),

    // ─── Full reset for when user navigates away ─────────────────────────────
    reset: () => set(INITIAL_SESSION),
}))
