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

---
## DONE

### TASK-001 로깅 기반 구축 (Phase 0)
- **Goal**
  - 개발/테스트/런타임 중 발생하는 모든 에러가
    반드시 **파일 로그(.log)** 로 남는 기반을 구축한다.

- **Scope (포함)**
  - `IMH/IMH_Interview/logs/agent/` 폴더 생성
  - `IMH/IMH_Interview/logs/runtime/` 폴더 생성
  - 공통 로거 유틸 설계 (Rotating / Error 분리)
  - `logger.exception()` 사용 규칙 정립

- **Verification**
  - `python scripts/check_logging.py` 실행 시 성공

---

### TASK-002 imh_core 최소 패키지 구성 (Phase 1)
- **Goal**: config / errors / dto 최소 코어 확정 및 구현
- **Scope**: `packages/imh_core/{config.py, errors.py, dto.py}`
- **Verification**: `scripts/verify_task_002.py` Pass

---

### TASK-003 Provider 인터페이스 + Mock 구현
- STT / LLM / Emotion / Visual / Voice 인터페이스 정의
- Mock 구현체 작성 (테스트 용도)
- **Verification**: `scripts/verify_task_003.py` Pass

---

### TASK-004 FastAPI 최소 엔트리 + healthcheck
- `/health` 단일 엔드포인트
- **Verification**: `IMH/api/health.py` 구현 및 `scripts/verify_task_004.py` Pass

---

### TASK-005 Playground STT (파일 업로드)
- **Goal**: Mock STT Provider 기반 파일 업로드 및 분석 API 구현
- **Scope**: `POST /api/v1/playground/stt`
- **Verification**: `python scripts/verify_task_005.py` Pass

---

### TASK-006 Playground PDF → Text (문서 업로드)
- **Goal**: PDF 업로드 → 텍스트 추출 Playground 파이프라인 검증
- **Scope**:
  - PDF 파일 업로드
  - 텍스트 추출 결과 반환
  - 저장 정책 준수(원본 파일 장기 저장 금지)
- **Verification**: `python scripts/verify_task_006.py` Pass

---

### TASK-007 Playground Embedding → Query Focus
- **Goal**: 검색(RAG) 용도로 사용되는 **Query Text**를 임베딩 벡터로 변환하는 Playground 파이프라인 검증
- **Scope**:
  - Query Text → Embedding 변환
  - Embedding Provider (Mock) 기반 검증
  - 대화 전체 / STT 결과 임베딩 제외
- **Verification**: `python scripts/verify_task_007.py` Pass

---

### TASK-008 Emotion 분석 (DeepFace, 1fps)
- **Goal**: Playground 환경에서 **DeepFace 기반 감정 분석 파이프라인**을 검증하고,
  실시간 면접 적용 전 저주기(1fps) Emotion 분석 코어의 안정성을 확인
- **Scope**:
  - 이미지 / 비디오 파일 기반 Emotion 분석
  - 1fps 프레임 샘플링 기반 DeepFace 추론
  - 얼굴 미검출 / 다중 얼굴 처리 정책 검증
  - 시계열 DTO 구조화 및 Playground API 연동
- **Verification**: `python scripts/verify_task_008.py` Pass

---

### TASK-009 Voice 분석 (Parselmouth)
- **Goal**: Playground 환경에서 **Parselmouth 기반 음성 분석 파이프라인**을 검증하고,
  실시간 면접 적용 전 음성 특성 분석 코어의 안정성을 확인
- **Scope**:
  - 오디오 파일 기반 음성 분석
  - Pitch / Intensity / Jitter / Shimmer / HNR 등 음향학적 지표 추출
  - 무음 / 비정상 파일 입력에 대한 예외 처리 정책 검증
  - Voice Provider 실구현체(Parselmouth) 기반 동작 확인
- **Verification**: `python scripts/verify_task_009.py` Pass

---

### TASK-010 Visual 분석 (MediaPipe)
- **Goal**: Playground 환경에서 **MediaPipe 기반 시각 분석 파이프라인**을 검증하고,
  실시간 면접 적용 전 비언어적 시각 정보 분석 코어의 안정성을 확인
- **Scope**:
  - 이미지 기반 얼굴 검출 및 존재 여부(Presence) 판단
  - 시선(Yaw) 및 자세(Pose) 정보 추출
  - 얼굴 미검출(No Face) 시 안전한 결과 반환 정책 검증
  - Visual Provider 실구현체(MediaPipe) 기반 동작 확인
- **Verification**: `python scripts/verify_task_010.py` Pass

---

### TASK-011 정량 평가 엔진 (루브릭 기반)
- **Goal**: Mock Provider / Analysis Result 기반 **정량 평가 로직(Eval Engine)** 검증
- **Scope**:
  - `packages/imh_eval` Rule-based 평가 로직
  - 직무/문제해결/의사소통/태도 영역별 점수 산출
  - `evidence_data` JSON 스키마 준수 및 직군별 가중치 적용
- **Verification**: `python scripts/verify_task_011.py` Pass

---

### TASK-012 평가 결과 리포팅 / 해석 계층 설계 (Reporting Layer)
- **Goal**: EvaluationResult(+Evidence)를 사용자 친화적 **InterviewReport(JSON)**로 변환하는 리포팅/해석 계층 구축
- **Scope**:
  - `packages/imh_report` 구현 (DTO / Mapping / Report Generator)
  - Score → Total Score(100점 환산) / Grade 매핑
  - `tag_code` 기반 Feedback/Insight 매핑
  - Mock 기반 Report 생성 및 구조 검증
- **Verification**: `python scripts/verify_task_012.py` Pass

---

### TASK-013 리포트 저장 / 이력 관리 (Persistence & History)
- **Goal**: 생성된 `InterviewReport`를 서비스 데이터로 보존하고, 면접 회차별 조회/리스트/상세 조회를 위한 Persistence 계층 구축
- **Scope**:
  - 파일 시스템 기반 `InterviewReport` 저장 구조 구현 (식별자/타임스탬프 기반)
  - Repository 인터페이스(`HistoryRepository`) 및 파일 기반 구현체(`FileHistoryRepository`) 구현
  - 메타데이터 파싱 기반 이력 조회(Find By ID / Find All) 기능 구현
  - 저장/조회 검증 스크립트(`scripts/verify_task_013.py`) 작성 및 검증 완료
- **Verification**: `python scripts/verify_task_013.py` Pass

---

### TASK-014 리포트 조회 API 노출 (Report API Contract)

- **Goal**:
  - 저장된 `InterviewReport`를 외부(UI/관리자/후속 서비스)에서 소비할 수 있도록
    **조회 전용 API 계약을 정의하고 노출**한다.

- **Scope**:
  - 단건 리포트 조회 API 계약 정의 (interview_id 기준)
  - 리포트 목록 조회 API 계약 정의 (타임스탬프 기준 정렬)
  - 응답 스키마 고정:
    - TASK-012에서 정의된 `InterviewReport` JSON 구조 재사용
  - API 응답 포맷 및 필드 의미 명세

- **Out of Scope**:
  - UI 화면 구현
  - 인증/권한 고도화
  - DB / 외부 저장소 연동
  - 실시간 세션 API

- **Dependencies**:
  - TASK-013 (리포트 저장 / 이력 관리) 완료

---

### TASK-015 리포트 소비 규격 정의 (UI / Client Contract)

- **Goal**:
  - 프론트엔드 및 클라이언트 관점에서
    `InterviewReport` JSON을 **어떻게 해석·표현·소비할지에 대한 규격을 확정**한다.

- **Scope**:
  - 리포트 주요 필드의 UI 표현 규칙 정의
    - 점수(Score), 등급(Grade), 요약(Summary), 피드백(Insight)
  - 시각화 요소 사용 규칙 정의
    - Radar Chart / Bar Chart 등에서 사용하는 필드 범위
  - 텍스트 길이 제한, 요약 우선순위 등 UI 친화 규칙 명시

- **Out of Scope**:
  - 실제 UI 컴포넌트 구현
  - 디자인 시안 작업
  - 사용자 인터랙션 로직

- **Dependencies**:
  - TASK-012 (Reporting Layer) 완료
  - TASK-014 (리포트 조회 API 계약) 완료

---

### TASK-017 Interview Session Engine (실시간 면접 세션 엔진)
- **Goal**:
  - “실시간 면접 플로우 통합”의 중심이 되는 세션 엔진을 정의하고,
    정책 기반 상태 전이 및 질문 진행 규칙을 일관되게 오케스트레이션한다.
- **Scope**:
  - 세션 상태 전이 정의: APPLIED → IN_PROGRESS → (COMPLETED | INTERRUPTED) → EVALUATED
  - 질문 진행 규칙:
    - 질문 전환 트리거(답변완료 버튼 / 침묵 / 제한시간) 정책 반영
    - 최소 질문 수 기본값 10개 보장(정책 기반)
    - 침묵 2케이스 구분(무응답 침묵 vs 답변 후 침묵)
  - 세션 중 결과 생성 타이밍(매 질문 평가, 최종 결과 공개는 종료 후) 정책 반영
- **Out of Scope**:
  - WebRTC/실시간 스트리밍 구현
  - 프론트/UI 구현
  - DB 도입/마이그레이션
- **Dependencies**:
  - 인터뷰 정책 스펙(INTERVIEW_POLICY_SPEC) 확정본
  - TASK-011 ~ TASK-015 완료

---

### TASK-018 실전/연습 모드 분리 (Interview Mode Policy Split)
- **Goal**:
  - “공고 기반 실전 면접”과 “AI 면접 연습”의 기능/권한/중단 정책을 분리한다.
- **Scope**:
  - 실전/연습 기능 차이 정책 반영(일시정지/재시도/재질문 등)
  - 중단/복구 정책 반영:
    - 연습: 재진행 허용
    - 실전: 중단 시 INTERRUPTED로 종료 처리
  - 결과 노출 정책 분리(실전은 관리자 설정 기반)
- **Out of Scope**:
  - 실제 UI 버튼/화면 구현
  - 장애 원인 자동 판별(사용자 강제 종료 vs 시스템 문제)
- **Dependencies**:
  - TASK-017 세션 엔진 정의 완료
  - 인터뷰 정책 스펙(INTERVIEW_POLICY_SPEC) 확정본

---

### TASK-019 공고(채용) 정책 엔진 (Job Posting Policy Engine)
- **Goal**:
  - 관리자(인사담당자)가 공고 등록 시 설정한 옵션이 면접 진행/노출 정책에 반영되도록 한다.
- **Scope**:
  - 공고별 설정 항목 정의 및 정책 반영:
    - 침묵 대기 시간
    - 답변 제한 시간
    - 평가 가중치 조정 범위(10~90%)
    - 필수 질문
    - 질문 표시 방식(TTS only / TTS + Text)
    - 공고별 모델 선택(등록 후 수정 불가)
    - 결과 공개 시점: 즉시 / 특정 시각 / 관리자 승인
    - 단, 어떤 설정이든 “2주 내 합/불합 자동 전달” 하한선 유지
- **Out of Scope**:
  - 실제 공고 등록 UI/관리자 페이지 구현
  - DB 기반 영속화(현재는 파일 기반/임시 구조 유지)
- **Dependencies**:
  - TASK-018 정책 분리 기준 확정
  - 인터뷰 정책 스펙(INTERVIEW_POLICY_SPEC) 확정본

---

### TASK-020 관리자 지원자 조회/필터 규격 (Admin Applicant Filtering)
- **Goal**:
  - 관리자가 면접자들을 빠르게 탐색/분류할 수 있는 조회/필터 기준을 확정한다.
- **Scope**:
  - 필수 필터:
    - 날짜
    - 접수/진행 상태(APPLIED/IN_PROGRESS/COMPLETED/INTERRUPTED/EVALUATED)
    - 합/불합
  - 추천 추가 필터(우선순위 낮음):
    - 점수 구간(전체/축별)
    - 축별 약점(예: 의사소통 낮음)
    - 중단 여부(INTERRUPTED)
    - 공고/직무/모집분야
- **Out of Scope**:
  - 실제 관리자 UI 구현
- **Dependencies**:
  - TASK-019 공고 정책 엔진 범위 확정
  - 리포트 조회 API 계약(TASK-014) 및 UI 소비 규격(TASK-015)

---

### TASK-021 세션 중단 표기/처리 규격 (Interrupt Handling & Visibility)
- **Goal**:
  - 실전/연습 모드의 “중단 처리”를 일관되게 종료 상태로 반영하고,
    관리자 조회에서 “면접 중단”이 명확히 구분되도록 한다.
- **Scope**:
  - 실전: INTERRUPTED 종료 처리
  - 연습: 재진행 허용(정책 범위 내)
  - 관리자 조회/리포트에 중단 플래그/표시 규격 확정
- **Out of Scope**:
  - 중단 원인 자동 판별(네트워크/브라우저/사용자 종료 등)
- **Dependencies**:
  - TASK-018 실전/연습 모드 분리 확정
  - TASK-020 관리자 조회 규격 확정

---
### TASK-022 서비스 레이어 및 DTO 구현 (Service Layer & Integration)
- **Goal**:
  - API 계층과 도메인 계층(세션 엔진)을 중재하는 Service Layer를 구현하고,
    DTO/Mapper를 통해 외부 계약과 내부 로직을 완전 격리한다.
- **Scope**:
  - `packages/imh_service/` 구현 (SessionService, AdminQueryService)
  - `packages/imh_dto/` 및 `Mapper` 구현
  - 동시성 제어(`ConcurrencyManager`) 및 트랜잭션 경계 설정
- **Out of Scope**:
  - 실제 API 엔드포인트 구현 (다음 단계)
- **Dependencies**:
  - TASK-021 (통합 아키텍처) 완료
  - TASK-022 계획(PLAN) 준수

---

### TASK-023 API 레이어 구현 및 연동 (API Layer Implementation)
- **Goal**:
  - Service Layer를 호출하는 FastAPI 엔드포인트를 구현하여 외부에서 인터뷰 세션을 수행할 수 있게 한다.
- **Scope**:
  - `IMH/api/session.py` (면접자용): 생성, 진행, 답변 제출
  - `IMH/api/admin.py` (관리자용): 조회, 관리
  - Exception Handling 및 Status Code 매핑
- **Verification**: `python scripts/verify_task_023.py` Pass

---

### TASK-024 질문은행 구조 정비 (Question Bank Structure)
- **Goal**:
  - 질문 생성 품질 저하 또는 실패 시 사용할 정적/동적 질문은행 구조를 정비한다.
- **Scope**:
  - `packages/imh_qbank` 패키지 신설
  - 질문 출처(Source) 계층 정의 (Generated vs Banked)
  - 태그 기반 질문 검색/매핑 전략
  - (원칙) qbank는 “질문 후보 조회/선택 지원”까지만 담당하며, 실제 질문 채택/상태 전이는 Engine/Service 계약을 통해서만 수행한다.
- **Verification**: `python scripts/verify_task_024.py` Pass

---

### TASK-025 RAG Fallback 엔진 통합
- **Goal**:
  - LLM 질문 생성 실패 시 질문은행을 Fallback으로 사용하는 로직을 통합한다.
- **Scope**:
  - RAG 기반 유사 질문 검색
  - (초기 구현) PGVector 없이도 Embedding Provider + 로컬/메모리 인덱스 기반 유사도 검색으로 시작 가능 (정식 벡터DB는 Out of Scope 유지)
  - Fallback 트리거 정책 정의
  - Snapshot 계약 침범 방지 하에 통합
- **Verification**: `python scripts/verify_task_025.py` Pass

---

### TASK-026 PostgreSQL 도입 (공고/세션/평가 영속화)
- **Goal**:
  - 현재 파일 기반 저장 구조를 PostgreSQL 기반으로 전환한다.
- **Scope**:
  - users / job_postings / interviews / evaluations 스키마 적용
  - 파일 기반 저장소 교체
  - **Write Path Switch** (Memory -> PostgreSQL)
  - **Dual Write Strategy** 수립 및 검증
- **Out of Scope**:
  - 인프라 배포 자동화
- **Verification**: `stage3_execution_report.md` (Stage 3 Execution)
- **Dependencies**:
  - Phase 7 완료
  - 데이터 아키텍처 설계 문서(예: docs/26.02.05(목)데이터 아키텍쳐,ERD 가이드.md)

---

### TASK-027 Redis 세션 상태 및 캐시 계층 도입 (Checkpoint 기반 진행) ✅ COMPLETE

- **Goal**:
  - 실시간 세션 상태 및 락 관리를 안정화하고,
  - Projection / RAG / Candidate / Prompt Cache 계층을 구축하여
    Redis = Read Optimization Only 구조를 확정한다.
  - PostgreSQL = Single Source of Truth 계약을 강화한다.
  - Dual Write 제거 조건을 충족한다.

- **Scope (CP0: Baseline)**: ✅ LOCKED
  - `RedisRuntimeStore` (PG -> Redis Mirror)
  - `RedisConcurrencyManager` (Fail-Fast Lock / Idempotency)
  - State Contract 확정
  - `verify_task_027.py` Pass

- **Scope (CP1: Projection Cache)**: ✅ LOCKED
  - `SessionProjectionDTO` / `RedisProjectionRepository`
  - Read-Through Strategy
  - Invalidate-First Policy
  - Redis Down Fallback
  - `verify_cp1.py` Pass

- **Scope (CP2: RAG Cache)**: ✅ LOCKED
  - `RAGCacheDTO` / `RedisRAGRepository`
  - CachedQuestionGenerator Decorator
  - Async Save
  - Versioned Key Strategy
  - Dynamic TTL (Authority 기반)
  - `verify_cp2.py` Pass
  - `TASK-027_CP2_AUDIT_REPORT.md` Pass

- **Scope (CP3: Candidate Pool Cache)**: ✅ LOCKED
  - Candidate Entity Cache + Candidate List Cache (Read Optimization)
  - Read-Through Strategy
  - Invalidate-on Save/Delete (PG 성공 이후 무효화)
  - Stale Data Protection (`is_active=true` 보장, Read-Time Filtering + Silent Drop)
  - Redis Down Soft Fallback (서비스 연속성 보장)
  - `scripts/verify_task_027_cp3.py` Pass
  - `TASK-027_CP3_VERIFICATION_REPORT.md` VERIFIED

- **Scope (CP4: Prompt Composition Cache)**: ✅ LOCKED
  - Redis Prompt Repository
  - CachedPromptComposer (Read-Through Pattern)
  - Logical Prompt Version Identifier
  - Versioned Key Strategy
  - Max Size Limit
  - Stampede Protection (Leader/Follower 최소 방지 전략)
  - Fail-Open Strategy
  - `verify_task_027_cp4.py` Pass
  - `TASK-027_CP4_AUDIT_REPORT.md` Pass

- **Architecture Contracts Reinforced**:
  - PostgreSQL = Single Source of Truth
  - Redis = Read Optimization Only
  - Write Order = PG → Redis
  - No Write-Back
  - Snapshot Immutable 유지
  - Deterministic Evaluation 보장

- **Dual Write Removal Condition**:
  - PostgreSQL-only 모드 안정성 검증 완료

- **Out of Scope**:
  - Redis Cluster / HA 구성

- **Dependencies**:
  - TASK-026 완료

---

## ACTIVE

### TASK-028 관리자 통계 대시보드

- **Goal**:
  - 공고별 / 직무별 / 평가축별 통계 시각화
  - 운영 관측(Observability) 강화를 통해
    시스템 품질 및 멀티모달 확장 기반을 마련한다.

- **Scope (초기 정의)**:
  - 평균 점수
  - 합격률
  - 평가축별 약점 분포
  - Query 전용 확장 계층 설계
  - 세션/모델/캐시 관련 운영 지표 확장 가능 구조

- **Out of Scope**:
  - 외부 BI 연동
  - UI 디자인 고도화

- **Dependencies**:
  - TASK-026 완료
  - TASK-027 완료

---
## HOLD

### TASK-016 TTS Provider (Text → Speech)
- **Goal**:
  - 면접 질문 또는 피드백을 음성으로 출력하기 위한 TTS Provider 계층 준비
- **Scope (예정)**:
  - TTS Provider 인터페이스 정의
  - Mock 기반 Text → Speech 변환 파이프라인
- **보류 사유**:
  - Phase 9는 COMPLETE이며(Redis CP0~CP4 🔒 LOCKED), 현재 최우선은 Phase 10(TASK-028) 운영 통계/관측 계층이다.
  - TTS는 실시간/Streaming 오케스트레이션과 결합될 가능성이 높아 별도 계약 하에 진행해야 한다.
  - Engine 경계 및 Snapshot 계약을 침해하지 않도록, 통계/관측 기반의 안정성 데이터 확보 이후 재개한다.
- **재개 조건**:
  - TASK-028 완료(운영 통계/관측 계층 확정)
  - Streaming 아키텍처(TTS 포함) 범위가 별도 문서/계약으로 고정된 이후
