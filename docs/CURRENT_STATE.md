# CURRENT_STATE
(IMH AI 면접 시스템 – 현재 개발 상태 스냅샷)

본 문서는 AI 코딩 에이전트가 **작업을 시작할 때 반드시 먼저 읽어야 하는 문서**이다.  
에이전트는 이 문서에 적힌 내용만을 근거로 현재 상태를 판단하며, 기억·추측·자율적 확장을 해서는 안 된다.

---

## 1. 개발 실행 환경 (강제)

- Python: **3.10.11**
- Virtual Environment: **interview_env (venv)**
- 모든 실행 및 검증은 반드시 `interview_env` 활성화 상태에서 수행한다.
- 가상환경은 `C:\big20\big20_AI_Interview_System\interview_env`에 있다.
- 글로벌 Python 환경에 패키지 설치는 금지한다.

---

## 2. Phase 1 ~ Phase 10 완료 기준선

시스템은 Phase 10까지 완료되어 운영 가능한 아키텍처로 안정화된 상태이다.

### 2.1 Core & Analysis (Phase 1 ~ 4)
- Core Processing: 파일 검증, 텍스트 추출, 임베딩 파이프라인 완료.
- Analysis: 음성(Parselmouth), 얼굴(DeepFace), 시각(MediaPipe) 분석 엔진 통합 완료.
- Evaluation: 루브릭 기반 점수 산출 및 리포팅 계층(JSON) 구축 완료.

### 2.2 Session & Policy (Phase 5)
- State Contract: APPLIED -> IN_PROGRESS -> COMPLETED/INTERRUPTED -> EVALUATED 고정.
- Freeze at Publish: 공고 발행 시 정책 동결 계약 준수.
- Snapshot Double Lock: 공고 및 세션 스냅샷 기반의 정합성 확보.
- Authority: SessionEngine이 정책 판단의 유일한 권한 보유.

### 2.3 Service & API (Phase 6)
- CQRS: Command(Service)와 Query(Admin) 경로의 완전 분리.
- Boundary: API -> Service -> Engine 단일 경로 강제 및 DTO/Mapper 적용.
- Concurrency: session_id 단위 Fail-Fast 동시성 정책(Lock) 적용.

### 2.4 Question Bank & RAG (Phase 7)
- QBank Source: STATIC(Banked) 및 GENERATED(LLM) 이중 구조 확정.
- RAG Fallback: LLM 실패 시 3-Tier(RAG -> Static -> Emergency) 전략 통합 완료.
- Independence: 질문 생성 로직과 세션 스냅샷 계약의 완전 독립성 유지.

### 2.5 PostgreSQL Persistence (Phase 8)
- Authority Store: PostgreSQL이 단일 권위 저장소(Source of Truth)로 확정.
- Write Path: PostgreSQL Primary 쓰기 경로 전환 완료.
- Safety: Restart Replay 및 Rollback Safety 검증 완료.
- TASK-029 (Baseline Alignment) 완료: 테이블 네이밍(sessions->interviews, reports->evaluation_scores) 및 실제 영속 경로 정렬 완료.
- Live Persistence 및 Live Hydration 검증 통과 (scripts/verify_live_task_029.py Pass).
- Redis Miss 시 PostgreSQL Authority 복구(Hydration) 가능 상태 확정.
- Schema Fail-Fast 검증 로직 적용(init_db verify_schema 강화): 테이블 존재 + 필수 컬럼 존재까지 검증.

### 2.6 Redis Runtime & Cache (Phase 9)
- Runtime Mirror: PG 데이터를 Redis에 복제하여 런타임 제어(Lock/Idempotency) 수행.
- Read Optimization: Projection, RAG, Candidate, Prompt 캐시 구축 완료.
- Contracts: Redis는 Authority가 아니며, No Write-Back 원칙을 고수함.

### 2.7 Statistics & Observability (Phase 10)
- Track A (Business Stats): PostgreSQL Snapshot 기반 통계 및 Redis 결과 캐시 (LOCKED).
- Track B (Operational Obs): Informational 목적의 운영 관측 계층 분리 (LOCKED).
- Isolation: Heavy Query 격리를 위한 MView 전략 및 물리적 서비스 분리 검증 완료.
- Phase 10 Audit (2026-02-19): **내부 테스트 한정 운영 가능** 판정 (심층 감사 보고서 생성 완료).

### 2.8 Phase 10 Stabilization (Mini-Patch) - 진행 중
- 목표: 외부 운영 승격을 위한 핵심 계약 취약점(R-1, R-2, R-3) 보완.
- 진행 제어 (TASK-030 완료):
  - **TASK-030 (Authority First) 완료**: PostgreSQL 권위 선행 보장 및 원자적 커밋 흐름(`_atomic_commit`) 구현 완료. (R-1 제거)
    - **핵심 성과**: Authority First / Atomic Commit / Visibility Barrier / Redis Mirroring Resilience / Projection Subset 보장.
    - **검증**: `scripts/verify_task_030.py` PASS (EXIT 0, 단일 글로벌 타임라인 검증 포함).
- **TASK-035 (LLM Wiring Sprint) 완료**:
  - Status: DONE
  - Scope:
    - Weight Sync wiring (Snapshot-first, FAIL-FAST enforced)
    - PhaseManager Flow Contract runtime enforcement
    - Fixed Question insertion (verbatim, no LLM/RAG)
    - Resume Summary prompt injection (MAIN/FOLLOW_UP 조건부)
    - Unified Feature Flags (default False)
  - Verification:
    - scripts/test_035_fast_gate.py Pass (28/28)
  - Contract Compliance:
    - Snapshot Authority preserved
    - No Redis Write-Back
    - No runtime snapshot mutation
    - Deterministic distribution maintained

### 2.9 Multimodal Layer (WebRTC Real-time) - DONE LOCK
- Real-time Audio/Video ingestion
- STT (Faster-Whisper, Resident)
- Vision (MediaPipe 2-3FPS)
- Emotion (DeepFace <1FPS)
- Audio (Parselmouth window-based)
- Redis Streams (At-least-once + Idempotent DB)
- PostgreSQL multimodal_observations
- SSE Projection
- gTTS
- PDF Snapshot Integration
- GPU Mutex with Cooperative Yield
- OOM Graceful Degradation
- **Fixpack Hardening (C1-E)**: Evaluation Determinism (Input Hash), Session Abort (Terminal 409), Mode Immutability, Atomic GPU 429 (LUA).

**Contracts:**
- Authority = PostgreSQL only
- Projection = Non-authoritative
- Evaluation Integration = Deterministic Input Hash (C1)
- Terminal States = ABORTED (C2)

### 2.10 Frontend Integration (TASK-FRONT-001) - DONE
프론트엔드는 서버의 권위(Projection)를 소비하는 계층으로 구축되었으며, 아래 결정성 계약을 강제한다.
- **Authority Pull 2-Step**: 모든 세션 진입 시 Step 1(Metadata fetch) 성공 후 Step 2(Projection hydrate)를 수행한다.
- **Pull Lock SSE Suppression**: Authority Pull 진행 중 도착하는 SSE 이벤트는 폐기한다 (Stale 오염 방지).
- **Projection Full Overwrite**: 서버 Projection 수신 시 부분 병합(Merge) 없이 전체 내용을 Deep-Replace 한다.
- **Initial Hydration Guard**: 세션 생성 직후 서버가 `current_question`을 제공하기 전까지 질문 영역 DOM을 생성하지 않는다.
- **Terminal Mutation Guard**: `ABORTED/DECIDED/EVALUATED` 상태 진입 시 사용자 입력(Mutation) DOM을 즉시 제거한다.
- **GPU 429 Countdown**: GPU 큐 초과 시 Retry-After 기반 카운트다운 배너를 표시하며, 자동 재전송 없이 사용자 수동 재시도만 허용한다.
- **Capability Drift Freeze**: 세션 시작 시점의 Capability(Video, WebRTC 등)를 동결하며, 진행 중 정책 변경을 수용하지 않는다.
- **Result Visibility Guard**: ACTUAL/PRACTICE 모드에 따른 결과 노출 정책을 DOM 제거 수준에서 강제한다.
- **Admin Boundary**: 지원자(Candidate)와 관리자(Admin)의 Store를 물리적으로 분리하며, 관리자 필드가 지원자 화면에 유출되지 않도록 차단한다.
- **Stats TTL 60s**: 관리자 통계는 60초 TTL을 가지며, 만료 시 Stale 표시 및 수동 새로고침만 허용한다.
- **Admin Control Panel**: 면접관 페르소나, 고정 질문, 역량 가중치 및 기능별(RAG/Resume/MM) On/Off를 제어할 수 있는 정책 패널이 통합됨.
- **Policy Freeze UI**: 공고 게시(PUBLISHED/CLOSED) 상태에서 AI 민감 정책 필드에 대한 수정을 원천 차단하는 UI Lock 구현 완료.
- **Resume Summary Transparency**: 지원자가 본인의 이력서 분석 결과(Summary)를 직접 확인할 수 있는 데이터 투명성 패널 구현 완료.

**원칙**: 프론트엔드는 상태를 생성하거나 추측하지 않으며, 오직 서버의 권위를 소비만 한다.

---

## 3. 시스템 운영 준비 상태 (Implementation Complete / System Ready)

현재 시스템은 모든 핵심 기능 구현이 완료되었으며 운영 가능 상태로 안정화되었다.

### 3.1 Core Engine
- **InterviewSessionEngine**: 상태 전이 및 정책 오케스트레이션 안정화.
- **PhaseManager**: 면접 단계별(OPENING/MAIN/FOLLOW_UP/CLOSING) 흐름 제어.
- **EvaluationEngine**: 루브릭 기반 평가 및 결정성 해시 검증.
- **RAG Question Generation**: 질문 은행 및 LLM 기반 동적 질문 생성 통합.

### 3.2 Infrastructure
- **PostgreSQL Persistence**: 단일 권위 저장소(Source of Truth) 영속화 구조 확정.
- **Redis Runtime State**: 런타임 제어, 멱등성 보장 및 프로젝션 캐싱.
- **SSE Streaming**: 실시간 프로젝션 푸시 및 프론트엔드 동기화.

### 3.3 Multimodal
- **STT Pipeline**: Faster-Whisper 기반 고성능 음성 인식.
- **Vision Analysis Pipeline**: MediaPipe 및 DeepFace 기반 시선/감정 분석.
- **Multimodal Flags**: 정책에 따른 기능별(Audio, Video, Gaze 등) 활성화 제어.

### 3.4 Frontend
- **Admin Dashboard**: 공고 관리, 지원자 조회, 통계 및 감사 타임라인.
- **Candidate Interview Flow**: 실시간 면접 인터페이스 및 WebRTC 연동.
- **Interview Policy Panel**: AI 정책(페르소나, 질문 수, 가중치 등) 통합 제어.
- **Resume Summary Transparency**: 데이터 거버넌스 기반 이력서 요약 노출.
- **Policy Freeze UI**: 데이터 무결성 보장을 위한 정책 수정 잠금.

---

---

## 3. 확정된 핵심 계약 (변경 금지)

| 항목 | 계약 내용 | 상태 |
|---|---|---|
| PostgreSQL Authority | PostgreSQL이 유일한 권위 저장소이다. | LOCKED |
| State Transition | Engine만이 상태를 전이시킬 수 있다. | LOCKED |
| Snapshot Immutable | 스냅샷은 생성 후 데이터 수정이 불가능하다. | LOCKED |
| Redis Role | Redis는 런타임 제어 및 리드 최적화 전용이다. | LOCKED |
| No Write-Back | Redis에서 PG로의 쓰기 경로는 존재하지 않는다. | LOCKED |
| Track A/B 분리 | 통계(비즈니스)와 관측(운영)은 서로 간섭하지 않는다. | LOCKED |
| Heavy Query Isolation | 운영에 비중이 큰 쿼리는 별도 경로(MView 등)로 격리한다. | LOCKED |
| Evaluation Determinism | evaluation_input_hash 기반 결정성 평가 보장. | LOCKED |
| Session Terminal | ABORTED 상태 진입 시 재진입 원천 차단. | LOCKED |
| GPU Concurrency | Redis LUA 기반 원자적 동시성 제어. | LOCKED |
| Statistical Determinism| PG Source 기반 UTC Repeatable Read 집계. | LOCKED |
| Drift Guard | DECIDED 세션에 대한 사후 수정 시도 금지(409). | LOCKED |
| Idempotent Override | Decision Override 시 중복 trace_id 차단. | LOCKED |
| Audit Append-only | 감사 로그는 절대 수정/삭제될 수 없다. | LOCKED |

---

## 4. 패키지 및 모듈 상태

- `imh_core`: DONE (기본 설정, 에러, DTO, 전역 로깅)
- `imh_providers`: DONE (STT: Faster-Whisper-v3-turbo 확정, LLM: Ollama/OpenAI, Emotion, Visual, Voice, Embedding)
- `imh_analysis`: DONE (DeepFace, Parselmouth, MediaPipe 연동)
- `imh_eval`: DONE (루브릭 기반 평가 엔진)
- `imh_history`: DONE (리포트 저장 및 이력 관리 - PG 전환 완료)
- `imh_job`: DONE (공고 정책 엔진, Freeze/Snapshot 로직)
- `imh_session`: DONE (세션 엔진, 모드 분리, 상태 관리)
- `imh_service`: DONE (유스케이스 오케스트레이션, DTO/Mapper, Drift Guard)
- `imh_qbank`: DONE (질문은행 관리 및 RAG Fallback 통합)
- `imh_stats`: DONE (PG-authoritative 통계 및 감사 타임라인)
- `IMH/api`: DONE (런타임 진입점 및 계약 노출)

---

## 5. 현재 작업 섹션

### ACTIVE
- **Phase 5 Planning (Advanced Integrity Locks)**: [PLANNING]
  - Active Phase: Phase 5
  - System Stability Level: Enterprise-grade (Local)

### DONE
- **TASK-033 (모델 비교 및 평가 취약점 탐지)**: [DONE]
  - 4상황(S1~S4) 기반 LLM 비교 벤치마크 완료 (On-Prem 100%).
  - Llama 3.2 루프 결함 수정 및 `exaone3.5:2.4b` 메인 엔진 확정.
  - 개선된 `cookieshake/a.x (iq2_m)`를 고품질 서브 엔진으로 확보.
  - Verification: `docs/benchmarks/task_033_v2/final_report.md` Pass.

### DONE
- **TASK-031 (Snapshot Immutability)**: [DONE] L2/L3 Guards implemented & verified. strict mutability rejection (L2 & L3).
- **TASK-032 LLM & Evaluation Integration**
- Goal: `OllamaLLMProvider`와 `OpenAILLMProvider`를 시스템에 연동하고 End-to-End 질문 생성 및 루브릭 평가 파이프라인 정합성 확보.
- Scope: `packages/imh_providers/llm`, `packages/imh_providers/question.py`, `SessionService` 트랜잭션. RAG Idempotency 및 Threading 고립 적용.
- Verification: `python scripts/dev/verify_task_032.py` Pass (EXIT 0 with Threaded Idempotency Proof)
- **TASK-034 (STT 벤치마크 및 엔진 선정)**: [DONE] 
  - Faster-Whisper-v3-turbo를 공식 로컬 STT 엔진으로 확정. 
  - `initial_prompt` 기반 전문 용어(IT Key terms) 인식 최적화 완료.
  - Verification: `docs/STT_ENGINE_SELECTION_REPORT.md` (EXIT 0)
- **TASK-M (Multimodal Integration MVP)**: [DONE]
  - Sprint 1-4 완료. Fast Gate 53/53 PASS.
  - multimodal_observations 테이블 신설 및 멱등성 확보.
  - Redis Streams, GPU Mutex, STT/Vision/Emotion/Audio Workers, WebRTC API 구현 완료.
  - Verification: `scripts/verify_mm_cli.py` Pass.
- TASK-016 (TTS Provider): 스트리밍 아키텍처 연동 기능이 TASK-M에 통합되어 완료됨. (gTTS Facade)
- **TASK-FRONT-001 (Frontend Integration)**: [DONE]
  - Slice A~E 전 범위 구현 및 빌드 검증 완료.
  - 결정성 Store 및 SSE Suppression 계약 적용.
  - 관리자 통계, 감사 타임라인, 결정 Override UI 구현 완료.


---

## 6. 특이사항 및 에이전트 주의사항

0.  **HIGH_RISK (해소됨 / ARCHIVED)**: TASK-029 완료. 테이블 네이밍 불일치(sessions->interviews, reports->evaluation_scores), PostgreSQL Authority 누락(FileRepo->PostgreSQLHistoryRepository 교체), Redis Miss Hydration 부재 3종 모두 해소. Live Verification PASS. Schema Fail-Fast 적용으로 재발 방지.
0.1 **Audit Risk (2026-02-19)**: Phase 10 심층 감사 결과 5종 위험 식별.
    - R-1 (MEDIUM): 상태 저장 비원자성 (Hot -> Cold 순서)
    - R-2 (LOW): tag_code DB 레벨 제약 부재
    - R-3 (LOW): Snapshot UPSERT 갱신 경로 잔존
    - R-4 (LOW): JSONB 인덱스 미비
    - R-5 (LOW): 평가 해상도 제한 (Communication 고정치)
    - **안정화 작업 완료**: 
    - TASK-030 (Authority First) DONE
    - TASK-031 (Snapshot Immutable) DONE
    - TASK-032 (LLM & Evaluation Integration) DONE
  - PostgreSQL Authority 선행 보장 및 원자성 강화 완료 (TASK-030)
  - Redis Runtime and Cache Layer 및 통계/관측 계층 구축 완료
  - LLM Provider 통합 및 동기 평가 엔진 연동 완료 (TASK-032)
- **향후 계획**:
  - LLM 메인 엔진(`exaone`) 기반 실제 면접 데이터 축적 및 사용자 피드백 반영
  - 서브 엔진(`a.x`, `llama`)을 활용한 하이브리드 평가 로직(Cross-Evaluation) 검토
1.  **상태 표기**: 문서 내의 모든 상태는 DONE, ACTIVE, BACKLOG, HOLD, LOCKED, DISABLED 중 하나를 사용한다.
2. **이모지 금지**: 어떠한 상황에서도 문서 내에 이모지를 사용하지 않는다.
3. **PASS 기준**: Verification 결과는 반드시 `scripts/verify_task_xxx.py Pass` 형식으로 명시한다.
4. **계약 우선**: 기능 구현보다 상위 계약(Authority, Snapshot, State Contract)의 보호가 최우선이다.
5. **Playground 독립성**: Playground는 운영 흐름과 격리된 실험 영역이다. 어떠한 경우에도 Playground 로직이 Session Engine의 상태 전이(State Contract)를 호출하거나 Snapshot 데이터를 생성, 수정, 오염시켜서는 안 된다. Playground는 Redis Runtime Layer를 Authority처럼 사용해서는 안 된다.
6. **Dual Write 제거 조건**: PostgreSQL 단일 쓰기 성공 및 데이터 정합성 검증이 완료된 경우에만 메모리 Secondary 쓰기를 중단한다. 제거 이후에도 Redis에서 PostgreSQL로의 쓰기(Write-Back)는 영구 금지되며, 장애 발생 시 기존 Dual Write 경로로 즉시 복귀하는 롤백 정책을 유지한다.
제거는 반드시 신규 TASK로만 수행한다. 문서 업데이트 없이 제거를 금지한다.
