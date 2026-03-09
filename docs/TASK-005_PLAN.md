# TASK-005 Plan: Playground STT (File Upload Based Analysis API)

**[작성일]** 2026-02-09  
**[상태]** Plan Proposed (수정 승인 대기)

---

## 1. Goal Summary
**목표**: Playground용 **파일 업로드 기반 분석 API** 구현.
오디오/영상 파일을 업로드받아 **Mock STT Provider**를 통해 분석하고, 결과를 즉시 반환하는 파이프라인(Upload → Process → Return)을 구축합니다. (DB 저장 없음)

## 2. Scope (범위)

| 구분 | In Scope (포함) | Out of Scope (제외) |
| :--- | :--- | :--- |
| **Feature** | `POST /api/v1/playground/stt` 구현 | UI/Frontend 개발 |
| **Logic** | 파일 업로드 핸들링 (Multipart) | DB 저장 (ERD 반영 안함) |
| **Logic** | `MockSTTProvider` 연동 | 실시간 스트리밍 / WebRTC |
| **Logic** | 임시 파일 생명주기 관리 (저장→분석→삭제) | 인증/인가 (Auth) |
| **Output** | JSON 응답 (`TranscriptDTO`) | 실제 모델(Whisper) 연동 |

## 3. API Design Draft

### 3.1 Endpoint
- **URL**: `/api/v1/playground/stt`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`

### 3.2 Request
| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `file` | `UploadFile` | Yes | 분석할 오디오/동영상 파일 |

### 3.3 Response (JSON)
`packages.imh_core.dto.TranscriptDTO` 스키마 반환
```json
{
  "text": "This is a mock transcription result.",
  "language": "ko",
  "segments": [
    { "start": 0.0, "end": 1.0, "text": "This is" },
    ...
  ],
  "duration": 3.0
}
```

### 3.4 Error Model
**`imh_core` 표준 Error DTO 준수** (`IMHBaseError`)
- 모든 에러 응답은 아래 필드를 포함하여 클라이언트가 일관되게 처리할 수 있도록 합니다.
  - `error_code`: 에러 식별 코드 (예: `STT_PROVIDER_ERROR`)
  - `message`: 사람이 읽을 수 있는 상세 메시지
  - `request_id`: 로깅 추적을 위한 고유 ID (선택적으로 포함)
- **주요 상태 코드**:
  - **400 Bad Request**: 파일 미전송, 지원하지 않는 포맷, 용량 초과(100MB)
  - **500 Internal Server Error**: Provider 처리 실패, 파일 IO 오류

## 4. Provider 연동 전략

### 4.1 Interface Reuse
- `packages.imh_providers.stt.base.ISTTProvider` 인터페이스 재사용.
- `packages.imh_providers.stt.mock.MockSTTProvider` 구현체 사용.

### 4.2 Integration Flow (Dependency Injection)
1. `IMH/api/dependencies.py` 생성 (제안)
2. `get_stt_provider()` 의존성 함수 정의
   - 현재: `return MockSTTProvider()`
   - 향후: Config에 따라 `FasterWhisperProvider` 등으로 교체 용이성 확보
3. Router에서 `Depends(get_stt_provider)`로 주입받아 사용.

## 5. 파일 처리 정책

### 5.1 Storage Policy
- **임시 저장 원칙**: 서버는 원본을 보관하지 않음 (`CURRENT_STATE.md` 준수).
- **Process**:
  1. `tempfile.NamedTemporaryFile(delete=False)`로 디스크에 임시 기록.
  2. Provider에 `file_path` 전달.
  3. `try...finally` 블록에서 `os.remove(file_path)` 호출로 **즉시 삭제 보장**.

### 5.2 Constraints
- **Format**: `.wav`, `.mp3`, `.m4a`, `.webm`, `.mp4` (확장자 및 MIME 타입 체크)
- **Video File Handling**: 동영상 파일(`.mp4`, `.webm` 등)이 업로드된 경우, **오디오 트랙만 추출하여** STT Provider에 전달하는 것을 원칙으로 합니다. (Mock 단계에서는 파일명만 전달하더라도, 실제 구현 시 오디오 추출 로직이 들어갈 자리임을 명시)
- **Size Limit**: 100MB (Application Level Check)

### 5.3 Security
- **Filename**: 업로드된 원본 파일명 무시, `uuid`로 랜덤 생성하여 Path Traversal 방지.

## 6. 로깅/관측성 설계

`TASK-001` 인프라 활용 (`IMH.main.logger` or `get_logger`)
- **INFO**: "STT Request: size={bytes} bytes, filename={uuid}, request_id={id}"
- **INFO**: "STT Success: latency={ms}ms"
- **ERROR**: "STT Failed: {error_code} - {message}" (Traceback은 `.log` 파일에만 기록)
- **PII 보호**: 원본 파일명, 변환된 텍스트 내용은 로그에 남기지 않음.

## 7. 테스트 전략

### 단위/통합 테스트 (`scripts/verify_task_005.py`)
- **성격**: 본 스크립트는 개발자가 구현 상태를 빠르게 확인하기 위한 **수동 검증 도구(Manual Developer Verification)**입니다.
- **범위**: CI/CD 파이프라인의 자동화 테스트와는 분리되며, API 엔드포인트의 기본 동작(Happy Path, Basic Error Path)만을 확인합니다.
- **Scenarios**:
  1. **정상 케이스**: Dummy `.wav` 파일 전송 → 200 OK & JSON 필드 검증.
  2. **예외 케이스**: 파일 없이 요청 → 422 Unprocessable Entity.
  3. **용량/형식 제한**: (코드 상 강제 로직이 들어갈 경우) 해당 로직 동작 확인.

## 8. 승인 후 구현 대상 파일 (예상)

| 구분 | 파일 경로 | 설명 |
| :--- | :--- | :--- |
| **[NEW]** | `IMH/IMH_Interview/IMH/api/playground.py` | 파일 업로드 및 STT 핸들러 구현 |
| **[NEW]** | `IMH/IMH_Interview/IMH/api/dependencies.py` | Provider DI 관리 (코드 구조화) |
| **[MODIFY]** | `IMH/IMH_Interview/IMH/main.py` | Router 등록 (`/api/v1/playground`) |
| **[NEW]** | `IMH/IMH_Interview/scripts/verify_task_005.py` | 수동 검증 스크립트 |
| **[MODIFY]** | `IMH/IMH_Interview/docs/DEV_LOG.md` | 구현 내역 기록 |

## 9. 리스크 및 결정 사항
- **Async IO**: FastAPI `UploadFile` 파일 쓰기와 Provider 호출을 모두 `async`로 처리하여 블로킹 방지.
- **Provider DI**: 이번 단계에서 `dependencies.py`를 도입하여 향후 모델 교체 기반을 마련함.
