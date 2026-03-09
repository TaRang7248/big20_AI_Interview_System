/**
 * CapabilityStore (Sections 2.4, 34, 80 - FRONT-TASK-01)
 *
 * Controls which features are visible/enabled.
 * Rules:
 * - Features with flag=false are REMOVED from the DOM (not just disabled)
 * - MVP scope: VIDEO_MODE disabled by default (Section 78, 80)
 * - Loaded at app boot from /api/v1/config/capabilities (or MVP defaults)
 */

import { create } from 'zustand'

// MVP Default Capabilities (Section 78, 80: TEXT-only initial deployment)
const MVP_DEFAULTS = {
    TEXT_MODE: true,
    VIDEO_MODE: false,      // Phase 3 – disabled until post-MVP approval
    BLIND_MODE: false,      // Phase 3 – requires VIDEO stable first
    PRACTICE_MODE: true,    // Enabled after 1-week internal soak
    ADMIN_STATS: true,      // Enabled after PG validation
    MULTIMODAL: false,      // Phase 3
    DEBUG_PANEL: false,     // Dev-only toggle (Section 67)
}

// Phase 3: Session-level VIDEO capability state (from policy_snapshot)
const VIDEO_DEFAULTS = {
    interview_mode: 'TEXT',          // TEXT | VIDEO — from server policy_snapshot
    video_enabled: false,
    webrtc_enabled: false,
    tts_enabled: false,
    blind_mode: false,               // ai_question_text_visible === false
    ai_question_text_visible: true,
}

export const useCapabilityStore = create((set, get) => ({
    capabilities: { ...MVP_DEFAULTS },
    isLoaded: false,
    loadError: null,
    // Phase 3: session-level video caps
    ...VIDEO_DEFAULTS,

    // Check if a feature/capability is enabled
    isEnabled: (featureKey) => {
        return get().capabilities[featureKey] === true
    },

    // Set capabilities from server response
    setCapabilities: (caps) => {
        set({ capabilities: { ...MVP_DEFAULTS, ...caps }, isLoaded: true, loadError: null })
    },

    // Fall back to MVP defaults on load error
    setDefaults: () => {
        set({ capabilities: { ...MVP_DEFAULTS }, isLoaded: true, loadError: 'LOAD_FAILED_USE_DEFAULTS' })
    },

    /**
     * Phase 3: Hydrate session-level video caps from server policy_snapshot.
     * Called once on session authority pull. Source: server only.
     * DOM removal (not hidden) for video components when video_enabled=false.
     */
    hydrateFromSession: (sessionData) => {
        const mode = sessionData?.interview_mode || sessionData?.mode || 'TEXT'
        const textVisible = sessionData?.ai_question_text_visible ?? true
        const isVideo = mode === 'VIDEO'
        set({
            interview_mode: mode,
            video_enabled: isVideo,
            webrtc_enabled: isVideo,
            tts_enabled: isVideo,
            blind_mode: isVideo && !textVisible,
            ai_question_text_visible: textVisible,
            capabilities: {
                ...get().capabilities,
                VIDEO_MODE: isVideo,
                BLIND_MODE: isVideo && !textVisible,
                MULTIMODAL: isVideo,
            },
        })
    },

    /** Reset session-level caps on teardown */
    resetSession: () => set({ ...VIDEO_DEFAULTS }),
}))

