import React, { useState, useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

export default function DeviceCheck() {
    const navigate = useNavigate()
    const [searchParams] = useSearchParams()
    const sessionId = searchParams.get('sessionId')
    const videoRef = useRef()

    const [checks, setChecks] = useState({
        camera: 'testing',
        mic: 'testing',
        network: 'testing',
    })
    const [stream, setStream] = useState(null)
    const [allOk, setAllOk] = useState(false)

    useEffect(() => {
        let mediaStream = null

        async function runChecks() {
            // Network check
            const networkOk = navigator.onLine
            setChecks(c => ({ ...c, network: networkOk ? 'ok' : 'error' }))

            // Camera + mic check
            try {
                mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
                setStream(mediaStream)
                if (videoRef.current) {
                    videoRef.current.srcObject = mediaStream
                }
                setChecks(c => ({ ...c, camera: 'ok', mic: 'ok' }))
            } catch {
                setChecks(c => ({ ...c, camera: 'error', mic: 'error' }))
            }
        }

        runChecks()

        return () => {
            if (mediaStream) {
                mediaStream.getTracks().forEach(t => t.stop())
            }
        }
    }, [])

    useEffect(() => {
        const ok = Object.values(checks).every(v => v === 'ok')
        setAllOk(ok)
    }, [checks])

    function handleStart() {
        // Stop media stream before navigating
        if (stream) {
            stream.getTracks().forEach(t => t.stop())
        }
        if (sessionId) {
            navigate(`/candidate/interview/${sessionId}`)
        } else {
            navigate('/candidate/postings')
        }
    }

    const deviceLabels = {
        camera: { label: '카메라', icon: '📷' },
        mic: { label: '마이크', icon: '🎤' },
        network: { label: '네트워크', icon: '🌐' },
    }

    const statusText = {
        testing: { label: '점검 중...', cls: 'testing' },
        ok: { label: '정상', cls: 'ok' },
        error: { label: '오류', cls: 'error' },
    }

    return (
        <div>
            <div className="page-header" style={{ textAlign: 'center', marginBottom: 40 }}>
                <h1 className="page-title">환경 테스트</h1>
                <p className="page-subtitle">면접 시작 전 카메라, 마이크, 네트워크 상태를 확인합니다.</p>
            </div>

            <div style={{ maxWidth: 700, margin: '0 auto' }}>
                <div className="device-check-grid">
                    {Object.entries(deviceLabels).map(([key, { label, icon }]) => {
                        const { label: statusLabel, cls } = statusText[checks[key]]
                        return (
                            <div key={key} className={`device-item ${cls}`}>
                                <div className="device-icon">{icon}</div>
                                <div className="device-name">{label}</div>
                                <div className={`device-status ${cls}`}>{statusLabel}</div>
                            </div>
                        )
                    })}
                </div>

                {/* Camera preview */}
                <div className="card" style={{ marginBottom: 24 }}>
                    <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12 }}>카메라 미리보기</div>
                    <div style={{
                        width: '100%', maxWidth: 480, margin: '0 auto',
                        aspectRatio: '16/9', background: 'var(--bg-secondary)',
                        borderRadius: 'var(--radius)', overflow: 'hidden',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                        {checks.camera === 'ok' ? (
                            <video
                                ref={videoRef}
                                autoPlay
                                muted
                                style={{ width: '100%', height: '100%', objectFit: 'cover', transform: 'scaleX(-1)' }}
                            />
                        ) : (
                            <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>
                                {checks.camera === 'testing' ? '카메라 연결 중...' : '카메라를 사용할 수 없습니다.'}
                            </div>
                        )}
                    </div>
                </div>

                <div className="alert alert-info" style={{ marginBottom: 24 }}>
                    💡 면접 중에는 카메라를 통해 표정과 시선이 기록됩니다. 적절한 조명과 조용한 환경을 준비해 주세요.
                </div>

                <button
                    className="btn btn-primary btn-full"
                    disabled={!allOk}
                    onClick={handleStart}
                    style={{ padding: '16px' }}
                >
                    {allOk ? '✅ 환경 확인 완료 – 면접 시작' : '⏳ 환경 확인 중...'}
                </button>

                {!allOk && checks.camera === 'error' && (
                    <div className="alert alert-error" style={{ marginTop: 12 }}>
                        카메라/마이크 접근 권한을 허용해 주세요. 브라우저 설정에서 허용 후 페이지를 새로고침하세요.
                    </div>
                )}
            </div>
        </div>
    )
}
