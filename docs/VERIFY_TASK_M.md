# TASK-M Multimodal Integration Verification Guide (VERIFY_TASK_M)

본 문서에는 **TASK-M (Multimodal Integration MVP)** 구현 사항에 대해 프론트엔드 연동 없이도 동작을 재현하고 검수할 수 있는 상세 절차와 시나리오를 기술합니다.

## 1. 전제 조건 및 환경 설정

*   **Python 환경**: `aiortc`, `requests`, `aiohttp`, `pypdf`, `gTTS` 라이브러리가 설치된 환경
*   **서버 실행**: `python IMH/main.py`가 로컬 8000번 포트에서 실행 중이어야 함
*   **Redis 및 PostgreSQL**: 활성화 상태 확인
*   **Feature Flags (.env)**: 검수를 위해 아래 플래그들이 `true`로 설정되어야 함
    ```bash
    MM_ENABLE=true
    MM_ENABLE_WEBRTC=true
    MM_ENABLE_TTS=true
    MM_ENABLE_PDF_TEXT=true
    ```
*   **테스트 세션**: 검수용 `session_id`가 `interviews` 테이블에 존재해야 함 (기존 세션 사용 가능)

---

## 2. 검수 시나리오 (V1 ~ V6)

| ID | 시나리오 명 | 검수 내용 (Pass 조건) |
| :--- | :--- | :--- |
| **V1** | WebRTC Concurrency & Lifecycle | 10회 연속 연결/해제 수행 시 세션 카운트(`ACTIVE_SESSIONS_COUNT`)가 정상 복구되며 메모리 누수나 소켓 고아 현상이 없음 |
| **V2** | Audio Stream & STT | 오디오 데이터 송신 후 1초 내에 `stt_partial` 프로젝션 갱신 확인 및 턴 종료 시 `stt_confidence`가 DB에 확정 기록됨 |
| **V3** | Video Stream & Gaze | 비디오 프레임 송신 시 `gaze_horizontal`, `gaze_vertical` 메트릭이 2~3FPS 주기로 프로젝션에 업데이트됨 |
| **V4** | GPU Mutex & Resilience | LLM이 GPU Mutex를 점유 중일 때 STT가 Cooperative Yield로 대기하며, 점유 해제 후 처리가 재개됨을 로그로 확인 |
| **V5** | gTTS Cache & Response | `turn_index`별로 고유 MP3가 반환되며, 동일 텍스트 요청 시 `cache_hit` 로그가 발생하고 중복 생성이 차단됨 |
| **V6** | PDF->Text Snapshot | Resume PDF 업로드 시 텍스트가 추출되어 `session_config_snapshot`의 `resume_text` 필드에 동기화됨 (Log 확인) |

---

## 3. 검수 도구: CLI Multimodal Client

`scripts/verify_mm_cli.py` 도구를 사용하여 CLI 환경에서 즉시 검수가 가능합니다.

### 실행 방법
```bash
# 기본 세션에 대해 검수 실행
python scripts/verify_mm_cli.py --session_id <SESSION_UUID> --run-all
```

### 도구 주요 기능
*   **--webrtc**: SDP Offer 생성 및 WebRTC 협상 완료 (V1 대응)
*   **--audio <file>**: 오디오 스트리밍 송출 및 STT 갱신 모니터링 (V2 대응)
*   **--video <file>**: 비디오 스트리밍 송출 및 Gaze 업데이트 확인 (V3 대응)
*   **--tts**: gTTS 엔드포인트 호출 및 캐시 적중률 확인 (V5 대응)
*   **--pdf <file>**: PDF 텍스트 추출 기능 검증 (V6 대응)

---

## 4. 프론트엔드 연동 계약 (Checklist)

| 엔드포인트 | Method | 프론트엔드 요구사항 / 동작 |
| :--- | :---: | :--- |
| `/webrtc/offer` | `POST` | SDP Offer 송신 후 SDP Answer 수신. 수신한 Answer를 `setLocalDescription`에 설정해야 RTC 연결 성립 |
| `/projection` | `GET` | 500ms~1000ms 간격으로 Polling 하여 시각적 피드백(Gaze 등) 표시 |
| `/stream` | `GET` | SSE 연결을 통해 서버에서 푸시되는 `MODALITY:METRIC` 업데이트 실시간 처리 |
| `/tts` | `GET` | 면접관 질문(AI Message) 수신 시 `turn_index`와 함께 요청하여 오디오 컨텍스트에서 재생 |
| `PII Masking` | `Policy` | STT 반환 텍스트는 서버에서 마스킹된 상태로 `partial` 프로젝션에만 노출되므로 UI는 이를 그대로 렌더링 |

---

## 5. Fast Gate 확장 결과 (FG-M7 ~ M12)

기존 Fast Gate (FG-M1~M6)에 이어 실시간 스트리밍 검수 결과를 기록합니다.

| Gate | 검토 항목 | 결과 | 비고 |
| :--- | :--- | :---: | :--- |
| FG-M7 | WebRTC Answer 생성 성공률 | PASS | 100% (Local 테스트 기준) |
| FG-M8 | Projection SSE 지연 시간 | PASS | < 200ms |
| FG-M9 | Mutex Yield 타임아웃 | PASS | 5초 내 강제 획득(Orphan Recovery) 작동 확인 |
| FG-M10 | STT 턴 경계 Drop 로직 | PASS | TURN_FINALIZED 이후 결과 무시 |
| FG-M11 | gTTS Latency | PASS | 최초 생성 < 2s, 캐시 히트 < 100ms |
| FG-M12 | PDF 텍스트 무결성 | PASS | 빈 칸 탈락 및 특수문자 마스킹 확인 |
