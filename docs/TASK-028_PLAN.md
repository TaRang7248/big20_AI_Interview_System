# TASK-028: 관리자 통계 및 운영 관측 계층 설계 (Final Plan)

이 문서는 **TASK-028: 관리자 통계 및 운영 관측 계층(Admin Statistics & Operation Observation Layer)** 의 최종 상세 설계 계획이다.
본 계층은 **Query 전용 확장**으로 설계되며, 기존 Command 계층, Snapshot/Freeze/State 계약, 그리고 데이터 권한(Authority)을 절대 침해하지 않는다.

---

## 1. Goal Description

운영자 및 관리자가 면접 진행 상황, 평가 결과, 시스템 운영 지표를 직관적으로 파악할 수 있는 **통계 및 관측(Observability) 계층**을 구축한다.
이 계층은 오직 **읽기(Read-Only)** 만을 수행하며, 어떠한 상태 변경이나 비즈니스 로직 개입도 허용하지 않는다.

---

## 2. Scope (2-Track Structure)

통계 및 관측 데이터는 다음 두 가지 트랙으로 구조화하며, 모두 **Query Only** 원칙을 따르되, **데이터 출처와 신뢰 수준(Trust Level)** 을 엄격히 분리한다.

### Track A: Business Statistics (관리자 통계) - 결정적 데이터
비즈니스 의사결정(합격 여부, 공고 성과 판단)의 근거가 되는 데이터이다.
**반드시 PostgreSQL에 확정 저장(Committed)된 Snapshot만을 원천으로 한다.**

- **면접 진행 통계**: 기간별/상태별(Applied, In Progress, Completed 등) 면접 진행 건수
- **평가 점수 집계**: 전체/직군별/공고별 평균 점수 및 점수 분포 (Histogram)
- **직군/공고별 합격률**: 최종 합격/불합격 비율 분석
- **루브릭 태그별 평균 점수**: 평가 항목(Rubric Tag)별 강점/약점 분석
- **기간 기반 트렌드**: 주간/월간 지원자 수 및 평균 점수 변화 추이
- **세션 완료율**: 중도 이탈(Interrupted) 대비 정상 완료(Completed) 비율

### Track B: Operational Observability (운영 관측) - 참고용 데이터
시스템 안정성 및 성능 모니터링을 위한 참고용(Informational) 데이터이다.
**비즈니스 의사결정(합격률, 점수)의 근거로 절대 사용하지 않는다.**
**로그 유실 가능성을 전제로 하며, 절대 수치보다는 추세(Trend) 확인을 목적으로 한다.**

- **평균 응답 시간**: 단계별(질문 생성 ~ 답변 제출 ~ 분석 완료) 소요 시간 통계
- **Redis 캐시 히트율**: Cache Hit/Miss 비율 (순수 관측 목적)
- **LLM 호출 실패율**: RAG/Generate 실패 빈도 및 Fallback 전환율
- **상태 전이 실패율**: 유효하지 않은 상태 전이 시도 횟수 (로그 기반 또는 실패 이벤트 집계)
- **단계별 처리 지연 분포**: 각 파이프라인 단계(STT, Analysis, Eval)의 Latency 분포

---

## 3. Observability 지표 설계 원칙

운영 관측 지표는 반드시 다음 3축으로 분해 가능해야 한다.

- **Reason**: 실패 또는 지연의 원인을 코드 레벨에서 분류 가능해야 한다. (예: `LLM_TIMEOUT`, `NO_FACE_DETECTED`)
- **Span**: 세션 전체가 아닌 단계별 구간으로 분해 가능해야 한다. (예: `STT_PROCESSING`, `EVALUATION_CALC`)
- **Layer**: 문제가 발생한 계층을 구분 가능해야 한다. (예: `API`, `Service`, `Provider`, `DB`, `Cache`)

> **[원칙]** 관측 지표는 `Reason` + `Span` + `Layer` 조합으로 Slice & Dice 가능해야 한다.

---

## 4. 데이터 출처 계약 (Data Source Authority)

관측 및 통계의 근거 데이터 출처는 다음 원칙을 엄격히 따른다.

- **1차 소스 (Primary Source - Business Stats)**:
  - **PostgreSQL**: 비즈니스 통계의 유일한 권위(Single Source of Truth).
  - Snapshot(`interviews`, `evaluations`) 테이블의 확정된 데이터만 사용.
- **2차 소스 (Secondary Source - Observability Only)**:
  - **Logs (Aggregated)**: 응답 시간, 캐시 히트율 등은 로그 파일 파싱을 통한 집계나 일시적 메모리 집계를 사용한다.
  - **PostgreSQL Failure Events**: 상태 전이 실패 등이 DB에 이벤트로 기록된 경우에만 DB를 참조한다.
  - **제약**: 로그 기반 데이터는 Snapshot 데이터와 Join 하거나 혼합하여 비즈니스 지표를 산출하는 것을 금지한다.
- **금지 호환 (Strictly Prohibited)**:
  - **Redis Authority 승격 금지**: Redis 데이터를 원천으로 통계를 산출하지 않는다.
  - **Log → Business Logic 금지**: 로그 분석 결과가 합격 여부나 점수에 영향을 주어서는 안 된다.

---

## 5. View 및 모델링 전략 (Read-Only)

- **PostgreSQL 스키마 변경 금지 (원천)**:
  - 기존 `users`, `job_postings`, `interviews`, `evaluations` 테이블의 스키마 변경은 금지한다.
- **통계 전용 View / Summary Table 허용**:
  - 통계 쿼리 최적화를 위한 **View**, **Materialized View (MView)**, 또는 **Summary Table** 생성은 허용한다.
  - **단, 조건**:
    1. 원천 데이터의 불변성을 침해하지 않아야 한다. (Read-Only)
    2. Summary Table은 원천 테이블과 분리된 **통계 전용 Read Model**이어야 한다.
    3. 통계 데이터를 원천 테이블에 다시 쓰는 **Write-Back**은 절대 금지한다.

---

## 6. 관측 지표 저장 및 성능 전략

- **저장 전략 (No New Write Path)**:
  - Phase 10에서는 **별도의 시계열 DB나 영속적인 관측 데이터 저장소를 도입하지 않는다.**
  - 관측 지표는 **Query-Time Aggregation** (조회 시점 집계) 또는 **In-Memory Buffer**를 기본으로 한다.
  - 로그 파일은 기존 로깅 정책을 따르며, 별도 적재 파이프라인을 구축하지 않는다.
- **쿼리 분류 및 성능 전략**:
  - **Type 1 (실시간 현황)**: Direct DB Query (Index 활용).
  - **Type 2 (기간 집계)**: Read-Through Caching (Redis).
  - **Type 3 (다차원 분석)**: MView 활용 + 배치 주기 갱신 (실시간 부하 격리).
  - **Type 4 (상관 분석)**: 백그라운드 배치로만 수행 (API 실시간 요청 금지).

---

## 7. 상태 전이 실패율 및 엔진 보호

- **출처 한정**:
  - "상태 전이 실패율"은 **이미 로그에 기록된 에러**나 **PostgreSQL에 기록된 실패 이력**만을 집계한다.
- **엔진 수정 금지**:
  - 실패율 측정을 위해 `SessionEngine`이나 `Command` 핸들러에 카운팅 로직을 심거나 DB에 기록하는 코드를 추가하지 않는다.
  - 엔진은 오직 비즈니스 로직 성공/실패만 반환하며, 통계 집계의 책임을 지지 않는다.

---

## 8. Snapshot / Freeze 침해 방지 조항 (Re-iterated)

- **Snapshot 재평가 금지**: 통계 산출 시 점수 재계산 절대 금지.
- **평가 재계산 금지**: 확정된 점수 변경 불가.
- **세션 상태 변경 금지**: 통계 조회(Query)의 Side-effect로 상태 변경 불가.
- **Engine 메서드 호출 금지**: 통계 로직에서 Engine 메서드 호출 불가.

---

## 9. 승인 게이트 (Final Verification Gates)

Plan 승인을 위해 다음 체크리스트를 통과해야 한다.

- [ ] **Query 전용 계층인가?**: Command 로직과 물리적/논리적으로 분리되었는가?
- [ ] **Command/Engine 침범이 없는가?**: Service Layer 및 Engine 메서드 호출, 수정이 없는가?
- [ ] **Snapshot 재해석이 없는가?**: 저장된 Snapshot 값을 그대로 사용하는가?
- [ ] **PostgreSQL Authority가 유지되는가?**: 비즈니스 통계의 원천이 PG인가?
- [ ] **Redis가 근거 데이터로 사용되지 않는가?**: Redis는 단순 캐시인가?
- [ ] **로그 지표와 비즈니스 지표가 분리되었는가?**: 로그는 참고용으로만 사용되는가?
- [ ] **상태 전이 실패율을 위해 Engine을 수정하지 않는가?**: 기존 로그/데이터만 활용하는가?
- [ ] **MView/Summary Table이 원천을 침해하지 않는가?**: Read Model로 격리되었는가?
- [ ] **신규 Write 경로가 없는가?**: 관측을 위한 영속 저장이 추가되지 않았는가?
