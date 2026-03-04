/**
 * AdminAuditTimeline — Slice D: Admin Audit Timeline (TASK-FRONT-001)
 *
 * Contracts enforced:
 * - Admin Authority Boundary: this component is ONLY rendered in adminOnly routes
 * - Authority Pull: fresh fetch on every mount; no candidate store reuse
 * - No optimistic update; no auto-retry
 * - Error format: RAW error_code + trace_id
 * - Observability: Copy for Support included
 * - Admin-only fields (evaluation_input_hash, audit_link) shown only here
 */

import React, { useState, useEffect, useCallback, useRef } from 'react'
import { createTraceId } from '../../lib/traceId'

function getTokenHeader() {
    return { Authorization: `Bearer ${localStorage.getItem('imh_token')}` }
}

function buildSupportPayload({ sessionId, traceId, snapshotHash }) {
    return [
        `session_id: ${sessionId || 'N/A'}`,
        `trace_id: ${traceId || 'N/A'}`,
        `snapshot_hash: ${snapshotHash || 'N/A'}`,
    ].join('\n')
}

export default function AdminAuditTimeline({ sessionId }) {
    const [events, setEvents] = useState([])
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState(null)
    const [filter, setFilter] = useState('')
    const [copiedId, setCopiedId] = useState(null)
    const traceIdRef = useRef(null)

    const fetchAudit = useCallback(async () => {
        const traceId = createTraceId()
        traceIdRef.current = traceId
        setIsLoading(true)
        setError(null)

        try {
            const res = await fetch(`/api/v1/interviews/${sessionId}/audit`, {
                headers: { ...getTokenHeader() },
            })
            if (!res.ok) {
                const errData = await res.json().catch(() => ({}))
                throw { error_code: errData.error_code || 'E_AUDIT_FETCH', trace_id: traceId, status: res.status }
            }
            const data = await res.json()
            // Sort chronologically (ascending)
            const sorted = (data.events ?? data ?? []).sort((a, b) =>
                new Date(a.timestamp) - new Date(b.timestamp)
            )
            setEvents(sorted)
        } catch (err) {
            setError(err.error_code
                ? err
                : { error_code: 'E_AUDIT_FETCH', trace_id: traceId, message: 'Audit 로그를 불러오지 못했습니다.' })
        } finally {
            setIsLoading(false)
        }
    }, [sessionId])

    useEffect(() => { fetchAudit() }, [fetchAudit])

    const filteredEvents = filter
        ? events.filter(e =>
            (e.trace_id || '').toLowerCase().includes(filter.toLowerCase()) ||
            (e.action || e.event_type || '').toLowerCase().includes(filter.toLowerCase()) ||
            (e.actor || e.admin_id || '').toLowerCase().includes(filter.toLowerCase())
        )
        : events

    const copyTraceId = (traceId) => {
        navigator.clipboard?.writeText(traceId ?? '').then(() => {
            setCopiedId(traceId)
            setTimeout(() => setCopiedId(null), 1500)
        })
    }

    const copySupport = () => {
        navigator.clipboard?.writeText(buildSupportPayload({ sessionId, traceId: traceIdRef.current }))
    }

    if (isLoading) return (
        <div style={s.container}>
            <div style={s.spinner} />
            <p style={{ color: '#64748b', marginTop: 12, fontSize: 13 }}>Audit 로그 로딩 중...</p>
        </div>
    )

    if (error) return (
        <div style={s.errorBox}>
            <p style={{ fontFamily: 'monospace', color: '#f87171', fontSize: 13 }}>
                {error.error_code} · {error.trace_id || 'N/A'}
            </p>
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button onClick={fetchAudit} style={s.smallBtn}>재시도</button>
                <button onClick={copySupport} style={s.smallBtnGhost}>Copy for Support</button>
            </div>
        </div>
    )

    return (
        <div>
            {/* Filter */}
            <div style={s.filterRow}>
                <input
                    id="audit-filter-input"
                    type="text"
                    value={filter}
                    onChange={e => setFilter(e.target.value)}
                    placeholder="trace_id / action / actor 검색..."
                    style={s.filterInput}
                />
                <button onClick={fetchAudit} style={s.smallBtn}>새로고침</button>
                <button onClick={copySupport} style={s.smallBtnGhost}>Copy for Support</button>
            </div>

            {filteredEvents.length === 0 ? (
                <p style={{ color: '#475569', fontSize: 13, padding: '16px 0' }}>이벤트가 없습니다.</p>
            ) : (
                <div style={s.timeline}>
                    {filteredEvents.map((ev, idx) => (
                        <div key={ev.trace_id || idx} style={s.row}>
                            <div style={s.rowDot} />
                            <div style={s.rowContent}>
                                <div style={s.rowTop}>
                                    <span style={s.actionTag}>{ev.action || ev.event_type || '?'}</span>
                                    {ev.actor && <span style={s.actor}>{ev.actor || ev.admin_id}</span>}
                                    <span style={s.ts}>{new Date(ev.timestamp).toLocaleString('ko-KR')}</span>
                                </div>
                                {ev.trace_id && (
                                    <div style={s.traceRow}>
                                        <code style={s.traceCode}>{ev.trace_id}</code>
                                        <button
                                            onClick={() => copyTraceId(ev.trace_id)}
                                            style={s.tinyBtn}
                                            title="trace_id 복사"
                                        >
                                            {copiedId === ev.trace_id ? '✓' : '복사'}
                                        </button>
                                    </div>
                                )}
                                {/* Payload summary (no raw dump) */}
                                {ev.payload_summary && (
                                    <p style={s.payloadSummary}>{String(ev.payload_summary).slice(0, 200)}</p>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}

const s = {
    container: { display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '32px 0' },
    spinner: {
        width: 32, height: 32,
        border: '3px solid rgba(99,102,241,0.2)', borderTopColor: '#6366f1',
        borderRadius: '50%', animation: 'spin 0.8s linear infinite',
    },
    errorBox: {
        background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)',
        borderRadius: 8, padding: 16, margin: '12px 0',
    },
    filterRow: { display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' },
    filterInput: {
        flex: 1, minWidth: 200, padding: '7px 12px',
        background: '#1e293b', border: '1px solid #334155',
        borderRadius: 6, color: '#f1f5f9', fontSize: 13, outline: 'none',
    },
    smallBtn: {
        padding: '6px 14px', background: 'rgba(99,102,241,0.15)',
        border: '1px solid rgba(99,102,241,0.3)', borderRadius: 6,
        color: '#a5b4fc', cursor: 'pointer', fontSize: 12,
    },
    smallBtnGhost: {
        padding: '6px 14px', background: 'transparent',
        border: '1px solid #334155', borderRadius: 6,
        color: '#64748b', cursor: 'pointer', fontSize: 12,
    },
    timeline: { display: 'flex', flexDirection: 'column', gap: 0 },
    row: { display: 'flex', gap: 12, position: 'relative', paddingBottom: 16 },
    rowDot: {
        width: 10, height: 10, borderRadius: '50%',
        background: '#6366f1', marginTop: 4, flexShrink: 0,
    },
    rowContent: { flex: 1, background: '#1e293b', border: '1px solid #334155', borderRadius: 8, padding: '10px 14px' },
    rowTop: { display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 6 },
    actionTag: {
        background: 'rgba(99,102,241,0.15)', color: '#a5b4fc',
        padding: '1px 8px', borderRadius: 99, fontSize: 12, fontWeight: 600,
    },
    actor: { color: '#94a3b8', fontSize: 12 },
    ts: { color: '#475569', fontSize: 11, marginLeft: 'auto' },
    traceRow: { display: 'flex', alignItems: 'center', gap: 6 },
    traceCode: { fontSize: 11, color: '#64748b', fontFamily: 'monospace', wordBreak: 'break-all' },
    tinyBtn: {
        padding: '1px 6px', background: 'transparent', border: '1px solid #334155',
        borderRadius: 4, color: '#64748b', cursor: 'pointer', fontSize: 10,
    },
    payloadSummary: { color: '#64748b', fontSize: 12, marginTop: 4, fontStyle: 'italic' },
}
