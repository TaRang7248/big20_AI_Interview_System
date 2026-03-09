# TASK-027: Candidate Pool 계약 정의서 - CP3 Plan V3 (Final Contract)

## 1. CP3 Scope 및 Candidate Pool 정의

### 1) Candidate Pool 정의
- **정의**: Candidate Pool은 "현재 유효한(Active) 질문 리소스의 **Read-Only Projection** 상태"를 의미한다.
- **생성 시점 정책 (Lazy Loading 원칙)**:
    - **Default**: 모든 Candidate Cache는 **최초 조회 시점(On-Demand)**에 생성됨을 원칙으로 한다. (Read-Through)
    - **Exception**: 세션 시작 시 필수적으로 사용되는 데이터에 한해, 시스템 부하 분산을 목적으로 **사전 적재(Pre-loading)**를 허용한다. 단, 이는 필수가 아닌 최적화 수단으로 분류한다.
    - **Contract**: 캐시 미스(Cache Miss) 발생 시, 반드시 원본 저장소(PostgreSQL)에서 즉시 데이터를 로드하여 가용성을 보장해야 한다.

### 2) 사용 레이어 및 책임 (Role & Responsibility)
구체적인 구현체 대신, 다음의 논리적 계층 정의를 따른다:
- **Application Service Layer**: 비즈니스 흐름을 관장하며, Candidate Data를 요청한다.
- **Candidate Provider**: 데이터의 원천(Cache vs DB)을 추상화하여 제공한다.
- **Cache Layer**: 인메모리 저장소와의 통신을 담당한다.
- **Source Repository**: 원본 데이터베이스와의 통신을 담당한다.

---

## 2. CP1 / CP2 와의 차이 (Scope Boundary)

- **CP1 (Session Context)**: 특정 사용자/세션의 **Stateful**한 진행 상태 저장.
- **CP2 (Vector Context)**: RAG를 위한 임베딩 벡터 및 유사도 검색 캐시.
- **CP3 (Candidate Context)**: 전역적으로 공유되는 **Stateless** 질문 엔티티 및 메타데이터 캐시.

---

## 3. PostgreSQL vs Cache 책임 경계 (Strict Contracts)

1. **Source of Truth**: 모든 데이터의 정본은 **PostgreSQL**이다. 캐시 데이터는 언제든지 삭제/재생성 가능하다.
2. **Authority**: 데이터의 생성/수정/삭제 권한은 오직 PostgreSQL을 통한 트랜잭션에만 있다.
3. **Immutability of Cache**: Cache Layer는 스스로 데이터를 생성하거나 변형하지 않는다. 오직 DB의 불변 복제본(Projected Copy)만을 저장한다.
4. **Resilience**: 캐시 장애는 전체 서비스 장애(Outage)로 이어져서는 안 되며, DB 직접 조회로 즉시 Fallback 되어야 한다.

---

## 4. Candidate List Cache 정책

본 CP3 단계에서는 Candidate Entity(단건) 캐시뿐만 아니라 **Candidate List(목록) 캐시**도 **허용(In Scope)**한다.
단, 다음 계약을 준수해야 한다:

- **Consistency**: 캐시 항목은 **조회 조건(Criteria) 및 논리적 범위(Scope)** 단위로 명확히 구분되어야 한다.
- **Dependency**: 목록에 포함된 각 항목의 상태 변경(예: Soft Delete)은 해당 항목이 포함된 목록 캐시의 정합성을 즉시 보장할 필요는 없으나(Eventual Consistency), 참조 무결성은 조회 시점에 검증되어야 한다.
- **Fallback**: 목록 캐시 미스 시, 즉시 DB 쿼리를 통해 재생성한다.

---

## 5. TTL (Time-To-Live) 결정 기준

구체적인 시간 수치 대신, 다음 **결정 기준(Decision Matrix)**에 따라 TTL을 설정한다:

1.  **Data Volatility (변경 빈도)**: 정보가 얼마나 자주 바뀌는가? (낮은 빈도 -> 긴 TTL)
2.  **Consistency Sensitivity (정합성 민감도)**: 사용자가 스테일 데이터를 보아도 되는가? (낮은 민감도 -> 긴 TTL)
3.  **Memory Pressure (리소스)**: 캐시 크기가 메모리에 주는 부담은? (높은 부담 -> 짧은 TTL)
4.  **Recalculation Cost (재생성 비용)**: DB 조회 비용이 얼마나 비싼가? (비싼 비용 -> 긴 TTL)

*Note: Dynamic TTL은 위 기준에 따라 런타임에 결정될 수 있으나, 기본 정책은 Static 설정값을 따른다.*

---

## 6. Stale Data 노출 방지 계약

Invalidation 지연 등으로 인해 Stale Data(예: Soft Deleted 질문)가 남아있더라도, **최종 사용자에게는 절대 노출되지 않아야 한다.**
이를 위해 다음 정책을 강제한다:

- **Read-Time Filtering**: 캐시에서 데이터를 조회한 직후, 어플리케이션 레벨에서 필수 상태(예: `is_active=true`)를 한 번 더 검증(Sanity Check)한다.
- **Silent Drop**: 검증 실패 시 해당 데이터는 없는 것으로 간주(Silent Drop)하고, 필요 시 DB에서 재조회하거나 빈 결과를 반환한다. (사용자에게 에러를 노출하지 않는다)

---

## 7. Cache Invalidation 정책 (Trigger & Scope)

### 1) Invalidation Triggers (무효화 유발 요인)
- **Entity Update**: 질문 내용, 카테고리 등 속성 변경 시.
- **Soft Delete**: 질문의 활성 상태(`is_active`)가 `false`로 변경 시.
- **Policy Change**: 공고(Job)의 질문 구성 정책이나 필터 조건 변경 시.
- **Global Flush**: 데이터 스키마 변경, 마이그레이션 등 시스템 레벨 초기화 시.

### 2) Scope of Impact (영향 범위)
- **Single Entity**: 변경된 엔티티 단위의 캐시 무효화.
- **Dependent Scopes**: 변경된 엔티티가 포함될 수 있는 **논리적 범위(List/Set)**의 캐시 무효화.
- **Namespace**: 버전 변경 등을 통한 **전체 범위(Broad Scope)**의 일괄 무효화.

*Note: TTL 기반 만료가 기본 전략일 수 있으나, 정책적으로 허용 가능한 범위 내에서만 사용한다.*

---

## 8. CP3 승인 게이트 (Approval Gates)

CP3 구현 승인을 위해서는 다음 **계약 조건들이 문서화된 정책 및 설계로 입증**되어야 한다:

1.  [ ] **Creation Policy**: 캐시 생성은 조회 시점(Lazy) 또는 명시적 Pre-load 정책을 준수해야 한다.
2.  [ ] **Architecture Abstraction**: 설계가 특정 캐시 기술에 종속되지 않고, 추상화된 역할을 통해 정의되어야 한다.
3.  [ ] **List Cache Consistency**: 목록 캐시 도입 시, 조회 조건과의 정합성 유지 정책이 확립되어야 한다.
4.  [ ] **TTL Strategy**: TTL 설정이 4가지 결정 기준(빈도/민감도/메모리/비용)에 근거하여 정의되어야 한다.
5.  [ ] **Stale Data Safety**: `is_active=false` 상태의 데이터 노출 방지 정책이 수립되어야 한다.
6.  [ ] **Invalidation Policy**: 데이터 변경 시 영향을 받는 엔티티 및 범위에 대한 무효화 정책이 정의되어야 한다.
7.  [ ] **PostgreSQL Authority**: 캐시 계층이 원본 데이터(PostgreSQL)에 쓰기(Write) 영향을 주는 경로가 없음이 보장되어야 한다. (No Write-Back)
8.  [ ] **Fallback Guarantee**: 캐시 사용 불가 시 DB 조회를 통해 서비스 가용성이 유지됨이 보장되어야 한다.
