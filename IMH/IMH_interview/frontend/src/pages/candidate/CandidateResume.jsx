import React, { useEffect, useState, useRef } from 'react'
import { resumeApi } from '../../services/api'
import { ERROR_CODES, getErrorMessage } from '../../lib/errorCodes'

// Phase 2-2: client-side MIME + size pre-validation
const ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.txt']
const MAX_FILE_SIZE_MB = 5
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

function validateFile(file) {
    const ext = '.' + file.name.split('.').pop().toLowerCase()
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
        return { ok: false, code: ERROR_CODES.E_MIME_REJECTED }
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
        return { ok: false, code: ERROR_CODES.E_FILE_TOO_LARGE }
    }
    return { ok: true }
}

export default function CandidateResume() {
    const [resume, setResume] = useState(null)
    const [loading, setLoading] = useState(true)
    const [uploading, setUploading] = useState(false)
    const [success, setSuccess] = useState('')
    const [error, setError] = useState('')
    const [parseStatus, setParseStatus] = useState(null)  // Phase 2-2: track parse_status
    const fileRef = useRef()

    useEffect(() => {
        resumeApi.get()
            .then(res => {
                setResume(res.data)
                setParseStatus(res.data.parse_status)
            })
            .catch(() => setResume(null))
            .finally(() => setLoading(false))
    }, [])

    async function handleUpload(e) {
        const file = e.target.files?.[0]
        if (!file) return

        // Phase 2-2: Client-side pre-validation (server also validates)
        const validation = validateFile(file)
        if (!validation.ok) {
            setError(getErrorMessage(validation.code))
            setSuccess('')
            return
        }

        setUploading(true)
        setError('')
        setSuccess('')
        try {
            const formData = new FormData()
            formData.append('file', file)
            const uploadRes = await resumeApi.upload(formData)
            const newParseStatus = uploadRes.data?.parse_status || 'PARSED'
            setParseStatus(newParseStatus)

            const res = await resumeApi.get()
            setResume(res.data)

            if (newParseStatus === 'FAILED') {
                setSuccess('이력서가 업로드되었습니다. (내용 분석은 실패했지만 면접 진행은 가능합니다.)')
            } else {
                setSuccess('이력서가 성공적으로 업로드되었습니다.')
            }
        } catch (err) {
            // Phase 2-2: Show server error_code–based message
            const errorCode = err.error_code || err.response?.headers?.['x-error-code']
            if (errorCode) {
                setError(getErrorMessage(errorCode))
            } else {
                setError(err.response?.data?.detail || '업로드 중 오류가 발생했습니다.')
            }
        } finally {
            setUploading(false)
        }
    }

    function formatSize(bytes) {
        if (!bytes) return ''
        if (bytes < 1024) return `${bytes}B`
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
        return `${(bytes / 1024 / 1024).toFixed(1)}MB`
    }

    return (
        <div>
            <div className="page-header">
                <h1 className="page-title">이력서 관리</h1>
                <p className="page-subtitle">면접 전 이력서를 업로드해 주세요. PDF, DOC, DOCX, TXT 파일 지원 (최대 {MAX_FILE_SIZE_MB}MB).</p>
            </div>

            <div style={{ maxWidth: 560 }}>
                {error && <div className="alert alert-error">{error}</div>}
                {success && <div className="alert alert-success">{success}</div>}

                {/* Upload area */}
                <div
                    className="card"
                    style={{
                        textAlign: 'center',
                        padding: '48px 24px',
                        border: '2px dashed var(--glass-border)',
                        cursor: uploading ? 'not-allowed' : 'pointer',
                        marginBottom: 24,
                        opacity: uploading ? 0.6 : 1,
                    }}
                    onClick={() => !uploading && fileRef.current?.click()}
                >
                    <div style={{ fontSize: 48, marginBottom: 12 }}>📄</div>
                    <div style={{ fontWeight: 600, marginBottom: 8 }}>
                        {uploading ? '업로드 중...' : '클릭하여 이력서 업로드'}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                        PDF, DOC, DOCX, TXT • 최대 {MAX_FILE_SIZE_MB}MB
                    </div>
                    <input
                        ref={fileRef}
                        type="file"
                        accept=".pdf,.doc,.docx,.txt"
                        style={{ display: 'none' }}
                        onChange={handleUpload}
                    />
                </div>

                {/* Current resume */}
                {loading ? (
                    <div className="loading"><div className="spinner" /></div>
                ) : resume ? (
                    <div className="card">
                        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                            현재 등록된 이력서
                        </div>
                        <div className="flex items-center gap-4">
                            <div style={{ fontSize: 32 }}>📎</div>
                            <div style={{ flex: 1 }}>
                                <div style={{ fontWeight: 600 }}>{resume.file_name}</div>
                                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                                    {formatSize(resume.file_size)} • {new Date(resume.uploaded_at).toLocaleDateString('ko-KR')}
                                </div>
                            </div>
                            <span className="badge badge-published">등록됨</span>
                            {/* Phase 2-2: Parse failure badge */}
                            {(parseStatus === 'FAILED' || resume.parse_status === 'FAILED') && (
                                <span
                                    className="badge"
                                    style={{ background: 'rgba(255,152,0,0.2)', color: '#ff9800', border: '1px solid rgba(255,152,0,0.4)' }}
                                    title="이력서 내용 분석에 실패했습니다. 면접은 정상 진행됩니다."
                                >
                                    ⚠ 분석 실패
                                </span>
                            )}
                        </div>
                    </div>
                ) : (
                    <div className="empty-state" style={{ padding: '32px' }}>
                        <p>등록된 이력서가 없습니다. 위에서 업로드해 주세요.</p>
                    </div>
                )}
            </div>
        </div>
    )
}
