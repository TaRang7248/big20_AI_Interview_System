# PROJECT_RUNTIME_SNAPSHOT.md

이 문서는 IMH AI 면접 시스템의 **절대 기준 상태(Single Source of Context)**를 정의한다. 
에이전트 및 개발자는 이 문서에 명시된 구조와 계약을 준수해야 하며, 추측에 기반한 확장을 금지한다.

---

### Active Runtime Components

- **Ollama LLM**: `exaone3.5:2.4b` (Main Reasoning)
- **Faster-Whisper**: GPU Resident (v3-turbo)
- **Redis**: Streams (MM Data) + Pub/Sub (SSE) + Mutex (GPU/Concurrent)
- **PostgreSQL**: Authority Persistence
- **CPU Workers**: Vision (MediaPipe), Emotion (DeepFace), Audio (Parselmouth)
- **SSE Broadcaster**: Real-time Projection push
- **WebRTC Signaling**: SDP Offer/Answer Endpoint
- **Capability Gating**: `video_enabled=false`, `webrtc_enabled=false` (Default OFF)

### Runtime Constraints

- **Hardware**: GTX 1660 Super 6GB
- **Concurrency**: Max 5 concurrent sessions (GPU Mutex LUA Guard)
- **GPU 429 Policy**:
  - Atomic `INCR` via Redis LUA script (Limit=5).
  - Rollback `DECR` on failure (try/finally).
  - Header: `Retry-After: 30`, `X-Error-Code: E_GPU_QUEUE_LIMIT`.
- **Session Terminal (Abort)**:
  - Terminal Status: `ABORTED`.
  - Re-entry Guard: `409 Conflict` (E_SESSION_TERMINAL).
- **Mode Immutability**:
  - `interview_mode` is immutable after session status leaves `APPLIED`.
  - Violations: `409 Conflict` (E_MODE_IMMUTABLE).
- **Evaluation Determinism (C1)**:
  - `evaluation_input_hash` is the single source of truth for evaluation identity.
  - Inputs: Context History, stt_snapshot_hash, resume/policy hashes.
  - STT Rule: Raw transcripts must be disposed immediately after hashing.
- **Redis Streams**: `MAXLEN ~10,000` per session
- **Persistence**: 5-min temp TTL for buffers
- **GPU Mutex**: STT Yield to LLM, Soft Degrade after 3 failures
- **Neutral Default**: 0.5 for all normalized metrics
- **STT Privacy**: Raw text excluded from DB (Projection only, masked)

---

# 2. 현재 활성화된 AI 파이프라인

## 2.1 LLM 면접 파이프라인
- **질문 생성**: STATIC(Banked) + GENERATED(LLM) 하이브리드. RAG Fallback 적용.
- **RAG 적용**: `imh_qbank` 내 Vector DB(pgvector) 기반 유사 질문 탐색 및 Context 주입.
- **Fallback**: LLM 실패 시 `Static -> Emergency` 순차적 폴백 트리거.
- **Persona**: `interviews` 테이블의 `persona` 컬럼 및 공고 정책(`JobPolicy`)에 기반함.
- **Prompt**: `imh_service/prompt/` 내 템플릿화되어 관리됨.
- **동기/비동기**: API 응답은 비동기이나, 내부 LLM 요청은 `idempotency` 제어 하에 동기적 처리 흐름을 가짐.
- **Wiring Layer (TASK-035)**:
  - Snapshot-first weight evaluation (Fail-Fast on mismatch)
  - Phase-governed step sequencing (OPENING → MAIN → FOLLOW_UP → CLOSING)
  - Deterministic Fixed Question override (no LLM/RAG)
  - Resume summary conditional prompt injection
  - Feature-Flag controlled activation (default OFF)

## 2.2 평가 루브릭 연결 상태
- **태그 체계**: `capability.knowledge`, `capability.problem_solving`, `capability.communication`, `capability.attitude` 4종.
- **정량 루브릭**: `rules.py` 내 점수 산출 로직 확정 (1~5점 척도).
- **evidence_data**: `evaluation_scores` 테이블의 `evidence_message_ids` (JSONB)에 저장.
- **PostgreSQL 연동**: 평가 결과는 `interview_evaluations` 및 `evaluation_scores`에 즉시 영속화.

## 2.3 STT 상태
- **모델**: **Faster-Whisper-v3-turbo** (최종 확정).
- **Streaming**: 현재 File-based Transcribe 방식 (스트리밍 미적용).
- **기술 용어**: `initial_prompt`에 IT 핵심 키워드 주입하여 인식률 강화.
- **환각 문제**: VAD(Voice Activity Detection) 및 Temperature=0 설정을 통해 통제 시도 중.

## 2.4 Vision / Emotion 상태
- **DeepFace / Parselmouth / MediaPipe** 엔진 패키지화 완료 (`imh_analysis`).
- **상태**: 로직은 존재하나 평가 엔진(`imh_eval`)에서는 현재 Gaze/Emotion 추출 후 가중치 합산 방식의 **일부 Placeholder/Mock 기반 작동**.

---

# 3. 데이터 저장 구조 확정 상태

## PostgreSQL (Authority Store)
- **interviews**: 세션 기본 정보 및 상태 통합 관리.
- **interview_evaluations**: 면접 결과 요약 및 최종 결정.
- **evaluation_scores**: 루브릭 기반 영역별 점수 (Authority).
- **messages**: 면접 전체 대화 이력 (Question/Answer).
- **questions**: 질문 은행 및 임베딩 데이터.

## Redis (Runtime / Projection)
- **Runtime Mirror**: `session:runtime:{id}` (PG 데이터 복제본, TTL 30분).
- **Projection**: `session:projection:{id}` (Read-Only 최적화 데이터).
- **Concurrency**: `lock:session:{id}` (Fail-Fast 락).
- **Idempotency**: `idempotency:{request_id}` (API 중복 실행 방지).

### Phase 4: Stats Engine Runtime Policy (Locked)
- **Scope**: DECIDED + EVALUATIVE only (물리적 격리).
- **Time Basis**: UTC `decided_at` 기준 집계 및 Rebuild 가능성 확보.
- **Isolation**: `REPEATABLE READ` 트랜잭션 (집계 일관성 보장).
- **Cache**: Redis TTL 60s, `job_id` + `month_bucket` scope invalidation.
- **Drift Guard**: 사후 수정 시도 시 HTTP 409 (E_LATE_MUTATION_FORBIDDEN) 반환.
- **Full Rebuild**: PostgreSQL 원본 데이터로부터 완전 재생성 보장 (PG-Only).

### Phase 4: Audit Runtime Policy (Locked)
- **Source**: PostgreSQL append-only (`session_audit_events`).
- **Events**: Created, Submitted, Started, Completed, Aborted, Decided, Overridden.
- **Idempotency**: `DECISION_MADE` unique per session (DB Index).
- **Override**: `DECISION_OVERRIDDEN` append-only correction (trace_id unique).
- **Consistency**: Audit DECISION_MADE count == Stats count 교차 검증 (35/35 PASS).

---

# 4. 현재 기술 부채 (Technical Debt)

- **R-5 (Comm. Eval)**: 의사소통 평가(`capability.communication`)가 현재 STAR 구조 유무에 따른 고정치(3/5점)만 부여함.
- **TTS**: 스트리밍 연동 로직 부재로 인해 현재 HOLD 상태.

---

# 5. 다음 고도화 대상 후보 정리

1. **LLM 고도화**: `exaone3.5` 외 하이브리드 평가 로직(Cross-Evaluation) 도입.
2. **멀티모달 통합**: 실시간 분석 데이터를 평가 엔진에 100% 반영 (Placeholder 제거).
3. **프론트엔드 연동**: WebSocket 기반 실시간 인터페이스 구축.
4. **부하 테스트**: Redis Mirroring 및 Lock 경합 상황에서의 병목 측정.

---

# 6. 절대 변경 금지 계약 목록 (LOCKED)

1. **PostgreSQL Authority**: 모든 상태의 유일한 권위는 PostgreSQL이다.
2. **Snapshot Immutable**: 발행된 공고 정책 및 완료된 평가 데이터는 절대 수정될 수 없다.
3. **No Write-Back**: Redis에서 PostgreSQL로의 쓰기 경로는 존재할 수 없다. (Mirroring Only)
4. **State Contract**: 세션 상태 전이는 오직 `InterviewSessionEngine`을 통해서만 발생한다.

---

# 7. LLM / STT / 모델 목록 명시

- **LLM**: `exaone3.5:2.4b` (Main), `cookieshake/a.x-iq2_m` (Sub/High-Quality).
- **STT**: `Faster-Whisper-v3-turbo` (Local).
- **Embedding**: `text-embedding-3-small` (OpenAI) 또는 `bge-m3` (Local 후보).
- **On-Prem**: Ollama 기반 로컬 추론 우선 원칙.

---

# 8. 현재 완성도 등급 (자체 평가)

- **기능 완성도**: 85% (멀티모달 통합 및 TTS 제외 완료)
- **안정성 수준**: Beta (내부 테스트 가능, TASK-030/031로 핵심 계약 보호 강화)
- **외부 운영 가능 여부**: 불가 (운영 관측성 및 보안 강화 필요)
- **멀티모달 준비도**: 60% (분석 엔진은 완료, 평가 반영 고도화 필요)
