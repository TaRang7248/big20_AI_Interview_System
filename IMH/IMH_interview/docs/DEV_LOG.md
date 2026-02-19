
## 2026-02-09

### TASK-001 로깅 기반 구축 (Logging Infrastructure)
- **요약**: `imh_core/logging` 패키지 구현 및 프로젝트 로그 디렉토리 구조 확정.
- **변경 사항**:
    - `packages/imh_core/logging/config.py` 생성: `TimedRotatingFileHandler` 적용 (매일 자정 로테이션).
    - `logs/agent/` 디렉토리 생성: 에이전트 및 로컬 개발용 로그 저장.
    - `logs/runtime/` 디렉토리 생성: 향후 API 서버 런타임 로그 저장용.
    - `scripts/check_logging.py` 추가: 로깅 동작 검증용 스크립트.
- **검증 증거**:
    - **생성된 로그 파일**:
        1. `IMH/IMH_Interview/logs/agent/agent.log`
        2. `IMH/IMH_Interview/logs/agent/agent.error.log`
        3. *(Runtime 로그 폴더 생성됨, 파일은 런타임 시 생성)*
    - **로테이션 설정**: `interval=1` (매일), `backupCount=30` (30일 보관)
    - **스택트레이스 기록 확인** (`agent.error.log` 발췌):
      ```text
      [2026-02-09 11:13:32] [ERROR] [verification_script] [check_logging.py:26] This is an INTENTIONAL EXCEPTION
      Traceback (most recent call last):
        File "...\scripts\check_logging.py", line 24, in verify_logging
          1 / 0
      ZeroDivisionError: division by zero
      ```
- **디렉토리 구조**:
  ```text
  IMH/IMH_Interview/packages
  ├── imh_core
  │   ├── logging
  │   │   ├── config.py
  │   │   └── __init__.py
  │   └── __init__.py
  └── __init__.py
  ```

### TASK-002 imh_core 최소 패키지 구성 (Core Infrastructure)
- **요약**: `imh_core` 패키지 내 `config`, `errors`, `dto` 모듈 구현 및 표준화
- **변경 사항**:
    - `packages/imh_core/config.py`: `pydantic-settings` 기반 단일 설정 클래스(`IMHConfig`) 구현. `.env` 로딩 지원.
    - `packages/imh_core/errors.py`: 공통 예외 클래스(`IMHBaseError`) 및 에러 코드 체계 정의.
    - `packages/imh_core/dto.py`: `pydantic.BaseModel` 기반 `BaseDTO` 정의 (ORM 모드, 공백 제거 자동화).
    - `scripts/verify_task_002.py`: 모듈 동작 검증 스크립트 작성.
- **검증 증거**:
    - **스크립트 실행 결과**: `python scripts/verify_task_002.py` -> `ALL PASS`
    - **Config**: `.env` 파일 로드 및 기본값 동작 확인.
    - **Errors**: 사용자 정의 에러 raise/catch 및 에러 코드 확인.
    - **DTO**: Pydantic 기능(공백 제거 등) 동작 확인.
- **디렉토리 구조**:
  ```text
  packages/imh_core
  ├── config.py
  ├── dto.py
  ├── errors.py
  └── logging/ (기존 유지)
  ```

### TASK-003 Provider 인터페이스 + Mock 구현 (Provider Layer)
- **요약**: STT, LLM, Emotion, Visual, Voice 5개 도메인의 Provider 인터페이스 정의 및 Async Mock 구현체 작성.
- **변경 사항**:
    - `packages/imh_core/dto.py`: 각 Provider별 입출력 DTO 추가 (`TranscriptDTO`, `LLMMessageDTO` 등).
    - `packages/imh_providers/`: 도메인별 패키지 구조 생성.
    - `packages/imh_providers/{domain}/base.py`: `abc.ABC` 기반 Async 인터페이스 정의 (`ISTTProvider` 등).
    - `packages/imh_providers/{domain}/mock.py`: `asyncio.sleep` 기반 Latency 시뮬레이션이 가능한 Mock 구현체 작성.
    - `scripts/verify_task_003.py`: 5개 Mock Provider 통합 검증 스크립트 작성.
- **검증 증거**:
    - **스크립트 실행 결과**: `python scripts/verify_task_003.py` -> `ALL MOCK PROVIDERS VERIFIED SUCCESSFULLY!`
    - **DTO**: Pydantic 모델을 통한 입출력 타입 강제 확인.
    - **Async**: `async def` 인터페이스 및 `await` 호출 정상 동작 확인.
- **디렉토리 구조**:
  ```text
  packages/imh_providers/
  ├── stt/ (base.py, mock.py)
  ├── llm/ (base.py, mock.py)
  ├── emotion/ (base.py, mock.py)
  ├── visual/ (base.py, mock.py)
  └── voice/ (base.py, mock.py)
  ```

### TASK-004 FastAPI 최소 엔트리 + Healthcheck (Application Entry)
- **요약**: `IMH/main.py` 진입점 생성 및 `/health` 라우터 구현. `imh_core` 로깅 연동.
- **변경 사항**:
    - `IMH/main.py`: FastAPI 앱 생성, `lifespan` 이벤트를 통한 런타임 로깅 초기화.
    - `IMH/api/health.py`: Liveness Probe용 `/health` 엔드포인트.
    - `logs/runtime/runtime.log`: 서버 실행 로그가 기록될 파일 생성 확인.
    - `scripts/verify_task_004.py`: 서버 구동 및 Healthcheck 응답 검증 스크립트.
- **검증 증거**:
    - **스크립트 실행 결과**: `python scripts/verify_task_004.py` -> `[PASS] Healthcheck response is valid.`
    - **Health Response**: `{"status": "ok", "version": "0.1.0", "timestamp": "..."}`
    - **Runtime Log**: `Starting IMH AI Interview v0.1.0...` 기록 확인.
- **디렉토리 구조**:
  ```text
  IMH/IMH_Interview/IMH
  ├── api/
  │   ├── health.py
  │   └── __init__.py
  └── main.py
  ```
- **환경 검증 보완 (2026-02-09 Supplementary)**:
    - **실행 환경**: `interview_env` (venv) 활성화 상태에서 `scripts/verify_task_004.py` 재검증 완료.
    - **패키지 확인**: `fastapi`, `uvicorn`, `httpx` 등 필수 패키지가 `interview_env`에 설치되어 있음을 확인.

### TASK-005 Playground STT (파일 업로드)
- **요약**: `dependencies.py`를 통한 Mock STT Provider 연동 및 파일 업로드 분석 API 구현.
- **변경 사항**:
    - `IMH/api/playground.py`: Playground STT Router 구현 (임시 파일 처리, Validation).
    - `IMH/api/dependencies.py`: Provider Dependency Injection (`get_stt_provider`) 추가.
    - `IMH/main.py`: Playground Router 등록 (`/api/v1/playground`).
    - `python-multipart` 패키지 설치: `UploadFile` 처리를 위한 의존성 추가.
- **검증 증거**:
    - **스크립트 실행 결과**: `python scripts/verify_task_005.py`
        - 정상 `.wav` 파일 -> 200 OK (Mock Data).
        - 비정상 `.txt` 파일 -> 400 Bad Request.
    - **로그 확인**: `logs/agent/agent.log`에 요청 정보(UUID 파일명, 사이즈) 및 처리 결과 기록 확인.
- **로그 파일**:
    - 런타임 로그: `logs/runtime/runtime.log`

### TASK-006 Playground PDF → Text (문서 업로드)
- **요약**: `pypdf` 기반 PDF 텍스트 추출 API 구현 (`/pdf-text`). 안정성 제약(페이지 수, 용량) 적용.
- **변경 사항**:
    - `packages/imh_core/dto.py`: `PDFExtractionResultDTO`, `PDFPageDTO` 추가.
    - `packages/imh_providers/pdf/`: `IPDFProvider` 인터페이스 및 `LocalPDFProvider` 구현.
    - `IMH/api/dependencies.py`: `get_pdf_provider` 추가.
    - `IMH/api/playground.py`: `POST /pdf-text` 엔드포인트 구현 (50페이지/10MB 제한).
    - `requirements.txt`: `pypdf` 의존성 확인.
    - `scripts/verify_task_006.py`: 검증 스크립트 작성.
- **검증 증거**:
    - **스크립트 실행 결과**: `python scripts/verify_task_006.py` (Verify Environment: interview_env)
        - Invalid Ext (.txt) -> 400 OK
        - Page Limit (51 pages) -> 400 OK
        - No Text (Blank PDF) -> 422 OK
    - **로그 확인**: `logs/agent/agent.log`에 페이지 수, 글자 수, Latency 기록 확인.

### TASK-007 Playground Embedding → Query Focus
- **요약**: 검색(RAG) 용도로 사용되는 **Query Text**를 임베딩 벡터로 변환하는 Playground 파이프라인 구현. 대화 전체/STT 결과 임베딩은 제외하고, Mock Provider 기반으로 변환 흐름만 검증.
- **변경 사항**:
    - `packages/imh_providers/embedding/`: Embedding Provider 패키지 신설 (`Interface`, `MockEmbeddingProvider`).
    - `packages/imh_core/dto.py`: `EmbeddingRequestDTO`, `EmbeddingResponseDTO` 추가.
    - `IMH/api/playground.py`: `POST /embedding` 엔드포인트 추가.
    - `scripts/verify_task_007.py`: Query Text → Embedding 변환 검증 스크립트 작성.
- **검증 증거**:
    - **스크립트 실행 결과**: `python scripts/verify_task_007.py` (Verify Environment: `interview_env`)
        - Valid Query Text -> Vector 반환 성공
        - Empty / Invalid Input -> Validation Error 처리 확인
        - 전체 테스트 통과 시 `"ALL TESTS PASSED"` 출력
    - **로그 확인**: `IMH/IMH_Interview/logs/runtime/runtime.log`에 API 요청/응답 및 처리 결과 기록 확인.

### TASK-008 Emotion 분석 (DeepFace Implementation)
- **요약**: DeepFace 모델을 활용한 **영상(1fps)/이미지 감정 분석** 파이프라인 구현. `playground` API에 통합 및 DTO 구조화.
- **변경 사항**:
    - `packages/imh_providers/emotion/dto.py`: 시계열 분석 결과(`VideoEmotionAnalysisResultDTO`) 및 프레임 DTO 정의.
    - `packages/imh_providers/emotion/deepface_impl.py`: `DeepFaceEmotionProvider` 구현 (OpenCV Backend, 1fps 샘플링, Face Detection Fail 처리).
    - `packages/imh_providers/emotion/base.py`, `mock.py`: `analyze_video` 인터페이스 추가 및 Mock 구현 업데이트.
    - `IMH/api/dependencies.py`: `get_emotion_provider` 의존성 주입 추가 (DeepFaceImpl 사용).
    - `IMH/api/playground.py`: `POST /emotion` 엔드포인트 구현 (이미지/비디오 분기 처리).
    - `scripts/verify_task_008.py`: `TestClient` 기반 통합 검증 스크립트 작성 (Dummy 영상/이미지 생성 및 업로드).
    - **환경 변경**: `tf-keras` 패키지 설치 (DeepFace + TF 2.20 호환성 이슈 해결).
- **검증 증거**:
    - **스크립트 실행 결과**: `python scripts/verify_task_008.py` (Verify Environment: `interview_env`)
        - Image Upload -> 200 OK (DeepFace/Image Result).
        - Video Upload (3s, 10fps) -> 200 OK. 3 Frames Analyzed (1fps Sampling 동작 확인).
        - JSON 구조(`metadata`, `results`) 및 `timestamp` 정합성 확인.
    - **로그 확인**: `IMH/IMH_Interview/logs/runtime/runtime.log`에 분석 프레임 수 및 처리 시간 기록 확인.


### TASK-009 Voice 분석 (Parselmouth)
- **요약**: `praat-parselmouth` 라이브러리를 활용한 음성 분석 Provider(`ParselmouthVoiceProvider`) 구현 및 Playground API 연동.
- **변경 사항**:
    - `packages/imh_providers/voice/parselmouth_impl.py`: `analyze_audio` 구현 (Pitch, Intensity, Jitter, Shimmer, HNR 추출).
    - `packages/imh_core/dto.py`: `VoiceResultDTO` 확장 (Intensity 및 Min/Max 필드 추가).
    - `IMH/api/playground.py`: `POST /voice` 엔드포인트 추가.
    - `IMH/api/dependencies.py`: `get_voice_provider` 의존성 주입 추가.
    - `scripts/verify_task_009.py`: 검증 스크립트 작성 (Sine Wave, Silence, Invalid File 테스트).
    - **환경 변경**: `praat-parselmouth` 패키지 설치.
- **검증 증거**:
    - **스크립트 실행 결과**: `python scripts/verify_task_009.py` (Verify Environment: `interview_env`)
        - Sine Wave (440Hz) -> 200 OK. Feature Extraction (Pitch ~440Hz, Jitter/Shimmer/HNR Valid).
        - Silence File -> 200 OK. Null/Zero Values Returned (Graceful Handling).
        - Invalid File (.txt) -> 500 Internal Server Error (Provider Exception Raised).
    - **로그 확인**: `logs/runtime/runtime.log`에 분석 지표 요약 및 예외 스택트레이스 기록.

#### TASK-009 Hotfix (2026-02-10)
- **요약**: Voice 분석 시 잘못된 파일 입력에 대해 500 대신 422 에러를 반환하도록 수정.
- **변경 사항**:
    - `packages/imh_providers/voice/parselmouth_impl.py`: `parselmouth.Sound` 생성 실패 시 `ValueError`로 래핑하여 raise.
    - `IMH/api/playground.py`: `analyze_voice`에서 `ValueError` 포착 시 `HTTP 422` 반환.
    - `scripts/verify_task_009.py`: Invalid File 테스트 기대치를 500 -> 422로 수정.
- **재검증 결과**:
    - Invalid File (.txt) -> 422 Unprocessable Entity 확인.
    - 정상/무음 파일 기존 테스트 통과 유지.

### PRE_TASK-010 선행 안정화 (Stabilization)
- **요약**: TASK-010 착수 전, 기존 Emotion 엔드포인트의 리소스 누수 및 Mock Provider 정합성 버그 수정.
- **변경 사항**:
    - `IMH/api/playground.py`: `analyze_emotion` 내 `UnboundLocalError`(예외 변수 미정의 참조) 및 임시 파일 삭제 누락 수정.
    - `packages/imh_providers/emotion/mock.py`: `EmotionResultDTO` 필수 필드(`scores`) 누락분 보완.
- **검증 증거**:
    - `scripts/verify_task_008.py` 실행 시 임시 파일 삭제 로그(`Temporary Emotion file deleted`) 확인 및 Regression Test (001~009) All Pass.

## 2026-02-10: TASK-010 Visual 분석 (MediaPipe) 구현
Plan 수립
- **요약**: MediaPipe 기반 시각 분석(시선, 포즈, 제스처) 모듈을 프로젝트 표준으로 흡수하기 위한 계획 문서 작성.
- **변경 사항**:
    - `docs/TASK-010_PLAN.md` 작성: "성공했던 구현의 재현 및 표준화"를 골자로 한 Phase 2 최종 분석 모듈 설계 방향 확정.
- **주요 전략**:
    - **재현 기반(Reproduction)**: 과거 성공한 MediaPipe 연동 구조를 Phase 2 기준선으로 고정.
    - **안전 출력 중심**: 얼굴/신체 미검출(No Face) 시에도 안정적인 DTO 반환 보장.
    - **관리형 리스크**: 의존성 충돌 이슈를 재설계가 아닌 환경 관리 대상으로 정의하여 안정성 확보.

### TASK-010 Visual 분석 (MediaPipe) Implementation
- **요약**: MediaPipe 기반 시각 분석(시선, 포즈) Provider(`MediaPipeVisualProvider`) 구현 및 Playground API 연동. Phase 2 기준선(Reproduction Baseline) 준수.
- **변경 사항**:
    - `packages/imh_providers/visual/dto.py`: `VisualResultDTO` 정의 (Presence, Attention, Pose Score 및 Metadata).
    - `packages/imh_providers/visual/mediapipe_impl.py`: `analyze` 메서드 구현. 얼굴 검출, 시선(Yaw), 어깨 기울기(Pose) 분석 로직 적용.
    - `IMH/api/dependencies.py`: `get_visual_provider` 의존성 주입 추가.
    - `IMH/api/playground.py`: `POST /visual` 엔드포인트 구현 (이미지 업로드).
    - `scripts/verify_task_010.py`: 검증 스크립트 작성 (No Face 시나리오 검증).
- **검증 증거**:
    - **스크립트 실행 결과**: `python scripts/verify_task_010.py` (Verify Environment: `interview_env`)
        - No Face Image (Black) -> `has_face=False`, `presence_score=0.0` 확인.
        - API Router Import -> 성공.
        - Provider Initialization -> 성공 (MediaPipe Spec: 0.10.5 확인).
    - **로그 확인**: `logs/agent/agent.log`에 `Visual Analysis succeeded. Has Face: False` 기록 확인.

## 2026-02-11: TASK-011 정량 평가 엔진 구현 (Phase 2 Evaluation)
- **변경 요약**: 
  - `packages/imh_eval` 패키지 신규 생성 (Rule-based Scoring Engine)
  - 루브릭 가이드 기반 4대 영역(직무/문제해결/의사소통/태도) 평가 로직 구현
  - `EvaluationContext` -> `RubricEvaluator` -> `EvaluationResult` 파이프라인 구축
  - `schema.py`를 통해 `evidence_data` 및 `tag_code` 계약 준수
  - TASK-011은 Rule-based Engine이며, 모델 품질은 평가 대상이 아님
- **테스트 방법**: 
  - `python scripts/verify_task_011.py` 실행
- **검증 결과**:
  - 만점 시나리오(DEV Profile) -> 5.0점 확인
  - 복합 시나리오(NON_TECH Profile) -> 가중치 적용 점수(2.7점) 정합성 확인
  - JSON Schema output 필드 존재여부 확인 완료
- **로그 파일**: `logs/agent/verify_task_011.log`


### TASK-025 RAG Fallback 엔진 통합 (RAG Fallback Integration)
- **요약**: Session Engine 내에 `QuestionGenerator` (RAG)와 `QuestionBankService` (Fallback)를 통합하여, 질문 생성 실패 시 안전하게 정적 질문으로 전환하는 로직 구현.
- **변경 사항**:
  - `packages/imh_session/dto.py`: `SessionQuestion` Value Object 및 `SessionQuestionType` 정의 (Snapshot 구성요소).
  - `packages/imh_providers/question.py`: `QuestionGenerator` 인터페이스 및 Mock 구현.
  - `packages/imh_session/engine.py`: `_get_next_question` 메서드 구현 (RAG -> Fallback -> Emergency 전략).
  - `packages/imh_service/session_service.py` & `IMH/api/dependencies.py`: 의존성 주입(DI) 구조 업데이트.
  - `scripts/verify_task_025.py`: 4가지 시나리오(Success, Fallback, Critical, Snapshot) 검증 스크립트 작성.
- **검증 결과**:
  - `python scripts/verify_task_025.py`: **Pass**
    1. **Normal Generation**: RAG Success -> Source `GENERATED` 확인.
    2. **Explicit Fallback**: RAG Failure -> Source `STATIC` (from QBank) 확인.
    3. **Critical Failure**: QBank Empty -> Emergency Message (Safe Fallback) 확인.
    4. **Snapshot Independence**: 질문 생성 후 저장된 세션 데이터의 불변성 확인.
- **주요 설계 반영**:
  - **Single Authority**: Fallback 결정은 오직 Session Engine이 수행.
  - **Snapshot Integrity**: 생성된 질문은 `SessionQuestion` Value Object로 스냅샷에 포함되어 영구 보존.
  - **Fail-Fast**: RAG 실패 시 즉시 Fallback 전환 (User Latency 최소화).
- **로그 및 산출물**:
  - `packages/imh_session/` 및 `packages/imh_providers/` 업데이트.

### TASK-012 평가 결과 리포팅 / 해석 계층 설계 (Reporting Layer)
- **요약**: `packages/imh_report` 패키지 구현. Evaluation Result를 입력받아 사용자 친화적인 리포트(JSON)를 생성하는 Logic 구현.
- **변경 사항**:
  - `packages/imh_report/dto.py`: `InterviewReport`, `ReportHeader`, `ReportDetail` 등 DTO 정의.
  - `packages/imh_report/mapping.py`: `tag_code` -> Feedback/Insight 매핑 및 등급 산출 로직 구현.
  - `packages/imh_report/engine.py`: `ReportGenerator.generate()` 구현 (5점 척도 -> 100점 환산, 등급 부여, Insight 결합).
  - `scripts/verify_task_012.py`: Mock Data 기반 리포트 생성 및 필드 검증 스크립트 작성.
- **검증 증거**:
  - **스크립트 실행 결과**: `python scripts/verify_task_012.py`
    - Mock Evaluation Result (3.5점) -> Report Total Score 70.0점, Grade "B" 확인.
    - 직무 역량(4점) -> "우수합니다" 피드백, Strength 추가 확인.
    - 태도(2점) -> "보완이 필요합니다" 피드백, Weakness 및 Actionable Insight 추가 확인.
    - JSON Output 구조(`header`, `details`, `footer`) 정합성 확인.
- **로그 및 산출물**:
  - `packages/imh_report/__init__.py` 포함 패키지 구조화.

### TASK-013 리포트 저장 / 이력 관리 (Persistence & History)
- **요약**: `packages/imh_history` 구현. `InterviewReport`(JSON)를 파일 시스템에 저장하고, 메타데이터 기반으로 이력을 조회하는 Repository 계층 구축.
- **변경 사항**:
  - `packages/imh_history/dto.py`: 리스트 조회용 메타데이터 `HistoryMetadata` DTO 정의.
  - `packages/imh_history/repository.py`: `HistoryRepository` 인터페이스 및 `FileHistoryRepository` 구현 (파일 시스템 기반 JSON 저장소).
  - `IMH/IMH_Interview/data/reports/`: 리포트 저장소 디렉토리 생성 및 `.gitignore` 설정.
  - `scripts/verify_task_013.py`: 저장(Save), 단건 조회(Find By ID), 목록 조회(Find All) 기능 검증 스크립트 작성.
- **검증 증거**:
  - **스크립트 실행 결과**: `python scripts/verify_task_013.py`
    - Save -> `data/reports/{timestamp}_{uuid}.json` 파일 생성 확인.
    - Find By ID -> 저장된 데이터와 조회된 DTO 일치 확인.
    - Find All -> 파일 리스트 파싱 및 타임스탬프 기준 정렬 확인.
    - 메타데이터 정합성(Score, Grade 등) 확인 완료.
- **로그 및 산출물**:
  - `packages/imh_history/` 패키지 구조화.

### TASK-014 리포트 조회 API 노출 (Report API)
- **요약**: 저장(TASK-013)된 리포트 데이터를 조회하기 위한 API Contract 구현 (BFF Endpoint).
- **변경 사항**:
  - `IMH/api/reports.py`: `GET /api/v1/reports` (목록) 및 `/{id}` (상세) 구현.
  - `IMH/api/dependencies.py`: `get_history_repository` 추가.
  - `IMH/main.py`: Report Router 등록.
  - `scripts/verify_task_014.py`: 통합 검증 스크립트 작성 (생성 -> 저장 -> 조회 -> 삭제 파이프라인).
- **검증 증거**:
  - **스크립트 실행 결과**: `python scripts/verify_task_014.py` -> `ALL TESTS PASSED`
    1. List API: 생성된 리포트가 목록에 포함됨 확인.
    2. Detail API: 상세 필드(점수, 등급 등)가 원본과 일치함 확인.
    3. Error Handling: 존재하지 않는 ID 요청 시 404 정상 반환 확인.
  - **참고**
    -  Windows 환경에서 테스트 로그 로테이션 시 `PermissionError` 발생 가능하나 로직 무관함.
    - 검증 스크립트(scripts/verify_task_014.py)는 Plan에 명시되진 않았으나, 
      구현 검증 목적의 보조 도구로 사용되었으며 Contract에는 영향을 주지 않는다.”
- **로그 및 산출물**:
  - `packages/imh_history/` 및 `packages/imh_report/` 기존 코드 활용.
  - API Layer 추가.

### TASK-015 리포트 소비 규격 정의 (Consumer Contract)
- **요약**: UI 및 외부 Client가 리포트 데이터를 올바르게 해석하기 위한 소비 규격(`TASK-015_CONTRACT.md`) 작성.
- **변경 사항**:
    - `docs/TASK-015_CONTRACT.md`: 리포트 소비 주체, 목적, 데이터 렌더링 가이드, 책임 경계 정의.
    - 구현 코드 없음 (Plan Only Task).
- **산출물**:
    - [TASK-015_CONTRACT.md](TASK-015_CONTRACT.md)

### TASK-020 관리자 지원자 조회/필터 규격 및 구현 (Admin Applicant Retrieval)
- **요약**: 관리자가 공고별 지원자 목록을 조회하고 다양한 조건(상태, 합불, 날짜 등)으로 필터링할 수 있는 규격 정의 및 구현.
- **변경 사항**:
    - `packages/imh_session/query.py`: `ApplicantQueryService` 구현 (Active Session + History Report Federated Search).
    - `packages/imh_session/infrastructure/memory_repo.py`: `MemorySessionRepository` 구현 (`find_by_job_id` 지원).
    - `packages/imh_history/dto.py` & `repository.py`: `HistoryMetadata`에 `job_id`, `status`, `started_at` 필드 추가 및 매핑 로직 구현.
    - `packages/imh_session/dto.py`: `SessionContext`에 `job_id`, `started_at` 필드 추가.
    - `packages/imh_eval` & `imh_report`: `job_id` 전파 로직 구현 (Context -> Result -> Report Header).
    - `docs/TASK-020_PLAN.md`: 관리자 조회 규격 및 필터 정책 확정.
    - `scripts/verify_task_020.py`: 통합 조회 및 필터링(Status, Date, Result, Alias) 검증 스크립트 작성.
- **검증 결과**:
    - `python scripts/verify_task_020.py`: **Pass**
        1. **Federated Search**: Active Session(Memory)과 Archived Report(File) 통합 조회 확인.
        2. **Job ID Filter**: 특정 공고 ID에 대한 세션만 필터링됨을 확인.
        3. **Status Filter**: `IN_PROGRESS`, `EVALUATED` 등 상태별 필터링 정상 동작 확인.
        4. **Result Filter**: `PASS/FAIL` 필터가 `EVALUATED` 상태 세션에 대해 정상 동작함 확인.
        5. **Date Filter**: `started_at` 기준 기간 필터링 동작 확인 (APPLIED 등 시작 시간 없는 세션 제외).
        6. **Alias**: `is_interrupted=True` 시 `INTERRUPTED` 상태 자동 포함 확인.
- **제약 사항**:
    - `search_keyword` (이름/이메일) 및 `weakness` 필터는 데이터(PII/Detail) 부재로 인해 현재 단계에서는 제한적으로 동작함 (향후 Phase 확장 시 보완)..
    - 구현 코드 없음 (Plan Only Task).
- **산출물**:
    - [TASK-015_CONTRACT.md](TASK-015_CONTRACT.md)

### TASK-017 Interview Session Engine (Phase 5 Core)
- **요약**: 실시간 면접 세션의 동작 정책을 관장하는 Session Engine (`packages/imh_session`) 구현 완료.
- **변경 사항**:
  - `packages/imh_session/` 패키지 구조화.
  - `state.py`: 5대 세션 상태(APPLIED, IN_PROGRESS, COMPLETED, INTERRUPTED, EVALUATED) 정의.
  - `dto.py`: `SessionConfig` (최소 10질문 기본값), `SessionContext` (Redis-like Hot State) 정의.
  - `repository.py`: Hot State(Redis) / Cold Storage(PostgreSQL) 인터페이스 분리 설계.
  - `engine.py`: Strict State Machine 및 Policy Enforcement 구현.
    - 최소 질문 수(10) 미달 시 조기 종료 차단 로직.
    - 침묵 2케이스(Post-Answer / No-Answer) 분기 처리 및 SILENCE_WARNING 이벤트 구조.
    - 조기 종료 신호(`early_exit_signaled`) 수신 시 종료 처리 로직.
  - `scripts/verify_task_017.py`: Mock Repository 기반 정책 검증 스크립트.
- **검증 증거**:
  - **스크립트 실행 결과**: `python scripts/verify_task_017.py` -> `Ran 7 tests in 0.003s OK`
    1. **State Machine**: APPLIED -> IN_PROGRESS -> COMPLETED 전이 확인.
    2. **Min Question Policy**: 10문제 미만에서 조기 종료 신호 무시 확인.
    3. **Early Exit**: 10문제 이상 + 신호 발생 시만 COMPLETED 전이 확인.
    4. **Silence Handling**: 
       - `is_no_answer=True` (무응답) -> 완료 카운트 증가, 다음 질문 진행.
       - `is_no_answer=False` (답변 후 침묵) -> 완료 카운트 증가.
    5. **Interruption**: USER_ABORT 시 INTERRUPTED 상태 확정 확인.
- **로그 및 산출물**:
  - `packages/imh_session/` 패키지 사용.

## 2026-02-13: TASK-018 실전/연습 모드 정책 분리 구현 (Interview Mode Policy Split)

- **작업 내용**:
  - `packages/imh_session/policy.py`: 정책 인터페이스(`InterviewPolicy`) 및 모드 구현체(`ActualModePolicy`, `PracticeModePolicy`) 정의.
  - `packages/imh_session/dto.py`: `SessionConfig`에 `mode: InterviewMode` 필드 추가 (기본값 ACTUAL).
  - `packages/imh_session/engine.py`: 
    - 엔진 초기화 시 정책 주입 로직 추가.
    - 조기 종료(`_complete_current_step`) 및 중단(`interrupt_session`) 로직에 정책 검사(`policy.requires_min_questions_for_early_exit`) 반영.
    - `resume_session` 메서드 추가 (정책 허용 시에만 동작).
  - `scripts/verify_task_018.py`: 실전/연습 모드별 정책 차이(재진입, 조기 종료 시점) 검증 스크립트 작성.

- **검증 결과**:
  - `python scripts/verify_task_018.py`: **Pass**
    1. **실전 모드**: 
       - 중단 시 `INTERRUPTED` 상태로 종료됨을 확인.
       - 재진입(`resume_session`) 시도 시 정책 위반 로그 발생 및 상태 유지 확인.
       - 최소 질문 수(5개) 미만에서 조기 종료 신호 무시(IN_PROGRESS 유지) 확인.
       - 최소 질문 수 충족 후 조기 종료 신호 시 `COMPLETED` 전이 확인.
    2. **연습 모드**: 
       - 중단 후 재진입(`resume_session`) 시 `IN_PROGRESS`로 복구됨을 확인.
       - 최소 질문 수 미만에서도 조기 종료 신호 시 즉시 `COMPLETED` 전이 확인.
  - `python scripts/verify_task_017.py`: **Pass**
    - 기존 엔진 로직(기본값 Actual Mode)에 회귀 없음을 확인.

### TASK-018 기술적 제약 및 향후 요구사항 (2026-02-13 보강)

**A. 런타임 진입점 부재 명시**
- 현재 프로젝트에는 SessionConfig를 생성하고 InterviewSessionEngine을 초기화하는 실제 런타임 경로(API Endpoint / Service Layer)가 아직 존재하지 않는다.
- TASK-017 및 TASK-018은 엔진 코어 로직과 정책 분리, 그리고 단위 검증 스크립트(scripts/verify_task_*.py) 수준까지만 포함한다.
- 따라서 Practice 모드(mode=InterviewMode.PRACTICE) 설정은 verify_task_018.py에서 수동으로 Config를 생성하여 주입하는 방식으로만 검증되었다.

**B. Mode 주입은 통합 단계에서 강제해야 함**
- 향후 Phase 5 후반부(실시간 면접 플로우 통합)에서 "연습 모드 시작" API 또는 "공고 기반 면접 시작" API가 구현될 예정이다.
- 해당 진입점에서 SessionConfig 생성 시 반드시 mode 값을 명시적으로 강제 주입해야 한다.
  - 연습 시작 → mode=InterviewMode.PRACTICE
  - 공고 기반 면접 → mode=InterviewMode.ACTUAL
- mode 값을 요청에 의존하지 말고, 서버 로직에서 강제 설정하도록 구현해야 한다.
- 이 항목은 통합 단계 DoD에 포함되어야 한다.

**C. 상태 전이 중앙 검증 관련 기술 부채 기록**
- `_update_status`는 상태 전이 유효성을 중앙에서 강제 검증하지 않으며, 호출자 책임 구조로 설계되어 있다.
- 현재 `resume_session`은 (1) status==INTERRUPTED 가드 + (2) policy 가드 이후 `_update_status`를 호출하여 문제없이 동작한다.
- 향후 엔진 안정화 단계에서 상태 전이 중앙 검증(guard/validator) 도입을 고려할 수 있다.
- 단, 본 TASK-018 범위에서는 구조 리팩터링이 금지되었으므로 변경하지 않았다.


### TASK-019 공고 정책 엔진 구현 (Job Policy Engine)
- **요약**: 공고(Job Posting)를 "불변의 AI 평가 스키마"로 정의하고, 상태(DRAFT/PUBLISHED/CLOSED)에 따른 엄격한 수정 통제 및 정책 스냅샷 로직을 구현.
- **변경 사항**:
    - `packages/imh_job/` 패키지 신설.
    - `enums.py`: `JobStatus` 정의.
    - `models.py`: `Job`, `JobPolicy` 모델 구현.
        - `JobPolicy`: AI-Sensitive Fields(Time limits, Weights, Requirements 등) 정의 및 유효성 검사.
        - `Job`: `publish()`, `close()`, `update_policy()` 메서드를 통한 상태 전이 및 불변성 강제.
        - `create_session_config()`: `SessionConfig` 스냅샷 생성 로직 구현.
    - `errors.py`: `JobStateError`, `PolicyValidationError` 정의.
    - `scripts/verify_task_019.py`: 상태 전이 및 정책 불변성 검증 스크립트 작성.
- **검증 결과**:
    - `python scripts/verify_task_019.py`: **Pass**
        - DRAFT 상태에서 정책 수정 가능 확인.
        - PUBLISHED 전환 후 정책 수정 시도 시 `PolicyValidationError` 발생 확인 (AI-Sensitive Fields 보호).
        - Session Snapshot 생성 시 값이 정확히 매핑됨을 확인.
        - CLOSED 상태에서 메타데이터 수정 차단 확인.
- **주요 정책 반영**:
    - **Irreversible Transition**: PUBLISHED 상태 이후 되돌리기 불가.
    - **Minimum Questions**: 최소 질문 수 10개 강제 (System Policy).
    - **Result Exposure**: 14일 자동 통지 규칙을 상위 제약으로 명시.

### TASK-019 결함 수정 (Bug Fix)
- **이슈**: Pydantic 모델의 `job.policy = ...` 직접 대입 허용으로 인한 불변성 우회 가능성 확인.
- **수정**: `Job` 모델의 `policy` 필드를 `_policy` (PrivateAttr)로 변경하고, `@property` setter를 통해 상태 기반 쓰기 권한을 강제함.
- **검증**: `verify_task_019.py`에 직접 대입 시도 테스트 케이스 추가 -> `PolicyValidationError` 발생 확인.

### TASK-020 관리자 지원자 조회/필터 규격 및 구현 (Admin Applicant Retrieval)
- **요약**: 관리자가 공고별 지원자 목록을 조회하고 다양한 조건(상태, 합불, 날짜 등)으로 필터링할 수 있는 규격 정의 및 구현.
- **변경 사항**:
    - `packages/imh_session/query.py`: `ApplicantQueryService` 구현 (Active Session + History Report Federated Search).
    - `packages/imh_session/infrastructure/memory_repo.py`: `MemorySessionRepository` 구현 (`find_by_job_id` 지원).
    - `packages/imh_history/dto.py` & `repository.py`: `HistoryMetadata`에 `job_id`, `status`, `started_at` 필드 추가 및 매핑 로직 구현.
    - `packages/imh_session/dto.py`: `SessionContext`에 `job_id`, `started_at` 필드 추가.
    - `packages/imh_eval` & `imh_report`: `job_id` 전파 로직 구현 (Context -> Result -> Report Header).
    - `docs/TASK-020_PLAN.md`: 관리자 조회 규격 및 필터 정책 확정.
    - `scripts/verify_task_020.py`: 통합 조회 및 필터링(Status, Date, Result, Alias) 검증 스크립트 작성.
- **검증 결과**:
    - `python scripts/verify_task_020.py`: **Pass**
        1. **Federated Search**: Active Session(Memory)과 Archived Report(File) 통합 조회 확인.
        2. **Job ID Filter**: 특정 공고 ID에 대한 세션만 필터링됨을 확인.
        3. **Status Filter**: `IN_PROGRESS`, `EVALUATED` 등 상태별 필터링 정상 동작 확인.
        4. **Result Filter**: `PASS/FAIL` 필터가 `EVALUATED` 상태 세션에 대해 정상 동작함 확인.
        5. **Date Filter**: `started_at` 기준 기간 필터링 동작 확인 (APPLIED 등 시작 시간 없는 세션 제외).
        6. **Alias**: `is_interrupted=True` 시 `INTERRUPTED` 상태 자동 포함 확인.
- **제약 사항**:
    - `search_keyword` (이름/이메일) 및 `weakness` 필터는 데이터(PII/Detail) 부재로 인해 현재 단계에서는 제한적으로 동작함 (향후 Phase 확장 시 보완).

#### TASK-020 계약 정합성 보강 (2026-02-13 Hotfix)
- **목적**: Plan 계약의 엄격한 준수를 위해 `weakness` 필터 제거 및 `search_keyword` 정식 지원(Validation) 적용.
- **변경 사항**:
    - `docs/TASK-020_PLAN.md`: `weakness` 필터 삭제(Deferred), `search_keyword` 제약 강제 명시.
    - `packages/imh_session/query.py`: `search_keyword` 길이(<2) 검증 및 Email(@) Exact Match 로직 구현. `weakness` 요청 시 400 Error 발생하도록 수정.
    - `scripts/verify_task_020.py`: Validation(Length, Weakness Rejection) 테스트 케이스 추가 및 검증 완료.
- **검증 결과**: `Ran 8 tests in 0.061s OK` (All Cases Pass)

### TASK-021 End-to-End 인터뷰 실행 아키텍처 통합 (Integration)
- **요약**: Session Engine, Job Policy Engine, Mode Policy, Admin Query Layer를 통합하여 전체 면접 실행 흐름을 구현.
- **변경 사항**:
    - `packages/imh_job/models.py`: `create_session_config`에 `result_exposure` 스냅샷 로직 추가.
    - `packages/imh_session/dto.py`: `SessionConfig`에 `result_exposure` 필드 추가.
    - `packages/imh_session/engine.py`: `SessionContext` 생성 시 `job_id` 주입 로직 보완.
    - `scripts/verify_task_021.py`: 통합 검증 스크립트 작성 (Job Freeze, Snapshot, Mode Policy, Admin Query 흐름 검증).
- **검증 결과**:
    - `python scripts/verify_task_021.py`: **Pass**
        1. **Job Policy Freeze**: PUBLISHED 상태 공고의 정책 수정 차단 확인.
        2. **Session Snapshot**: 공고 정책 변경이 기존 세션 스냅샷에 영향 주지 않음을 확인.
        3. **Actual Mode Flow**: 중단 시 Resume 불가(Strict) 확인.
        4. **Practice Mode Flow**: 중단 시 Resume 가능(Flexible) 확인.
- **주요 계약 반영**:
    - **Snapshot Double Lock**: Job Policy(Template) -> Session Config(Instance) 이중 잠금 체계 완성.
    - **Result Exposure**: 평가 공개 정책이 스냅샷에 포함되어 Evaluation Engine으로 전달됨을 보장.


### TASK-022 서비스 레이어 및 DTO 구현 (Service Layer & Integration)
- **요약**: API 모듈과 도메인(세션 엔진)을 중재하는 Service Layer(`packages/imh_service`)를 구현하고, DTO/Mapper를 통해 외부 의존성을 격리함.
- **변경 사항**:
    - `packages/imh_service/`:
        - `SessionService`: 세션 생성, 답변 제출(Command) 오케스트레이션 및 리포지토리 트랜잭션 관리.
        - `AdminQueryService`: Admin용 Read-Only 조회 서비스 (Lock Bypass 정책 적용).
        - `ConcurrencyManager`: 파일 기반 Lock(`Fail-Fast` 정책) 구현.
        - `Mapper`: Domain Entity ↔ API DTO 간 명시적 변환 로직 구현.
    - `packages/imh_dto/`: `SessionResponseDTO`, `AnswerSubmissionDTO` 등 API 계약용 객체 정의.
    - `scripts/verify_task_022.py`: 서비스 레이어 로직 및 동시성 제어, DTO 매핑 검증 스크립트 작성.
- **검증 결과**:
    - `python scripts/verify_task_022.py`: **Pass**
        1. **Fail-Fast Lock**: Lock 점유 상태에서 `submit_answer` 호출 시 `BlockingIOError` 발생 확인.
        2. **DTO Separation**: Service 메소드 반환값이 Domain Object가 아닌 DTO임을 확인.
        3. **Admin Query Bypass**: Lock 상태에서도 `AdminQueryService`는 정상 조회됨을 확인 (Read-Only Contract).
        4. **Creation Flow**: `JobConfig` 스냅샷 기반 세션 생성 및 초기 상태 매핑 확인.
- **주요 설계 반영**:
    - **Layered Arch**: API -> DTO -> Service -> Domain 방향성 준수.
    - **Strict Isolation**: Domain Entity가 API 외부로 절대 노출되지 않도록 Mapper 강제.
    - **Concurrency Identity**: Session ID 기반 파일 락으로 Race Condition 방지 (Redis 도입 전 임시 조치).


### TASK-023 API Layer & Runtime Contract Definition
- **요약**: 인터뷰 세션 실행을 외부에서 호출 가능한 **API 인터페이스 계층(API Layer)** 구현 및 검증 완료.
- **변경 사항**:
    - `IMH/api/` 패키지 구현
        - `schemas.py`: Request/Response 스키마 정의 (Pydantic).
        - `dependencies.py`: Dependency Injection Composition Root 구현 (Singleton Repo, Transient Service).
        - `session.py`: 세션 생성/조회/답변 API Router 구현.
        - `admin.py`: 관리자 조회 API Router 구현 (Service Layer Bypass).
    - `IMH/main.py`: FastAPI Application Bootstrap 구현.
    - `packages/imh_service/session_service.py`: `create_session_from_job` 오케스트레이션 추가 및 Config 로딩 로직 개선.
    - `packages/imh_job/repository.py`: `MemoryJobPostingRepository` 구현.
    - `packages/imh_history/repository.py`: `FileHistoryRepository` 인터페이스 정합성 보완 (`update_interview_status`, `save_interview_result` 추가).
    - `scripts/verify_task_023.py`: API 통합 검증 스크립트 작성 (Lifecycle, Concurrency, Snapshot Integrity).
- **검증 결과**:
    - `python scripts/verify_task_023.py`: **Pass**
        1. **Session Lifecycle**: 생성(APPLIED) -> 조회(IN_PROGRESS) -> 답변(IN_PROGRESS) 흐름 확인.
        2. **Snapshot**: Job Policy(Immutable) 기반 세션 Config 생성 확인.
        3. **Fail-Fast**: 동시성 제어(423 Locked) 정상 동작 확인.
        4. **Admin Read-Only**: 관리자 API 조회 정상 동작 확인.
- **주요 설계 반영**:
    - **Contract-First**: API Layer는 Service Layer의 Facade 역할만 수행하며, 로직을 직접 처리하지 않음.
    - **Strict Isolation**: Service Layer가 Repository/Engine 접근을 전담(API는 Service만 호출).
    - **Runtime Entry**: `main.py`를 통해 ASGI 호환 런타임 진입점 확보.


### TASK-023 API Layer & Runtime Contract Definition
- **요약**: 인터뷰 세션 실행을 외부에서 호출 가능한 **API 인터페이스 계층(API Layer)** 구현 및 검증 완료.
- **변경 사항**:
    - `IMH/api/` 패키지 구현
        - `schemas.py`: Request/Response 스키마 정의 (Pydantic).
        - `dependencies.py`: Dependency Injection Composition Root 구현 (Singleton Repo, Transient Service).
        - `session.py`: 세션 생성/조회/답변 API Router 구현.
        - `admin.py`: 관리자 조회 API Router 구현 (Service Layer Bypass).
    - `IMH/main.py`: FastAPI Application Bootstrap 구현.
    - `packages/imh_service/session_service.py`: `create_session_from_job` 오케스트레이션 추가 및 Config 로딩 로직 개선.
    - `packages/imh_job/repository.py`: `MemoryJobPostingRepository` 구현.
    - `packages/imh_history/repository.py`: `FileHistoryRepository` 인터페이스 정합성 보완 (`update_interview_status`, `save_interview_result` 추가).
    - `scripts/verify_task_023.py`: API 통합 검증 스크립트 작성 (Lifecycle, Concurrency, Snapshot Integrity).
- **검증 결과**:
    - `python scripts/verify_task_023.py`: **Pass**
        1. **Session Lifecycle**: 생성(APPLIED) -> 조회(IN_PROGRESS) -> 답변(IN_PROGRESS) 흐름 확인.
        2. **Snapshot**: Job Policy(Immutable) 기반 세션 Config 생성 확인.
        3. **Fail-Fast**: 동시성 제어(423 Locked) 정상 동작 확인.
        4. **Admin Read-Only**: 관리자 API 조회 정상 동작 확인.
- **주요 설계 반영**:
    - **Contract-First**: API Layer는 Service Layer의 Facade 역할만 수행하며, 로직을 직접 처리하지 않음.
    - **Strict Isolation**: Service Layer가 Repository/Engine 접근을 전담(API는 Service만 호출).
    - **Runtime Entry**: `main.py`를 통해 ASGI 호환 런타임 진입점 확보.

#### TASK-023 Hardening Patch (2026-02-13)
- **목적**: API Layer의 동시성 정책 검증 강화 및 아키텍처 위반 방지 가드레일 추가.
- **변경 사항**:
    - `scripts/verify_task_023.py`: 
        1. `test_real_parallel_execution`: `ThreadPoolExecutor` 기반 병렬 호출 테스트 추가.
           - Thread A: Lock 수동 점유 (1.0s Sleep)
           - Thread B: API 호출 -> 즉시 Fail-Fast (423) 반환 및 대기 시간 < 0.5s 검증.
        2. `test_api_guardrails`: API Router 파일(`session.py`, `admin.py`) 정적 분석 추가.
           - `packages.imh_session.engine`, `repository` 직접 Import 여부 검사.
- **검증 결과**:
    - Parallel Test: Status 423, Duration 0.0040s (No Wait Confirmed).
    - Guardrails: All Pass (No Prohibited Imports).

#### TASK-023 Hardening Patch v2 (2026-02-13)
- **목적**: 동시성 테스트의 실제 경쟁 상황 재현 및 가드레일 정적 분석 강화 (AST 기반).
- **변경 사항**:
    - `scripts/verify_task_023.py`:
        1. `test_real_parallel_execution`: 
           - **Real API Race**: `test_client`를 통한 실제 API 요청 2개 동시 실행 (ThreadPoolExecutor).
           - **Retry Loop**: 경쟁 상태가 발생할 때까지 최대 50회 반복 (Iteration 1에서 즉시 423 충돌 확인).
           - **No Manual Lock**: `cm.acquire_lock()` 직접 호출 제거, 순수 API 레벨 경쟁 검증.
        2. `test_api_guardrails`:
           - **AST Parsing**: `ast` 모듈을 사용하여 Import 구문 파싱.
           - **Robustness**: 단순 문자열 매칭 한계(alias, from-import) 극복 및 정확한 모듈 경로/클래스명 감지.
- **검증 결과**:
    - Race Condition: Iteration 1에서 충돌 발생 (Status 423/200). Fail-Fast 동작 확인.
    - AST Guardrails: All Pass.

### TASK-024 질문은행 구조 정비 (Question Bank Structure)
- **요약**: 질문 생성 실패 시 Fallback 및 정적 자산 관리를 위한 `packages/imh_qbank` 패키지 구현.
- **변경 사항**:
    - `packages/imh_qbank/domain.py`: `Question`, `SourceType`, `SourceMetadata` 정의. Soft Delete 상태(`DELETED`) 지원.
    - `packages/imh_qbank/repository.py`: `JsonFileQuestionRepository` 구현 (파일 기반 저장소).
    - `packages/imh_qbank/service.py`: `QuestionBankService` 구현 (Candidate Provider).
        - Soft Delete된 질문은 후보군(Candidates)에서 자동 제외 정책 적용.
    - `scripts/verify_task_024.py`: Soft Delete 및 Session Immutability(Edit-Tolerant, Delete-Tolerant) 검증 스크립트 작성.
- **검증 결과**:
    - `python scripts/verify_task_024.py`: **Pass**
        1. **Static Question Addition**: 저장 및 조회 성공.
        2. **Edit-Tolerant**: 질문은행 수정 시에도 세션 스냅샷(Copy) 불변성 유지 확인.
        3. **Soft Delete**: `soft_delete_question` 호출 시 Status `DELETED` 변경 확인.
        4. **Candidate Exclusion**: Soft Delete된 질문이 `get_candidates` 결과에서 제외됨 확인.
        5. **Delete-Tolerant**: 삭제 후에도 ID 기반 조회(History/Audit) 가능함 확인.
- **주요 설계 반영**:
    - **Boundaries**: Engine/Service에 대한 역방향 의존성 없음 (QBank는 수동적 Provider).
    - **Source Layer**: Static Origin과 Generated Origin을 구분 가능한 도메인 모델 적용.
    - **Policy**: Soft Delete를 기본 삭제 정책으로 채택하여 이력 추적성 확보.
- **로그 및 산출물**:
    - `packages/imh_qbank/` 패키지 신설.
    - `logs/agent/` 로그 파일 참조.

## 2026-02-13
### TASK-025 RAG Fallback 엔진 통합 (RAG Fallback Engine Integration)
- **요약**: LLM 질문 생성 실패 시 Static Question Bank로 안전하게 전환하는 3-Tier Fallback 구조를 SessionEngine 내부에 통합.
- **변경 사항**:
    - `packages/imh_session/dto.py`: `SessionQuestion` Value Object 및 `SessionQuestionType(GENERATED/STATIC)` 정의.
    - `packages/imh_providers/question.py`: `QuestionGenerator` 인터페이스 및 `MockQuestionGenerator` 구현.
    - `packages/imh_session/engine.py`: `_get_next_question()`에 3-Tier 전략 구현 (RAG → QBank → Emergency).
        - Fallback은 상태 전이를 유발하지 않음.
        - Source 타입은 Engine 내부에서만 결정.
    - `packages/imh_service/session_service.py`: QuestionGenerator / QuestionBankService 의존성 주입.
    - `scripts/verify_task_025.py`: Fallback, Snapshot Independence, Emergency 안정성 검증 스크립트 작성.
- **검증 결과**:
    - `python scripts/verify_task_025.py`: **Pass**
        1. **Normal Generation**: RAG 성공 시 Source=GENERATED 확인.
        2. **Explicit Fallback**: RAG 실패 시 Static QBank 사용 확인.
        3. **Critical Failure**: QBank 비어있는 경우 Emergency Question 반환 확인.
        4. **Snapshot Independence**: Provider/QBank 변경 이후에도 세션 내 current_question 불변 확인.
- **주요 설계 반영**:
    - **Authority**: Fallback 판단 권한은 SessionEngine 단일 주체로 고정.
    - **Contract Protection**: Freeze / Snapshot / State Contract 침범 없음.
    - **Immutability**: 질문은 Snapshot에 Value Object로 고정.
    - **Boundaries**: Provider 및 Service는 정책 판단을 수행하지 않음.
- **로그 및 산출물**:
    - Fallback 동작 및 예외 처리 로그는 `logs/runtime/`에 기록.
    - Contract Stability 검증 완료 (위반 없음).

## 2026-02-18
---

### TASK-026 PostgreSQL 영속화 전환 (PostgreSQL Persistence Migration & Write Switch)

- **요약**:  
  기존 File/Memory 기반 저장 구조를 PostgreSQL 기반 단일 영속 구조로 안전하게 전환.  
  Dual Write → Read Switch → Write Switch → Restart/Replay → Rollback 검증까지 완료.  
  현재 시스템은 PostgreSQL Primary 구조로 안정 전환된 상태.

---

## 📌 변경 사항

### 1️⃣ Checkpoint 1 – PostgreSQL Repository 구축

- `HistoryRepository`
- `SessionRepository`
- `JobRepository`

**구현 원칙**
- Repository는 Engine 로직 포함 금지 (격리 유지)
- DTO/Mapper 분리 유지
- JSON 직렬화는 `model_dump(mode="json")` 기반 처리
- Engine/PolicyEngine 호출 없음

**검증**
- `checkpoint1_test.log`: ALL PASSED
- datetime 직렬화 문제 해결

---

### 2️⃣ Checkpoint 1.5 – 통합 안전성 검증

- Freeze / Snapshot / State Contract 유지 확인
- 역직렬화 + 도메인 생성자 호출 수준에서 복원 수행
- PolicyEngine 미호출 검증

**결과**
- 통합 테스트 ALL PASSED
- 기존 계약 침범 없음

---

### 3️⃣ Checkpoint 2 – Stage 1 Dual Write 체계 확립

**구조**
- Write: Primary(File/Memory) + Secondary(PostgreSQL)
- Read: Primary만 사용
- DB 직접 조회는 검증 스크립트 전용

**Fail-Fast 정책**
- PRIMARY_SUCCESS_SECONDARY_FAIL
- SECONDARY_SUCCESS_PRIMARY_FAIL
- BOTH_FAIL

JSON 구조화 로그 기록:
- event
- case
- domain
- identifier
- timestamp
- error

**CRITICAL 보완**
- Report interview_id 단일 생성 원칙 적용
- Adapter 1회 생성 → raw_debug_info 전달 → 동일 ID 저장

**검증**
- `checkpoint2_enhanced.log`: ALL PASSED
- 회귀 테스트 통과

---

### 4️⃣ Checkpoint 3 – 기존 데이터 마이그레이션

**목표**
- File/Memory → PostgreSQL 완전 이관
- 멱등성 보장
- 100% 정합성 검증

**핵심 개선**
- JSONB 컬럼에 `json.dumps()` 저장 금지
- `set_type_codec('jsonb')` 적용
- dict 기반 저장/비교 확정

**안전 프로토콜**
- 자동 UPDATE 금지
- FK 위반 SKIP 금지
- 불일치 시 즉시 중단
- Primary를 단일 진실 원천(Source of Truth)으로 고정

**결과**
- JSONB dict 기반 저장 확정
- Primary(dict) == PostgreSQL(dict) 직접 비교 PASS
- Orphan Report 격리 및 증거 보존 완료

---

### 5️⃣ Checkpoint 4 – Read Path Switch

**Phase 4.1 – Shadow Read**
- Memory vs PostgreSQL 비교 검증
- 100% 데이터 일치 확인

**Critical Fix**
- question_history 저장 누락 버그 수정
- asyncpg connection scheme 보완

**Phase 4.2 – Canary Rollout**
- 1% 세션 Postgres Read 적용
- Deterministic Hash 기반 라우팅
- 정상/Canary 세션 분리 검증 PASS

---

### 6️⃣ Stage 3 – Write Primary Switch

- Write Primary = PostgreSQL 전환
- Memory는 Secondary로 유지
- Restart Replay PASS
- Rollback 가능성 검증 PASS

**운영 모드 확정**
- Read: PostgreSQL (100%)
- Write: PostgreSQL Primary
- Secondary Write: Memory (Dual Write 유지)

---

## 🛡 주요 설계 원칙 유지

- Engine 단일 정책 판단 구조 유지
- Freeze 계약 변경 없음
- Snapshot Double Lock 유지
- State Contract 유지
- Service/API Boundary 변경 없음
- Command/Query 분리 유지
- DTO/Mapper 분리 유지
- AST Guardrail 전제 유지

---

## 🔄 Dual Write 전략

- 즉시 제거하지 않음
- 단기 안전망으로 유지
- 제거 조건은 TASK-027 이후 별도 승인

**제거 조건**
- Redis Session Runtime State 도입 완료
- Postgres-only Loopback PASS
- Rollback/복구 전략 문서화
- question_history 무결성 재검증 PASS

---

## 📊 검증 결과 요약

- JSONB 타입 무결성 PASS
- question_history 손실 없음
- Restart Replay PASS
- Rollback Safety PASS
- Shadow/Canary/100% 전환 PASS
- 구조 계약 위반 없음

---

## 📁 로그 및 산출물

- checkpoint1_test.log
- checkpoint2_enhanced.log
- checkpoint3_completion_report.md
- checkpoint4_completion_report.md
- stage3_execution_report.md
- orphan_reports_backup/
- quarantine_manifest.json

모든 검증 스크립트 PASS 확인.

---

## 🎯 최종 상태

TASK-026은 “PostgreSQL 단일 영속 구조로의 안전 전환” 목표를 달성하였다.

Redis 도입은 TASK-027 범위이며,  
Dual Write 제거는 TASK-027 안정화 이후 수행한다.

---

## 2026-02-19

### TASK-027 / CP1 Session Projection Cache Implemented
- **요약**: Redis Session Projection Cache (CP1) 구현 완료. PostgreSQL을 Sole Authority로 유지하며, Redis는 Read-Only View(Projection)로만 사용.
- **주요 구현**:
    - `packages/imh_dto/projection.py`: UI 전용 `SessionProjectionDTO` 정의.
    - `packages/imh_session/infrastructure/redis_projection_repository.py`: Redis 접근 로직 (TTL 30m, No-Lock Stampede Strategy).
    - `packages/imh_service/mapper.py`: `to_projection_dto` 매퍼 추가.
    - `packages/imh_service/session_service.py`: `get_session_projection` (Read-Through) 및 Invalidation Logic (Invalidate-First) 통합.
- **검증 결과**:
    - `scripts/verify_cp1.py`: **Pass (4 tests)**
        1. **Cache Miss**: PG Load -> Redis Save -> Return 확인.
        2. **Cache Hit**: PG Bypass -> Redis Return 확인.
        3. **Invalidation**: Write(Submit Answer) -> Redis Key 삭제 확인.
        4. **Redis Down**: Graceful Degradation (Log Warn + PG Fallback) 확인.
- **Authority Contract 준수**:
    - Projection은 오직 UI 조회를 위해서만 사용됨.
    - Domain/Engine 로직은 Projection에 의존하지 않음 (PG Source 원칙).

---

### TASK-027 / CP2 RAG Result Cache Implemented
- **요약**: RAG Result Cache (CP2) 구현 완료. 비용/지연 최적화 목적의 Read-Only Cache이며, Authority는 PostgreSQL 유지.
- **주요 구현**:
    - `packages/imh_dto/rag_cache.py`: `RAGCacheDTO` 정의 (Value Object).
    - `packages/imh_session/infrastructure/redis_rag_repository.py`: Versioned Key 생성(`rag:{job}:{ver}:{hash}`) 및 TTL 정책(`calculate_ttl`) 구현.
    - `packages/imh_service/cached_question_generator.py`: `CachedQuestionGenerator` Decorator 구현 (Read-Through pattern, Async Save).
    - **Optimization**: `asyncio.create_task` 기반 Fire-and-Forget Save 전략 적용 (User Latency 우선).
- **검증 결과**:
    - `scripts/verify_cp2.py`: **Pass (5 tests)**
        1. **Key Determinism**: Input/Params/Version 변경 시 Key 변경 확인 (Collision Safety).
        2. **Cache Miss**: Real Generator 호출 -> Async Save 트리거 확인 (Fire-and-Forget).
        3. **Cache Hit**: Real Generator 호출 없이 Cached Content 반환 및 SessionQuestion 재구성 확인.
        4. **Redis Down**: Connection Error 시 Log Warn 후 Real Generator Fallback 확인 (Graceful Degradation).
        5. **TTL Policy**: Traffic/Mode 조건에 따른 Dynamic TTL(24h/48h/1h) 계산 로직 확인.
- **Authority Contract 준수**:
    - RAG Cache는 Engine 의사결정에 사용되지 않음.
    - Save 실패는 사용자 응답에 영향 없음 (Availability Priority).

---

#### TASK-027 / CP2 Dynamic TTL Implementation (Hardening)
- **요약**: CP2 Dynamic TTL 적용. PostgreSQL Authority 기반의 `TTLContextResolver`를 도입하여 Service Layer 침범 없이 안전하게 TTL 결정 로직 구현.
- **변경 사항**:
    - `packages/imh_service/ttl_resolver.py`: `PostgresTTLResolver` 구현 (Active Candidate Count 조회).
    - `packages/imh_service/cached_question_generator.py`: Resolver 주입 및 `calculate_ttl` 연동.
- **검증 결과**:
    - `scripts/verify_cp2.py`: **Pass (7 tests)**
        1. **High Traffic**: Active Candidate > 100 → TTL 48h (172800s) 검증.
        2. **Debug Mode**: Debug=True → TTL 1h (3600s) 검증.
        3. **Resolver Failure**: DB Error → Safe Default 24h (86400s) Fallback 검증.
- **Authority Protection**:
    - Decorator는 DB를 직접 조회하지 않고, Resolver 인터페이스를 통해 안전하게 위임.
    - Resolver는 SessionStateRepository(PG)를 사용하여 Active Count의 정합성 보장.

### TASK-027 / CP2 LOCKED (RAG Cache & Cost Optimization)
- **일자**: 2026-02-19
- **상태**: **LOCKED**
- **핵심 계약 요약**:
    - **PostgreSQL Authority**: Cache is NOT for Engine Decisions.
    - **Redis Role**: Read Optimization Only (Loss Tolerant).
    - **Immutable Key**: Versioned Key (Job+Policy+Prompt+Input) ensures correctness.
    - **No Write-Back**: Unidirectional Flow (PG -> Calc -> Redis).
    - **Safety**: Async Save (Exception Tolerant) & Graceful Fallback.
- **검증**: `scripts/verify_cp2.py` **PASS** (7 tests including Dynamic TTL)
- **감사**: `docs/TASK-027_CP2_AUDIT_REPORT.md` (Authority & Layering Compliance Verified)

