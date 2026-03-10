# 00_AGENT_PLAYBOOK — Phase 10 기준 통합 운영 PLAYBOOK

본 문서는 **Phase 10 완료 기준** 시스템의 운영 통제와 아키텍처 보호를 위해 제정된 **운영 통제 헌장**이다.  
코딩 에이전트는 더 이상 설계를 시도하지 않으며, 확정된 운영 기준선(Baseline) 내에서만 작업을 수행한다.

---

## 0. 목적 및 기준선 선언
- **본 문서는 설계 진행 문서가 아닌 "운영 통제 헌장"이다.**
- Phase 10 (Operational Statistics & Observability) 완료 후의 안정화 기준선을 준수한다.
- 에이전트는 본 문서에 명시된 통제 규칙을 위반하는 어떠한 코드 수정이나 아키텍처 변경도 수행할 수 없다.

---

## 1. 에이전트 실행 프로토콜 (Mandatory Protocols)

### 1.1 변경 승인 게이트 (Plan-Only First)
- 코드 수정 전 반드시 **변경 제안서(Proposal)** 작성 → 사용자 승인 후 구현.
- 승인 전에는 실제 코드 변경, 커밋, 대규모 diff 출력 금지.

### 1.2 로깅 및 관측 규칙 (Logging)
- 모든 런타임 관측 및 에러는 `logs/*.log` 파일에 남긴다.
- `logger.exception()` 사용 및 스택트레이스 포함 의무.
- 보안: RAW 답변 원문, 개인정보, 비밀번호, 인증 토큰 로깅 금지.

### 1.3 Python 실행 환경 규칙 (venv 강제)
- 단일 가상환경 사용: `interview_env` (C:\big20\big20_AI_Interview_System\interview_env)
- 모든 python / pip 실행은 해당 경로의 `Scripts\python.exe`를 직접 지정하여 수행한다.
- 전역 Python 사용 또는 venv 신규 생성은 절대 금지한다.

### 1.4 폴더 및 모듈 구조 규칙
- **IMH/ 사용**: `app/` 폴더 대신 `IMH/`를 사용한다. 신규 import 시 `app.*`를 강제한다.
- **Package-Centric**: 재사용 로직은 `packages/` 하위 모듈로 관리한다.
- 진입점(Entry)은 Thin 레이어로 유지하고 비즈니스 로직은 분리한다.

### 1.5 루트 디렉토리 청결 유지 (Root Hygiene)
- 루트 디렉토리(Project Root)에는 어떠한 임시 파일(`.txt`, `.log`, `.tmp`)도 직접 생성하지 않는다.
- 모든 테스트 및 벤치마크 산출물은 `docs/benchmarks/` 하위 폴더로, 런타임 로그는 `logs/benchmarks/` 또는 `logs/runtime/`으로 경로를 명시하여 생성한다.
- 작업 종료 시 루트에 남은 임시 파일이 있다면 반드시 아카이빙 경로로 이동시키거나 제거한다.

---

## 2. 문서 접근 통제 (Single Source of Truth)

### 2.1 접근 통제 구역
- **PROJECT_STATUS.md 접근 금지**: 해당 문서는 ChatGPT 전용 전략 문서로, 에이전트의 판단 근거가 아니다.
- **docs/ 폴더 유일 원칙**: 에이전트의 모든 판단 근거는 프로젝트 루트의 `docs/` 내 문서로 한정한다.
- **_refs/ 직접 구현 금지**: `_refs/` 내 원본 스펙은 `docs/` 문서(CURRENT_STATE 등)에 반영된 이후에만 구현 기준이 된다.

### 2.2 문서 불일치 처리
- 사용자 지시와 docs/ 문서가 충돌할 경우, 에이전트는 이를 보고하고 docs/ 기준 수정을 먼저 제안한다.
- 구현과 문서가 다를 경우 `docs/DECISIONS.md`에 사유를 기록하고 합치(Alignment) 작업을 우선 수행한다.

---

## 3. 아키텍처 보호 원칙 (Phase 10 기준)

코딩 에이전트는 다음의 8대 아키텍처 원칙을 절대 훼손할 수 없다.

1. **PostgreSQL Authority**: 모든 영속 데이터의 유일한 권위 저장소(Source of Truth)는 PostgreSQL이다.
2. **Redis Runtime/Cache Only**: Redis는 런타임 제어(Lock, Idempotency) 및 조회 최적화(Cache) 전용이다.
3. **No Write-Back 금지**: Redis에서 PostgreSQL로 데이터를 역으로 기록하는 경로는 영구히 금지한다.
4. **Snapshot Immutable**: 공고 및 세션 스냅샷은 생성 후 데이터 수정이 절대 불가능하다.
5. **Session Engine Transition**: 인터뷰 상태 전이는 오직 Session Engine의 메서드 호출을 통해서만 수행한다.
6. **Track A/B 완전 분리**: 비즈니스 통계(Track A)와 운영 관측(Track B)은 코드 및 경로 수준에서 물리적으로 분리한다.
7. **Stats/Obs Write Path 금지**: 통계 및 관측 계층은 어떠한 경우에도 신규 영속 Write Path를 생성하지 않는다.
8. **Playground 격리**: Playground는 운영 흐름(Engine/State Contract)과 완전히 독립된 실험 영역이다.

---

## 4. 문서 체계 및 Task Queue 규격

### 4.1 Task 1개 템플릿
- **Task ID**: T-YYYYMMDD-###
- **Goal**: 완료 정의
- **Scope**: 범위 명시
- **Spec Links**: 관련 docs 문서 링크
- **Acceptance Criteria**: 검증 가능한 체크리스트 (curl, pytest 등)
- **Files**: 대상 파일 목록

### 4.2 Task 가이드
- Task 크기는 1~2개 엔드포인트 또는 1개 데이터 계약 확정 수준으로 쪼갠다.
- 모든 Task는 "검증 스크립트 실행 시 Pass"를 완료 조건(Acceptance Criteria)으로 포함한다.

---

## 5. 스펙 참조 규칙

1. **최신성 우선**: 문서 내 날짜가 명시된 경우 가장 최신 날짜를 따름.
2. **ERD 변경 우선**: ERD 가이드에서 명시된 테이블 구조/관계 변경은 기타 설계보다 우선한다.
3. **불일치 기록**: 구현 상의 특이사항이나 설계 수용 불가 사항은 반드시 `docs/DECISIONS.md`에 영구 기록한다.

---

## Appendix

### A. 핵심 JSON 계약 요약
- **chat_history**: `{role, content, timestamp, question_id?}` 배열 형태.
- **evidence_data**: 루브릭 가이드 기반의 정량 근거 필드 포함.

### B. 주요 문서 링크 (정책 및 스펙)
- 인터뷰 정책 스펙: `_refs/26.02.11(수)인터뷰 정책 스펙.md`
- ERD 가이드: `_refs/26.02.05(목)데이터 아키텍쳐,ERD 가이드.md`
- UI 설계: `_refs/26.02.06(금)AI 면접 프로그램 UI 설계 초안.md`
- 질문 태그: `_refs/26.02.05(목)질문태그설계.md`
- 루브릭: `_refs/26.02.09(월)정량평가 루브릭 가이드.md`
- 현재 상태 스냅샷: `docs/CURRENT_STATE.md`