# CURRENT_STATE
(IMH AI 면접 시스템 – 현재 개발 상태 스냅샷)

본 문서는 AI 코딩 에이전트가 **작업을 시작할 때 반드시 먼저 읽어야 하는 문서**이다.  
에이전트는 이 문서에 적힌 내용만을 근거로 현재 상태를 판단하며,
기억·추측·자율적 확장을 해서는 안 된다.

## 개발 실행 환경 (강제)

- Python: **3.10.11**
- Virtual Environment: **interview_env (venv)**
- 모든 python 실행 / pip install / 검증은
  반드시 `interview_env` 활성화 상태에서 수행한다.
- 글로벌(시스템) Python 환경에 패키지 설치는 금지한다.

# 검증 상태 요약 (Phase 1 ~ Phase 7, TASK-004 ~ TASK-025)

# Phase 1 ~ Phase 4. Core Processing & Report Layer

## 1. Core Processing Layer (TASK-004 ~ TASK-011)

- 파일 검증, 텍스트 추출, 임베딩 파이프라인 정상 동작 검증 완료
- 음성 분석(Pitch/Intensity/Jitter/Shimmer/HNR) 정책 계약 동작 확인
- 얼굴 분석(MediaPipe) 및 No Face 정책 계약 동작 확인
- 루브릭 기반 점수 산출 및 직군 가중치 로직 정상 동작 확인
- 모든 검증은 Python 3.10.11 + `interview_env` 환경에서 수행됨

---

## 2. Report & Persistence Layer (TASK-013 ~ TASK-014)

- InterviewReport 파일 저장/조회/정렬 계약 동작 검증 완료
- `/reports` API 목록/상세 조회 정상 동작 확인
- DTO 직렬화 및 404 처리 계약 동작 검증 완료
- 파일 기반 메타데이터 구성 정책 유지 확인
- 저장 단위 원자성 및 정렬 기준 계약 유지 확인

---

# Phase 5. Session & Policy Engine Architecture 고정

## 3. Session & Policy Engine Layer (TASK-017 ~ TASK-019, TASK-021)

- 세션 상태 전이(APPLIED → IN_PROGRESS → COMPLETED/INTERRUPTED → EVALUATED) 계약 동작 검증 완료
- 최소 질문 수 10개 규칙 및 침묵 처리 규칙 계약 동작 검증 완료
- Actual / Practice 모드 분리 및 Resume 정책 계약 동작 검증 완료
- 공고 상태 전이(DRAFT → PUBLISHED → CLOSED) 및 Immutable Policy 계약 동작 검증 완료
- AI-Sensitive Fields 불변 계약 유지 확인

### End-to-End 통합 실행 (TASK-021)

- Job Policy Freeze at Publish 적용 확인
- Snapshot Double Lock(Job/Session) 계약 동작 검증 완료
- Snapshot 기반 질문/평가/조회 흐름 정합성 확인
- Phase 5 핵심 계약(Freeze / Snapshot / State Contract) 보호 상태 확인

---

## 4. Admin Query Layer (TASK-020)

- Active + History 통합 조회(Federated Search) 정상 동작 확인
- 필수 필터(job_id, status, result, date) 계약 준수 확인
- `result` 필터는 EVALUATED 상태에만 적용됨 검증 완료
- `is_interrupted` alias 합집합 처리 확인
- `search_keyword` 계약(2자 이상, email exact, name partial) 준수 확인
- `weakness` 필터는 Phase 7 이후로 Deferred
- Snapshot 기반 Read-Only 조회 경계 준수 확인
- Scope Lock 위반 없음 확인

📌 **Phase 5 종료 상태**
- 상태 전이 계약 고정
- Snapshot 불변성 고정
- Freeze at Publish 계약 고정
- Admin Query Read-Only 경계 확정

---

# Phase 6. Service Layer & API Boundary 확정 (TASK-022 ~ TASK-023)

## 5. Service Layer (TASK-022)

- API → Service → Engine 단일 Command 경로 강제 확인
- 상태 변경은 반드시 Engine 메서드를 통해서만 수행됨 검증 완료
- DTO ↔ Domain 완전 분리 (명시적 Mapper 적용) 확정
- Command / Query 분리(CQRS) 구조 고정
- session_id 단위 Fail-Fast 동시성 정책 적용 완료
- Admin Query는 Read-Only Query Service 경로로 분리

## 6. API Layer & Runtime Entry (TASK-023)

- API Layer는 Service Layer의 Entry Adapter로만 동작
- Engine/Repository 직접 접근 없음 (AST Guardrail 검증 완료)
- 상태 전이 / Lock 정의 / Freeze 해석을 API에서 수행하지 않음
- 병렬 요청 경쟁 시 1건 423 즉시 반환 검증 완료
- 구조 계약 위반 방지 Guardrail 확보

📌 **Phase 6 기준선**
- API ↔ Service ↔ Engine 경계 고정
- Fail-Fast 동시성 정책 확정
- 외부 런타임 진입점 안정화 완료

---

# Phase 7. Question Bank & RAG Fallback Integration

## 7. Question Bank Layer (TASK-024)

- `packages/imh_qbank` 구조 확정 (Domain / Repository / Service)
- Source 계층 정의 (STATIC / GENERATED ORIGIN)
- Soft Delete 정책 도입 (status=DELETED → 신규 세션 자동 제외)
- Snapshot과 완전 독립(Value Object) 구조 검증 완료
- Hard Delete 경로 없음 확인
- Engine/Service 경계 침범 없음 검증 완료

## 8. RAG Fallback Engine 통합 (TASK-025)

- SessionEngine 단일 판단 주체(Fallback Authority) 고정
- 3-Tier 전략 검증 완료:
  1) RAG 생성 시도
  2) Static QBank Fallback
  3) Emergency Safe Fallback
- Fallback은 상태 전이를 유발하지 않음 검증 완료
- Generated 질문은 Snapshot에 Value로 고정
- Snapshot Independence 검증 완료
- Freeze / Snapshot / State Contract 침해 없음 확인
- Contract Stability 재검증 완료

📌 **Phase 7 기준선**
- Question Source 이중 구조 안정화
- Engine 권한 단일화 유지
- Snapshot 오염 없음
- 핵심 계약(Freeze / Snapshot / State Contract) 보호 유지

---

# Phase 8. PostgreSQL 영속화 전환 완료 (TASK-026)

- Primary Data Store: PostgreSQL (Read / Write)
- Dual Write 전략 유지 (Postgres Primary + Memory Secondary)
- Restart Replay / Rollback Safety 검증 완료
- Snapshot 영속화 전략 확정
- 기존 파일 기반 구조 완전 전환 완료

📌 **Phase 8 기준선**
- PostgreSQL 단일 권위 저장소 확정
- Memory는 Secondary / Rollback Safety 용도로만 유지
- Write Path Switch 완료
- 계약 불변 유지

---

# Phase 9. Redis Introduction (Runtime & Control)

## 9. Redis Baseline (TASK-027 CP0)

- **Status**: ✅ VERIFIED / LOCKED
- **Scope**:
  - Runtime Mirror (PG → Redis 단순 복제)
  - Distributed Lock (interview_id 단위)
  - Idempotency Guard (request_id 기반)
- **Immutable Contracts**:
  - PostgreSQL Only Source of Truth
  - Write Order: PG Commit → Redis Mirror
  - No Write-Back (Redis → PG 금지)
  - Redis Down 시 Fail-Fast Reject
  - Hydration = Mirror 복원 (상태 변경 아님)
  - Pause는 Operational Flag (State Transition 아님)

📌 **Phase 9 현재 기준선**
- Redis는 Authority가 아니다.
- Redis는 Control + Runtime Layer에만 한정된다.
- Snapshot / Freeze / State Contract 침해 없음.
- Restart Replay 안전성 유지.

---

## 1. 프로젝트 목적 (확정)

- 목적: **AI 모의면접 시스템**
- 전략:
  - 1단계: **API 기반 모델로 핵심 기능을 빠르게 구현**
  - 2단계: **on-premise 모델로 교체하여 성능/비용 최적화**
- 모든 모델은 **API / Local(on-prem)** 방식으로 언제든 교체 가능하도록 추상화한다.
- 질문 생성(RAG/LLM) 또한 Provider 추상화를 통해 교체 가능하도록 설계한다.
- Engine은 정책 판단의 단일 주체이며, 외부 모델은 수동적 공급자 역할만 수행한다.

---
## 2. 현재 개발 단계

- 상태: **Phase 9 진행 중 (Redis Baseline CP0 LOCKED)**

---

### Phase 5 완료: End-to-End 실행 아키텍처 고정 (TASK-021)

- 세션 엔진 통합 완료
- Job Policy Freeze at Publish 계약 고정
- Snapshot Double Lock (Job / Session) 구조 확정
- 상태 전이(State Contract) 기반 실행 흐름 고정
- 관리자 조회 계층(Admin Query Layer) 통합 완료
- Snapshot 기반 Evaluation / Admin Query 정합성 확보

---

### Phase 6 완료: Service Layer & API Boundary 확정 (TASK-022 ~ TASK-023)

- DTO / Mapper 완전 분리
- Command / Query 분리(CQRS) 계약 고정
- Fail-Fast 동시성 정책 적용
- API → Service → Engine 단일 Command 경로 고정
- Engine 외부 정책 판단 경로 차단
- AST 기반 Guardrail 적용 완료
- Runtime Entry 경계 확정

---

### Phase 7 완료: Question Bank & RAG Fallback Integration (TASK-024 ~ TASK-025)

#### Question Bank 정비
- Source 계층 정의 (Static Origin / Generated Origin)
- Soft Delete 정책 도입
- Snapshot과 완전 독립(Value Object) 구조 확정
- Engine/Service 경계 침범 없음 검증 완료

#### RAG Fallback 통합
- SessionEngine 단일 판단 주체(Fallback Authority) 고정
- 3-Tier 전략 구현:
  1) RAG 생성
  2) Static QBank Fallback
  3) Emergency Safe Fallback
- Fallback은 상태 전이를 유발하지 않음
- Snapshot Value Object 불변성 유지
- Freeze 계약 침범 없음 확인
- Snapshot Independence 검증 완료
- Contract Stability 재검증 완료

---

### Phase 8 완료: PostgreSQL 영속화 전환 (TASK-026)

- Primary Data Store: PostgreSQL (Read / Write)
- Write Path Switch 완료 (`WRITE_PATH_PRIMARY=POSTGRES`)
- Dual Write 유지 (Postgres Primary + Memory Secondary)
- Restart Replay / Rollback Safety 검증 완료
- Snapshot 영속화 전략 확정
- 기존 File 기반 저장소 전환 완료

📌 **Phase 8 기준선**
- PostgreSQL이 단일 권위 저장소
- Memory는 Secondary / Rollback Safety 용도로만 유지
- 핵심 계약(Freeze / Snapshot / State Contract) 유지

---

# Phase 9. Redis Introduction (Runtime & Control)

## TASK-027 / CP0 (LOCKED)

- **Status**: VERIFIED → LOCKED
- **Scope**:
  - Runtime Mirror (PG → Redis 단순 복제)
  - Distributed Lock (`interview_id` 단위)
  - Idempotency Guard (`request_id` 기반)
- **Immutable Contracts**:
  - PostgreSQL Only Source of Truth
  - Write Order: PG Commit → Redis Mirror
  - No Write-Back (Redis → PG 금지)
  - Redis Down 시 Fail-Fast Reject
  - Hydration = Mirror 복원 (상태 변경 아님)
  - Pause는 Operational Flag (State Transition 아님)

📌 **Phase 9 현재 기준선**
- Redis는 Authority가 아니다.
- Redis는 Control + Runtime Layer 역할만 수행한다.
- Snapshot / Freeze / State Contract 침해 없음.
- Restart Replay / Rollback Safety 유지.

---

# 향후 단계 (NOT STARTED)

## Phase 9+: Redis Cache Extension (CP1 ~ CP4)

- CP1: Projection Cache (Session View)
- CP2: RAG Cache
- CP3: Candidate Cache
- CP4: Prompt Cache

※ 모든 확장은 CP0 불변 계약을 침해하지 않는 범위에서만 수행한다.

---

# 현재 Phase의 목적 (Phase 9)

- Redis Control Layer 안정화
- Runtime Mirror 신뢰성 확보
- Dual Write 제거 시점 판단을 위한 안전성 확보
- CP1~CP4 확장을 위한 계약 기반 마련



## 3. 확정된 핵심 방향 (변경 금지)

### 3.1 기능 우선순위 (최신 기준)

1. **Phase 2 Playground 기반 정적 파일 분석은 유지**
   - 오디오/영상 업로드 → STT / 감정 / 시선 / 음성 분석 검증
   - 문서(PDF) 업로드 → Text 추출(PDF→Text)
   - 목적: 개발/검증/테스트 하네스(Regression) 역할 유지
   - Phase 6 이후에도 독립 테스트 환경으로 유지
   - Session Engine / Snapshot 구조와 완전히 분리 유지

2. **Phase 7 완료: 질문은행 + RAG Fallback 통합 구조 확정**
   - Session Engine 단일 정책 판단 구조 유지
   - Question Source 분리 구조 확정:
     - STATIC (Question Bank)
     - GENERATED (RAG/LLM)
   - RAG 실패 시 3-Tier 전략 고정:
     1) RAG 생성 시도
     2) Static QBank Fallback
     3) Emergency Safe Fallback
   - Fallback은 상태 전이를 유발하지 않음 (State Contract 불변)
   - Generated 질문은 Snapshot에 Value Object로 고정
   - Freeze / Snapshot / State Contract 계약 침범 금지
   - Engine 외부에서 질문 Source 변경 경로 금지

3. **TTS(Text→Speech)**
   - 실시간 면접 단계의 구성요소
   - 현재는 HOLD 유지
   - 질문 생성 계층(RAG) 및 Snapshot 안정화 이후 재개
   - Engine 경계 침범 없이 Provider 방식으로 통합 예정

4. **RAG / 질문은행 / 임베딩**
   - 온프레미스 저성능 모델 보정 목적
   - 질문 품질 안정화 및 직무/공고 기반 보강
   - Phase 7에서 Fallback 구조까지 안정화 완료
   - 향후 Phase 8에서는:
     - PGVector / 외부 RAG 도입 가능
     - Engine 경계 불변 유지
   - Snapshot 계약과 충돌 금지
   - metadata는 최소 집합 유지 (Snapshot 오염 방지)

5. **UI/프론트 연동**
   - API 및 질문 생성 계층 안정화 이후 확장
   - API → Service → Engine 단일 Command 경로 유지
   - Command/Query 분리 원칙 유지
   - 상태 전이(State Contract) API 우회 금지
   - 질문 Source 조작 API 금지

---

- (세션 상태) APPLIED / IN_PROGRESS / COMPLETED / INTERRUPTED / EVALUATED
  → 기준 상태값으로 유지 (변경 금지)
  → Fallback은 해당 상태에 영향을 주지 않음

---

### 3.2 모델 구성 (현재 기준)

| 분석 항목 | 모델 | 실행 환경 |
|----------|------|-----------|
| STT | Faster-Whisper | GPU (VRAM ~1GB) |
| LLM | GPT-4o / Qwen3-4B / A.X-4.0-Light / EXAONE 7.8B / Llama3.1-KO | GPU (~4.5GB) |
| Emotion | DeepFace | CPU (1fps) |
| Visual | MediaPipe | CPU |
| Voice | Parselmouth | CPU |

※ 모델 교체 가능 (Provider 인터페이스 고정)
※ Engine은 모델에 의존하지 않음 (정책 판단 분리 유지)
※ RAG/LLM은 동기 Request/Response 방식 기준으로 통합 완료
※ Streaming 방식은 별도 Phase에서 구조 검토 후 도입

---

## 4. 저장 정책 (확정)

- ❌ 서버는 **원본 영상/오디오 파일을 장기 저장하지 않는다**
- ⭕ 저장 대상:
  - 텍스트(STT 결과)
  - 분석 결과 요약
  - 평가 점수 및 근거(JSONB)
- 목적: 보안, 비용, 법적 리스크 최소화

### 4.1 현재 저장소 상태(현행)
- 현재 활성 DB(PostgreSQL/Redis/PGVector)는 도입하지 않는다.
- 리포트/이력 저장은 파일 기반(FileHistoryRepository)으로 운영한다.
- DB 도입은 리포트 구조 및 실시간 플로우 정책이 안정화된 이후 단계에서 진행한다.
---

## 5. 데이터/설계 기준 문서 (읽기 전용)

아래 문서들은 **_refs/** 폴더에 있으며,  
구현 시 반드시 **무손실 반영**해야 한다.

1. ERD / 데이터 아키텍쳐  
   - `26.02.05(목)데이터 아키텍쳐,ERD 가이드.md`
   - 핵심:
     - `MESSAGES` 테이블 제거
     - `INTERVIEWS.chat_history (jsonb)` 통합

2. UI 설계 (최신본)
   - `26.02.06(금)AI 면접 프로그램 UI 설계 초안.md`
   - 면접 진행도(phase), 답변 완료 버튼, 관리자 UI 포함

3. 질문 태그 설계
   - `26.02.05(목)질문태그설계.md`
   - tag_code는 **문자열 식별자**, 변경/삭제 금지

4. 정량 평가 루브릭
   - `26.02.09(월)정량평가 루브릭 가이드.md`
   - 평가 JSON 스키마 고정

5. 인터뷰 정책 스펙
   - `26.02.11(수)인터뷰 정책 스펙.md`
   - 최소 질문 10개 보장
   - 침묵 2케이스 처리 정책(무응답/답변 후 침묵 구분)
   - 세션 상태 ENUM(APPLIED / IN_PROGRESS / COMPLETED / INTERRUPTED / EVALUATED)
   - 결과 공개 정책(2주 이내 합/불합 자동 통지 보장)
---

## 6. 확정된 폴더 / 모듈 구조

IMH/IMH_Interview/
├── IMH/                  # (app 대체) FastAPI 엔트리 / Router 조립
│   ├── api/
│   └── main.py
├── packages/             # 공유 가능한 핵심 로직
│   ├── imh_core/
│   ├── imh_providers/
│   ├── imh_analysis/
│   ├── imh_eval/
│   ├── imh_history/
│   ├── imh_job/
│   ├── imh_session/
│   ├── imh_service/
│   └── imh_qbank/
├── docs/                 # 운영 문서 (사람/에이전트용)
├── logs/                 # 실제 로그 파일 (.log)
│   ├── agent/
│   └── runtime/
├── _refs/                # 스펙/기준 문서 (읽기 전용)
└── scripts/


- packages/는 팀원과 공유 가능한 단위로 설계한다.
- IMH/는 실행 진입점만 담당하며 비즈니스 로직을 가지지 않는다.

### 진행 상태

- `packages/imh_core/`: ✅ DONE  
  - TASK-002 완료 (config / errors / dto)
  - 공통 로깅 기반 포함 (TASK-001)
  - TASK-026: PostgreSQL Repository 구현 및 Primary Write Path 전환 완료
  - TASK-027: Redis Control Layer 및 Runtime Mirror 도입 완료 (CP0 LOCKED)

- `packages/imh_providers/`: ✅ DONE
  - TASK-003: Provider 인터페이스 + Mock 구조 확정
  - TASK-006: PDF Local Provider 추가
  - TASK-007: Embedding Provider (Interface / Mock) 추가

- `packages/imh_analysis/`: ✅ DONE
  - TASK-008: Emotion 분석 모듈 구현 완료
  - TASK-009: Voice Provider (Parselmouth 기반 실제 구현) 추가
  - TASK-010: Visual Provider (MediaPipe 기반 실제 구현) 추가

- `packages/imh_eval/`: ✅ DONE
  - TASK-011: 정량 평가 엔진 (RubricEvaluator) 구현 완료
  - 영역별 점수 산출 로직 및 가중치 적용 검증 완료

- `packages/imh_history/`: ✅ DONE
  - TASK-013: 리포트 저장소(FileHistoryRepository) 구현 완료
  - JSON 파일 기반 영구 저장 및 이력 조회 검증 완료

- `packages/imh_job/`: ✅ DONE
  - TASK-019: 공고 정책 엔진(Job Policy Engine) 구현 완료
  - JobStatus(DRAFT/PUBLISHED/CLOSED) 전이 및 AI-Sensitive Fields 불변성 강제 검증 완료
  - Job Policy Freeze at Publish 계약 고정
  - Session Snapshot 생성 로직 구현 완료

- `packages/imh_session/`: ✅ DONE
  - TASK-017: Interview Session Engine 구현 완료
    - 상태(APPLIED / IN_PROGRESS / COMPLETED / INTERRUPTED / EVALUATED) 정의
    - 최소 질문 수(10) 및 조기 종료 정책 구현
    - 침묵 2케이스(Post-Answer / No-Answer) 처리 로직 구현
    - Redis / PostgreSQL 추상화 인터페이스 설계
    - Strict Verification Script(`verify_task_017.py`) Pass

  - TASK-018: Interview Mode Policy Split 구현 완료
    - InterviewPolicy 인터페이스 및 모드별(Actual / Practice) 구현체 정의
    - SessionConfig에 mode 추가 및 Engine 주입 로직 구현
    - 조기 종료 / 중단 / 재진입 정책 분리 검증 완료 (`verify_task_018.py`)

  - TASK-020: 관리자 지원자 조회/필터 규격 및 구현 완료
    - `ApplicantQueryService` 구현 (Active Session + History Federated Search)
    - `MemorySessionRepository` 인프라 구현 (`find_by_job_id` 지원)
    - 관리자 조회 규격(필터/정렬/페이징) 및 정책 준수 검증 완료 (`verify_task_020.py`)

  - TASK-021: End-to-End 인터뷰 실행 아키텍처 통합 구현 완료
    - Job Policy Freeze at Publish 계약 적용
    - Snapshot Double Lock 구조 구현
      - Job Policy Snapshot (Template)
      - Session Config Snapshot (Instance Deep Copy)
    - Session Engine ↔ Job Policy Engine ↔ Evaluation ↔ Admin Query 통합 흐름 구현
    - 상태 전이(State Contract) 기반 실행 흐름 검증 완료
    - Actual / Practice 모드별 중단/재진입 정책 통합 적용 검증 완료
    - Snapshot 기반 Evaluation 및 Admin Query 정합성 검증 완료 (`verify_task_021.py`)

  - TASK-022: Service Layer 및 외부 경계 통합 구현 완료
    - `SessionService` 구현 (Command 전용 유스케이스 오케스트레이션)
    - `AdminQueryService` 구현 (Read-Only Query 경로 분리)
    - API ↔ Domain 완전 격리 (DTO / 명시적 Mapper 적용)
    - Command(Lock) / Query(Bypass) 구조 분리 확정
    - session_id 단위 File/Memory Lock 기반 Fail-Fast 동시성 제어 적용
    - Engine 상태 변경은 반드시 엔진 메서드를 통해서만 수행됨 확인
    - Phase 5 계약(Freeze / Snapshot / State Contract) 훼손 없음 검증 완료 (`verify_task_022.py`)

- `packages/imh_qbank/`: ✅ DONE
  - TASK-024: 질문은행 구조 정비 완료
    - 질문 자산 관리(SourceType 분리) 및 Soft Delete 정책 구현
    - Candidate Provider 인터페이스(Service Layer 연동 준비) 구현
    - Session Immutability(Edit/Delete Tolerant) 검증 완료 (`verify_task_024.py`)
    - Engine/Service 경계 준수(단방향 의존) 확인

  - TASK-025: RAG Fallback 엔진 통합 완료
    - Session Engine 내 RAG -> Fallback -> Emergency 전략 구현
    - `QuestionGenerator` (Mock) 및 `QBankService` 통합
    - `SessionQuestion` Value Object 기반 Snapshot 불변성 보장
    - `verify_task_025.py` 검증 PASS (Success/Fallback/Critical/Snapshot 시나리오)

- `IMH/api/`: ✅ DONE
  - TASK-014: 리포트 조회 API 노출
    - 리포트 목록(List) / 상세(Detail) 조회 API 구현
    - 저장된 리포트(JSON)를 외부 소비 계층에서 조회 가능하도록 노출
    - List / Detail 데이터 노출 정책 분리
    - Read-only API 동작 검증 완료

  - TASK-023: API Layer 및 Runtime Entry 경계 확정 완료
    - API Interface Layer 구현 (Session / Admin 진입점 분리)
    - Application Bootstrap 및 Composition Root 단일 진입 경계 확정
    - API → Service → Engine 단일 Command 경로 강제 구조 유지
    - DTO ↔ Domain 완전 격리 및 명시적 Response Mapping 적용
    - API Layer에서 Engine/Repository 직접 접근 없음(AST 기반 정적 분석 검증 완료)
    - 상태 전이 판단 / Lock 정의 / Freeze 해석을 API Layer에서 수행하지 않음 검증 완료
    - 실제 병렬 API 요청 2건 경쟁 기반 Fail-Fast 동시성 정책 검증 완료 (`verify_task_023.py`)
    - AST 기반 Guardrail 적용으로 구조 계약 위반 방지 체계 확보
    - Phase 5 계약(Freeze / Snapshot / State Contract) 침범 없음 재확인

- `IMH/IMH_Interview/_refs/`: ✅ DONE
  - TASK-015: UI / Client 리포트 소비 규격 정의
    - `TASK-015_CONTRACT.md` 문서를 통해
      리포트 해석, 표현, Null 처리, 책임 경계 규칙 확정

  - 인터뷰 정책 스펙(INTERVIEW_POLICY_SPEC) 확정
    - 최소 질문 10개 보장
    - 침묵 2케이스 처리 정책
    - 세션 상태 ENUM(APPLIED / IN_PROGRESS / COMPLETED / INTERRUPTED / EVALUATED)
    - 결과 공개 정책(2주 내 합/불합 자동 통지 보장)
    - 실전 / 연습 모드 정책 분리
    - Phase 5 계약은 변경 불가 기준선으로 고정

📌 현재 상태 요약:
- Phase 1 ~ Phase 9 (CP0) 완료
- PostgreSQL Primary 전환 완료
- Redis Runtime & Control Baseline 확정 (CP0 LOCKED)
- API / Service / Engine 경계 고정
- Snapshot / Freeze / State Contract 보호 상태 유지
- Redis는 Authority가 아닌 Control + Runtime Layer로 한정
- CP1 (Projection Cache) 미시작


## 7. 로깅 / 기록 규칙 (중요)

### 7.1 에러 로그는 “진짜 로그파일(.log)”로 남긴다
- 에이전트가 개발/테스트/실행 중 발견하는 모든 에러는 **MD가 아니라 로그파일(.log)** 로 기록한다.
- 로그 위치:
  - `IMH/IMH_Interview/logs/agent/` (에이전트/개발/테스트)
  - `IMH/IMH_Interview/logs/runtime/` (API 서버 런타임)

### 7.2 MD 문서는 “사람이 읽는 요약”만 남긴다
- `docs/DEV_LOG.md`에는 아래만 남긴다.
  - 변경 요약(무엇을/왜)
  - 테스트 방법(재현 커맨드)
  - 에러 요약 + **해당 로그파일 경로**
- 상세 스택트레이스/긴 로그는 **항상 .log 파일**에 남긴다.

### 7.3 로그에 포함되어야 할 필드(권장)
- timestamp, level, logger_name, file:line, message
- (가능하면) request_id, user_id(또는 session_id), latency_ms

### 7.4 로그에 절대 포함하면 안 되는 것(금지)
- 사용자 개인정보(PII)
- 인증 토큰/키/API Key
- 원문 대화 전체(민감정보/용량/정책 이슈)
- 업로드 파일의 원문 전체(필요 시 요약/해시/메타데이터만)

---

## 8. 변경 승인 규칙 (강제)

### 8.1 Plan → Approval → Implement
에이전트는 아래 순서를 반드시 지킨다.

1) **Plan(변경 제안서) 작성**
- 어떤 파일을 만들거나 수정할지
- 왜 필요한지
- 무엇을 추가/변경/삭제하는지
- 영향 범위(API/패키지/테스트/환경)
- 롤백 방법

2) **사용자(프로젝트 오너) 허락을 받은 뒤에만 구현**
- 허락 전에는 코드 생성/수정/대규모 diff 출력 금지

3) **구현 후 기록**
- `docs/DEV_LOG.md` 업데이트(요약/테스트/로그 경로)

---

## 9. 지금 당장 하면 안 되는 것 (중요)

아래 항목은 현재 단계(Phase 7 완료 → 구조 안정화 단계)에서 **명시적으로 금지**한다.

- DB 마이그레이션/스키마 확정(ERD 반영 구현 포함)  
  → Phase 8에서 별도 계약 하에 진행
- 실시간 면접의 네트워크/스트리밍 인프라 구현(WebRTC/저지연 스트리밍 파이프라인)
- LLM 평가 엔진의 대규모 재구현(루브릭/스코어링 로직 재설계)
- 신규 도메인 확장 목적의 엔드포인트 대량 생성 (Phase 6 범위 외 기능 확장 금지)
- 프론트/UI 개발(대시보드/관리자 화면 포함)
- Streaming 기반 LLM 구조 전환(Async/WebSocket 전환 포함)
- Phase 5에서 확정된 상태 ENUM / Snapshot 계약 / Freeze 계약 변경
- TASK-022에서 확정된 Service Layer 구조(명령/조회 분리, DTO 격리, Lock 정책) 변경
- Engine 단일 정책 판단 구조 변경
- Question Source 구조(STATIC / GENERATED) 변경
- Generated 질문의 Session-local 자산 정책 변경
- Fallback 3-Tier 전략 변경

> 현재는 “RAG Fallback 구조 안정화 및 계약 보호 단계”이며,  
> 핵심 정책/상태/스냅샷/엔진 경계 계약은 변경하지 않는다.

---

## 10. 현재 최우선 목표

## ACTIVE

### Phase 9 안정화 (Redis Baseline 확정 이후)

- Redis Control Layer 안정성 재검증
- Distributed Lock / Idempotency Guard 실환경 시나리오 점검
- Hydration 신뢰성 검증 (Flush / 장애 / 재기동 상황)
- Dual Write 제거 시점 판단을 위한 안정성 데이터 수집
- CP0 불변 계약 침해 여부 지속 모니터링

📌 현재 기준:
- PostgreSQL = 단일 Source of Truth
- Redis = Control + Runtime Mirror + Read Optimization Caches (CP1/CP2)
- Write Order = PG → Redis (절대 순서 유지)
- No Write-Back (Redis → PG 금지)

---

## Active Phase 9 Implementation

### TASK-027 / CP1: Projection Cache Implemented (LOCKED)
- **Goal**: Redis Session View Projection 구축
- **Status**: ✅ LOCKED (Verified & Frozen)
- **Outcome**: 
  - `SessionProjectionDTO` 정의 및 Redis Repo 구현
  - `get_session_projection` Read-Through 전략 적용
  - `Invalidate-First` 정책 준수 확인
  - Redis Down 검증 완료
  - PostgreSQL Authority 유지 (Projection은 Derived View)
  - **Restriction**: CP2~CP4 작업 진행 중 CP1 구조 변경 금지.

---

### TASK-027 / CP2: RAG Cache Implemented (LOCKED)
- **Goal**: 비용 최적화 및 Latency 단축
- **Status**: ✅ LOCKED (Verified & Frozen)
- **Outcome**: 
  - `RAGCacheDTO` 정의 및 `RedisRAGRepository` 구현
  - `CachedQuestionGenerator` Read-Through Decorator 적용
  - Async Save & Graceful Fallback 구현
  - Versioned Key & Dynamic TTL (`TTLContextResolver`) 적용 완료
  - Cache Hit 시 SessionQuestion 재구성 (새 ID / SourceType / cached metadata)
  - **Audit**: `docs/TASK-027_CP2_AUDIT_REPORT.md` Pass

  - **Immutable Contracts**:
    - **PG Authority**: Cache is NOT Logic Decision Source
    - **Redis Role**: Read Optimization Only
    - **Write Flow**: No Write-Back to PG
    - **Safety**: Async Save & Graceful Degradation
    - **Key Integrity**: 결과에 영향 주는 파라미터는 반드시 Key에 포함 (축소 금지)

---

## Next Approval Target (Phase 9 확장 단계)

### TASK-027 / CP3: Candidate Pool Cache (Planned)
- **Goal**: 질문 생성 후보군(Candidates) 캐싱
- **Scope**: 
  - `get_candidates` 최적화
  - QBank Soft Delete 반영 전략
- **Status**: Not Started



---

## HOLD

### TASK-016 TTS Provider (Text → Speech)

- **Goal**:
  - AI 면접 질문을 음성(TTS)으로 출력하기 위한 Provider 계층 준비
- **보류 사유**:
  - Runtime 안정화(Phase 9 CP0) 우선
  - Projection/Cache 전략(CP1~CP4) 구조 확정 전에는 출력 계층 확장 보류
- **재개 조건**:
  - Redis 확장 단계(CP1~CP2) 안정화
  - 세션 상태 관리 구조 장기 안정성 검증 완료
  - Streaming 전략 별도 승인 후 진행
