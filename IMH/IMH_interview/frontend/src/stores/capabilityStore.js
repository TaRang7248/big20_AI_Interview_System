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

export const useCapabilityStore = create((set, get) => ({
    capabilities: { ...MVP_DEFAULTS },
    isLoaded: false,
    loadError: null,

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
}))
