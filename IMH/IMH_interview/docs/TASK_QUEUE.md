# TASK_QUEUE
(IMH AI 면접 시스템 – 에이전트 작업 통제 큐)

본 문서는 AI 코딩 에이전트가 **현재 시점에 수행해도 되는 작업만을 명시**한다.  
에이전트는 ACTIVE 상태의 TASK만 수행 가능하며,  
그 외 작업은 절대 착수해서는 안 된다.

---

## 상태 정의
- BACKLOG : 대기 (착수 금지)
- ACTIVE  : 현재 허용 (에이전트 착수 가능)
- DONE    : 완료
- HOLD    : 보류 (조건 충족 전까지 착수 금지)
- LOCKED  : 계약 확정 및 변경 불가 상태
- DISABLED: 비활성화 (사용 안 함)

---
## DONE

### TASK-001 로깅 기반 구축 (Phase 0)
- Goal: 개발/테스트/런타임 중 발생하는 모든 에러가 반드시 파일 로그(.log)로 남는 기반을 구축한다.
- Scope:
  - IMH/IMH_Interview/logs/agent/ 폴더 생성
  - IMH/IMH_Interview/logs/runtime/ 폴더 생성
  - 공통 로거 유틸 설계 (Rotating / Error 분리)
  - logger.exception() 사용 규칙 정립
- Verification: python scripts/check_logging.py Pass

---

### TASK-002 imh_core 최소 패키지 구성 (Phase 1)
- Goal: config / errors / dto 최소 코어 확정 및 구현
- Scope: packages/imh_core/{config.py, errors.py, dto.py}
- Verification: python scripts/verify_task_002.py Pass

---

### TASK-003 Provider 인터페이스 + Mock 구현
- Goal: 각 분석 모듈의 인터페이스 정의 및 Mock 구현체 작성
- Scope: STT / LLM / Emotion / Visual / Voice 인터페이스 및 Mock 구현
- Verification: python scripts/verify_task_003.py Pass

---

### TASK-004 FastAPI 최소 엔트리 + healthcheck
- Goal: FastAPI 기반 엔트리 구축 및 헬스체크 구현
- Scope: /health 단일 엔드포인트 구현
- Verification: python scripts/verify_task_004.py Pass

---

### TASK-005 Playground STT (파일 업로드)
- Goal: Mock STT Provider 기반 파일 업로드 및 분석 API 구현
- Scope: POST /api/v1/playground/stt
- Verification: python scripts/verify_task_005.py Pass

---

### TASK-006 Playground PDF → Text (문서 업로드)
- Goal: PDF 업로드 → 텍스트 추출 Playground 파이프라인 검증
- Scope: PDF 파일 업로드 및 텍스트 추출 결과 반환
- Verification: python scripts/verify_task_006.py Pass

---

### TASK-007 Playground Embedding → Query Focus
- Goal: 검색(RAG) 용도로 사용되는 Query Text를 임베딩 벡터로 변환하는 Playground 파이프라인 검증
- Scope: Query Text → Embedding 변환 및 Mock 기반 검증
- Verification: python scripts/verify_task_007.py Pass

---

### TASK-008 Emotion 분석 (DeepFace, 1fps)
- Goal: DeepFace 기반 감정 분석 파이프라인 검증
- Scope: 이미지/비디오 기반 분석 및 1fps 샘플링 적용
- Verification: python scripts/verify_task_008.py Pass

---

### TASK-009 Voice 분석 (Parselmouth)
- Goal: Parselmouth 기반 음성 분석 파이프라인 검증
- Scope: 오디오 파일 기반 분석 및 음향 지표 추출
- Verification: python scripts/verify_task_009.py Pass

---

### TASK-010 Visual 분석 (MediaPipe)
- Goal: MediaPipe 기반 시각 분석 파이프라인 검증
- Scope: 얼굴 검출, 시선 및 자세 정보 추출
- Verification: python scripts/verify_task_010.py Pass

---

### TASK-011 정량 평가 엔진 (루브릭 기반)
- Goal: Mock Provider / Analysis Result 기반 정량 평가 로직 검증
- Scope: packages/imh_eval Rule-based 평가 로직 구현
- Verification: python scripts/verify_task_011.py Pass

---

### TASK-012 평가 결과 리포팅 / 해석 계층 설계 (Reporting Layer)
- Goal: EvaluationResult를 InterviewReport(JSON)로 변환하는 계층 구축
- Scope: packages/imh_report 구현 및 매핑 로직 구축
- Verification: python scripts/verify_task_012.py Pass

---

### TASK-013 리포트 저장 / 이력 관리 (Persistence & History)
- Goal: 생성된 InterviewReport 보존 및 조회 계층 구축
- Scope: 파일 기반 HistoryRepository 구현
- Verification: python scripts/verify_task_013.py Pass

---

### TASK-014 리포트 조회 API 노출 (Report API Contract)
- Goal: InterviewReport 조회 전용 API 계약 정의 및 노출
- Scope: 단건/목록 조회 API 계약 및 응답 스키마 고정
- Verification: python scripts/verify_task_014.py Pass

---

### TASK-015 리포트 소비 규격 정의 (UI / Client Contract)
- Goal: InterviewReport JSON 해석 및 표현 규격 확정
- Scope: UI 표현 규칙 및 시각화 요소 사용 규칙 정의
- Verification: (Contract Document Only) Pass

---

### TASK-017 Interview Session Engine (실시간 면접 세션 엔진)
- Goal: 세션 엔진 정의 및 정책 기반 오케스트레이션 구현
- Scope: 상태 전이 정의(APPLIED -> IN_PROGRESS -> COMPLETED) 및 질문 진행 규칙 반영
- Verification: python scripts/verify_task_017.py Pass

---

### TASK-018 실전/연습 모드 분리 (Interview Mode Policy Split)
- Goal: 실전 면접과 AI 면접 연습의 정책 분리
- Scope: 모드별 중단/복구 및 결과 노출 정책 반영
- Verification: python scripts/verify_task_018.py Pass

---

### TASK-019 공고(채용) 정책 엔진 (Job Posting Policy Engine)
- Goal: 공고별 설정 옵션이 면접 진행 정책에 반영되도록 구현
- Scope: 공고별 설정 항목 정의 및 정책 반영 (침묵 시간 등)
- Verification: python scripts/verify_task_019.py Pass

---

### TASK-020 관리자 지원자 조회/필터 규격 (Admin Applicant Filtering)
- Goal: 관리자용 지원자 탐색/분류 필터 기준 확정 및 구현
- Scope: 날짜, 상태, 합불 등 필수 필터 구현
- Verification: python scripts/verify_task_020.py Pass

---

### TASK-021 세션 중단 표기/처리 규격 (Interrupt Handling & Visibility)
- Goal: 중단 처리를 일관되게 종료 상태로 반영하고 관리자 조회 규격 확정
- Scope: INTERRUPTED 종료 처리 및 관리자 조회 플래그 반영
- Verification: python scripts/verify_task_021.py Pass

---

### TASK-022 서비스 레이어 및 DTO 구현 (Service Layer & Integration)
- Goal: API와 도메인 계층을 중재하는 Service Layer 구현
- Scope: packages/imh_service 및 DTO/Mapper 구현
- Verification: python scripts/verify_task_022.py Pass

---

### TASK-023 API 레이어 구현 및 연동 (API Layer Implementation)
- Goal: Service Layer를 호출하는 FastAPI 엔드포인트 구현
- Scope: IMH/api/{session.py, admin.py} 구현
- Verification: python scripts/verify_task_023.py Pass

---

### TASK-024 질문은행 구조 정비 (Question Bank Structure)
- Goal: 정적/동적 질문은행 구조 정비
- Scope: packages/imh_qbank 패키지 신설 및 출처 계층 정의
- Verification: python scripts/verify_task_024.py Pass

---

### TASK-025 RAG Fallback 엔진 통합
- Goal: LLM 질문 생성 실패 시 질문은행을 Fallback으로 사용하도록 통합
- Scope: RAG 기반 유사 질문 검색 및 Fallback 트리거 정책 정의
- Verification: python scripts/verify_task_025.py Pass

---

### TASK-026 PostgreSQL 도입 (공고/세션/평가 영속화)
- Goal: 파일 기반 저장 구조를 PostgreSQL로 전환
- Scope: 스키마 적용 및 Write Path Switch (Memory -> PostgreSQL)
- Verification: python scripts/verify_migration.py Pass

---

### TASK-027 Redis 세션 상태 및 캐시 계층 도입 (Checkpoint 0~4)
- Goal: 실시간 세션 상태 관리 및 각 단계별 캐시 계층 구축
- Status: DONE / LOCKED

- [CP0: Baseline Runtime Layer]
  - Scope: Runtime Mirror, Distributed Lock, Idempotency Guard
  - Status: LOCKED
  - Verification: python scripts/verify_task_027.py Pass

- [CP1: Projection Cache]
  - Scope: SessionProjectionDTO, RedisProjectionRepository
  - Status: LOCKED
  - Verification: python scripts/verify_cp1.py Pass

- [CP2: RAG Cache]
  - Scope: RAGCacheDTO, RedisRAGRepository, Async Save
  - Status: LOCKED
  - Verification: python scripts/verify_cp2.py Pass

- [CP3: Candidate Pool Cache]
  - Scope: Candidate Entity/List Cache, Invalidate-on Save
  - Status: LOCKED
  - Verification: python scripts/verify_task_027_cp3.py Pass

- [CP4: Prompt Composition Cache]
  - Scope: Redis Prompt Repository, CachedPromptComposer, Max Size Limit
  - Status: LOCKED
  - Verification: python scripts/verify_task_027_cp4.py Pass

---

### TASK-028 관리자 통계 및 운영 관측 계층 설계 (Phase 10)
- Goal: 통계 시각화 및 운영 관측(Observability) 강화
- Status: DONE / LOCKED

- [CP0: Business Statistics MVP]
  - Scope: Track A (Business Stats), Real-time & Period Aggregation
  - Status: LOCKED
  - Verification: python scripts/verify_task_028_cp0.py Pass

- [CP1: Operational Observability]
  - Scope: Track B (Operational Observability), MView Isolation, Log Integration
  - Status: LOCKED
  - Verification: python scripts/verify_task_028_cp1.py Pass

---

### TASK-029 시스템 기준선 합치 및 아키텍처 보호 강화 (Baseline Alignment)
- Goal: Playbook/ERD 기준으로 DB 스키마, Repository SQL, DI, Engine Hydration 정렬
- Status: DONE
- 수행 내역:
  - 테이블 네이밍 정렬: sessions -> interviews, reports -> evaluation_scores (RENAME, 데이터 보존)
  - PostgreSQLHistoryRepository 주입 고정 (DI 교체, PG 미설정 시 FileHistoryRepository fallback)
  - Redis Miss 시 PostgreSQL Authority 복구 Hydration 로직 구현
  - Schema Fail-Fast 적용: init_db verify_schema가 테이블 + 필수 컬럼 존재까지 검증
- Verification:
  - python scripts/verify_task_029.py Pass (4종 정적 검증)
  - python scripts/verify_live_task_029.py Pass (Live Persistence/Hydration 실 DB 검증)

---

### TASK-030 상태 저장 원자성 및 PostgreSQL 권위 선행 보장
- Goal: PostgreSQL 쓰기 성공이 Hot Storage 반영보다 선행되도록 정렬하여 Authority 정합성 강화 (R-1 대응)
- Scope: `InterviewSessionEngine` 원자적 커밋 흐름(`_atomic_commit`) 및 저장 순서 정비
- Verification: python scripts/verify_task_030.py Pass (EXIT 0)

---

### TASK-032 LLM & Evaluation Integration
- Goal: `OllamaLLMProvider`와 `OpenAILLMProvider`를 시스템에 연동하고 End-to-End 질문 생성 및 루브릭 평가 파이프라인 정합성 확보.
- Scope: `packages/imh_providers/llm`, `packages/imh_providers/question.py`, `SessionService` 트랜잭션. RAG Idempotency 및 Threading 고립 적용.
- Verification: `python scripts/dev/verify_task_032.py` Pass (EXIT 0 with Threaded Idempotency Proof)

---

### TASK-035 LLM Wiring Sprint
- Goal: Task-034 정책 모듈을 SessionEngine 및 EvaluationEngine에 Wiring
- Scope:
  - Evaluation Weight Sync (Fail-Fast)
  - Phase Flow Contract Enforcement
  - Fixed Question insertion
  - Resume Summary Injection
  - Unified Feature Flags
- Verification:
  - python scripts/test_035_fast_gate.py Pass (28/28)
- Status: DONE

---

## 2.2 Phase 10 Stabilization (ACTIVE)

### TASK-033 모델 비교 및 평가 취약점 탐지 테스트 파이프라인
- Goal: 4상황(S1~S4) 자동 생성 및 메인/Fallback LLM 성능 검증, 프롬프트/평가 취약점(Drill-down, 오염, 환각 등) 탐지 파이프라인 구축.
- Scope: `scripts/benchmark_task_033_v2.py` 구현 및 On-Prem 모델 벤치마크 수행.
- Status: DONE
- Verification: docs/benchmarks/task_033_v2/final_report.md Pass

---

---


---

### TASK-032 tag_code 허용 값 제약 및 무결성 강화
- Purpose: 평가 태그(tag_code)가 정의된 범위를 벗어나지 않도록 DB 및 로직 레벨에서 무결성 강제 (R-2 대응)
- Scope: `evaluation_scores` 테이블 스키마 및 `RubricEvaluator` 검증 로직
- Acceptance Criteria:
  - `evaluation_scores` 테이블에 `tag_code` 제약(CHECK/FK/ENUM 등) 반영
  - 허용되지 않은 `tag_code` 저장 시도 시 에러 반환 검증
  - python scripts/verify_task_032.py Pass
- Status: BACKLOG

### TASK-M-FIX: Phase 3 Stability & Determinism Fixpack
- Goal: Phase 3 감사 결함(C1-C3) 해결 및 GPU 429 원자성 확보.
- Scope:
    - evaluation_input_hash + STT snapshot hash (Determinism)
    - Blind Mode audio fail Abort 처리 (Authority)
    - interview_mode immutability 409 가드 (Contract)
    - GPU 429 Redis INCR 원자성 개선 (Atomic)
- Verification: scripts/verify_fixpack.py Pass
- Status: DONE

---

## ACTIVE

### PHASE-4-PLAN: Statistical + Audit Hardening
- Goal: PG-authoritative 통계 대시보드 및 관리자 감사 타임라인 설계 및 구현.
- Status: DONE
- Verification: scripts/verify_phase4_contracts.py Pass (35/35 PASS)
- Slices:
  - Slice 1: Aggregate Stats Service (PG-Only) - DONE
  - Slice 2: Rebuild & Idempotency Safety - DONE
  - Slice 3: Audit Timeline & Wiring - DONE
  - Slice 4: Drift Guard & Decision Override - DONE

---

### Phase 5: Planning (ACTIVE)

#### TASK-Phase5-PLAN: Advanced Integrity Locks
- Goal: Enterprise-grade 시스템 안정성 및 무결성 강화 가드 설계.
- Status: ACTIVE
- Scope: Plan Only

---

### TASK-FRONT-001: WebRTC Frontend MVP 구현
- Goal: 백엔드 멀티모달 및 관리자 API를 소비하는 프론트엔드 연동 개발.
- Status: DONE
- Scope:
    - Authority Pull 2-Step Protocol 구현 (Store Sync)
    - Multimodal (Video/Gaze/Emotion) Projection 연동
    - Result Screen (Actual/Practice 정책 반영)
    - Admin Views (Audit Timeline, Decision Override)
    - Admin Stats (TTL 60s, Job Stats Dashboard)
- Verification: npm run build Pass & Slice A-E 수동 검증 통과

---

## NEXT

### TASK-QA-001: 시스템 통합 테스트 및 리그레션 검증
- Goal: 프론트 통합 이후 전체 사용자 시나리오(V1-V6) 및 관리자 운영 흐름 검증.
- Scope:
    - ACTUAL/PRACTICE 모드별 End-to-End 테스트
    - 네트워크 지연/단절 시 SAFE_MODE 및 Recovery 동작 확인
    - 다중 탭 동시 접속 시 Cross-tab guard 동작 확인
    - Admin Decision Override 후 통계 반영 정합성 확인
- Status: BACKLOG

---

### TASK-032 tag_code 허용 값 제약 및 무결성 강화
- Purpose: 평가 태그(tag_code)가 정의된 범위를 벗어나지 않도록 DB 및 로직 레벨에서 무결성 강제 (R-2 대응)
- Scope: `evaluation_scores` 테이블 스키마 및 `RubricEvaluator` 검증 로직
- Status: BACKLOG
