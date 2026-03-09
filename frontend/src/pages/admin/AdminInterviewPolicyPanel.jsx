/**
 * AdminInterviewPolicyPanel — Interview Policy Configuration UI
 *
 * Displays AI-Sensitive policy fields (Frozen at Publish).
 * When isLocked=true (PUBLISHED/CLOSED), all fields become read-only (disabled).
 *
 * Data Governance:
 * - AI Policy fields: total_question_limit, question_timeout_sec, evaluation_weights,
 *   persona, fixed_questions, wiring flags → ALL frozen at Publish
 * - Operational Metadata: location, headcount, deadline, tags → always editable
 */
import React from 'react'

const PERSONA_OPTIONS = [
    { value: 'professional', label: '전문적 (Professional) — 구조적, 공식적' },
    { value: 'friendly', label: '친근 (Friendly) — 따뜻하고 격려적' },
    { value: 'strict', label: '엄격 (Strict) — 정밀하고 도전적' },
]

export default function AdminInterviewPolicyPanel({ form, onChange, isLocked }) {
    // isLocked: status === 'PUBLISHED' || status === 'CLOSED'
    const lockTitle = isLocked
        ? '🔒 게시된 공고의 AI 정책 필드는 수정할 수 없습니다. (Policy Freeze)'
        : ''

    function handleWeightChange(key, value) {
        const prev = form.evaluation_weights || { job: 40, comm: 30, attitude: 30 }
        onChange({ target: { name: 'evaluation_weights', value: { ...prev, [key]: parseFloat(value) || 0 } } })
    }

    function handleFixedQAdd() {
        const prev = form.fixed_questions || []
        onChange({ target: { name: 'fixed_questions', value: [...prev, ''] } })
    }

    function handleFixedQChange(idx, value) {
        const prev = form.fixed_questions || []
        const updated = prev.map((q, i) => i === idx ? value : q)
        onChange({ target: { name: 'fixed_questions', value: updated } })
    }

    function handleFixedQRemove(idx) {
        const prev = form.fixed_questions || []
        onChange({ target: { name: 'fixed_questions', value: prev.filter((_, i) => i !== idx) } })
    }

    function handleToggle(name) {
        onChange({ target: { name, value: !form[name] } })
    }

    const weights = form.evaluation_weights || { job: 40, comm: 30, attitude: 30 }
    const fixedQs = form.fixed_questions || []

    return (
        <div style={{ borderTop: '1px solid var(--glass-border)', paddingTop: 24, marginTop: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-secondary)' }}>
                    🤖 AI 면접 정책 설정
                </div>
                {isLocked && (
                    <span style={{
                        fontSize: 11, padding: '2px 8px', borderRadius: 99,
                        background: 'rgba(239,68,68,0.12)', color: '#f87171',
                        border: '1px solid rgba(239,68,68,0.3)', fontWeight: 600,
                    }}>
                        🔒 정책 동결됨 (Freeze)
                    </span>
                )}
            </div>
            {isLocked && (
                <div style={{
                    background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)',
                    borderRadius: 8, padding: '10px 14px', marginBottom: 20,
                    fontSize: 13, color: '#fca5a5',
                }}>
                    ⚠️ {lockTitle}
                </div>
            )}

            {/* ── 질문 수 & 시간 ── */}
            <div className="form-row">
                <div className="form-group">
                    <label className="form-label">총 질문 수</label>
                    <input
                        name="total_question_limit"
                        className="form-input"
                        type="number" min="1" max="20"
                        value={form.total_question_limit ?? 10}
                        onChange={onChange}
                        disabled={isLocked}
                        title={lockTitle}
                    />
                </div>
                <div className="form-group">
                    <label className="form-label">답변 제한 시간 (초)</label>
                    <input
                        name="question_timeout_sec"
                        className="form-input"
                        type="number" min="30"
                        value={form.question_timeout_sec ?? 120}
                        onChange={onChange}
                        disabled={isLocked}
                        title={lockTitle}
                    />
                </div>
            </div>

            {/* ── 면접 모드 ── */}
            <div className="form-group">
                <label className="form-label">면접 모드</label>
                <select
                    name="mode"
                    className="form-select"
                    value={form.mode ?? 'ACTUAL'}
                    onChange={onChange}
                    disabled={isLocked}
                    title={lockTitle}
                >
                    <option value="ACTUAL">실전 (ACTUAL)</option>
                    <option value="PRACTICE">연습 (PRACTICE)</option>
                </select>
            </div>

            {/* ── 면접관 페르소나 ── */}
            <div className="form-group">
                <label className="form-label">면접관 페르소나</label>
                <select
                    name="persona"
                    className="form-select"
                    value={form.persona ?? 'professional'}
                    onChange={onChange}
                    disabled={isLocked}
                    title={lockTitle}
                >
                    {PERSONA_OPTIONS.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                </select>
            </div>

            {/* ── 역량 가중치 ── */}
            <div style={{ marginBottom: 20 }}>
                <label className="form-label" style={{ marginBottom: 10, display: 'block' }}>
                    역량 평가 가중치
                    <span style={{ fontSize: 11, color: 'var(--text-secondary)', marginLeft: 6 }}>
                        (합계 = {(weights.job || 0) + (weights.comm || 0) + (weights.attitude || 0)}%)
                    </span>
                </label>
                <div className="form-row">
                    {[
                        { key: 'job', label: '직무역량' },
                        { key: 'comm', label: '의사소통' },
                        { key: 'attitude', label: '태도' },
                    ].map(({ key, label }) => (
                        <div key={key} className="form-group">
                            <label className="form-label" style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                                {label} (%)
                            </label>
                            <input
                                className="form-input"
                                type="number" min="0" max="100"
                                value={weights[key] ?? 0}
                                onChange={e => handleWeightChange(key, e.target.value)}
                                disabled={isLocked}
                                title={lockTitle}
                            />
                        </div>
                    ))}
                </div>
            </div>

            {/* ── 고정 질문 ── */}
            <div style={{ marginBottom: 20 }}>
                <label className="form-label" style={{ marginBottom: 10, display: 'block' }}>
                    고정 질문 목록 (always injected)
                </label>
                {fixedQs.length === 0 ? (
                    <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '0 0 8px' }}>
                        등록된 고정 질문이 없습니다.
                    </p>
                ) : (
                    <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 8px' }}>
                        {fixedQs.map((q, i) => (
                            <li key={i} style={{
                                display: 'flex', alignItems: 'flex-start', gap: 8,
                                padding: '6px 10px', background: 'rgba(255,255,255,0.04)',
                                borderRadius: 6, marginBottom: 4, fontSize: 13,
                            }}>
                                <span style={{ color: 'var(--text-secondary)', minWidth: 20 }}>{i + 1}.</span>
                                <input
                                    className="form-input"
                                    style={{ flex: 1, fontSize: 13, padding: '4px 8px' }}
                                    value={q}
                                    onChange={e => handleFixedQChange(i, e.target.value)}
                                    placeholder="고정 질문을 입력하세요"
                                    disabled={isLocked}
                                />
                                {!isLocked && (
                                    <button
                                        type="button"
                                        onClick={() => handleFixedQRemove(i)}
                                        style={{
                                            background: 'none', border: 'none',
                                            color: '#f87171', cursor: 'pointer', fontSize: 14, padding: 0,
                                        }}
                                    >✕</button>
                                )}
                            </li>
                        ))}
                    </ul>
                )}
                {!isLocked && (
                    <button
                        type="button"
                        onClick={handleFixedQAdd}
                        className="btn btn-secondary"
                        style={{ fontSize: 13, padding: '6px 14px' }}
                    >
                        + 고정 질문 추가
                    </button>
                )}
            </div>

            {/* ── Wiring Flags ── */}
            <div style={{ marginBottom: 8 }}>
                <label className="form-label" style={{ marginBottom: 12, display: 'block' }}>
                    기능 활성화 설정 (Wiring Flags)
                </label>
                {[
                    { key: 'wiring_resume_q_enabled', label: '이력서 기반 질문 생성', icon: '📄' },
                    { key: 'wiring_rag_enabled', label: 'RAG 질문은행 검색', icon: '🔍' },
                    { key: 'wiring_multimodal_enabled', label: '멀티모달 분석 (STT, 표정, 시선)', icon: '🎥' },
                ].map(({ key, label, icon }) => (
                    <div key={key} style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '10px 14px', background: 'rgba(255,255,255,0.04)',
                        borderRadius: 8, marginBottom: 8,
                    }}>
                        <span style={{ fontSize: 14, color: 'var(--text-primary)' }}>
                            {icon} {label}
                        </span>
                        <label style={{ position: 'relative', display: 'inline-block', width: 44, height: 24 }}>
                            <input
                                type="checkbox"
                                checked={form[key] !== false}
                                onChange={() => !isLocked && handleToggle(key)}
                                disabled={isLocked}
                                style={{ opacity: 0, width: 0, height: 0 }}
                            />
                            <span style={{
                                position: 'absolute', cursor: isLocked ? 'not-allowed' : 'pointer',
                                top: 0, left: 0, right: 0, bottom: 0,
                                background: form[key] !== false ? '#22c55e' : '#475569',
                                borderRadius: 999, transition: 'background 0.2s',
                            }}>
                                <span style={{
                                    position: 'absolute', height: 18, width: 18,
                                    left: form[key] !== false ? 22 : 3, bottom: 3,
                                    background: '#fff', borderRadius: '50%', transition: 'left 0.2s',
                                }} />
                            </span>
                        </label>
                    </div>
                ))}
            </div>
        </div>
    )
}
