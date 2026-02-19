# CP1: Session Projection Cache Plan

## 1. 개요 (Overview)
- **CP1(Checkpoint 1)**은 PostgreSQL을 유일한 권위(Authority)로 유지하면서, Session Runtime의 읽기 성능을 최적화하기 위한 **Projection Cache Strategy**를 정의한다.
- Redis는 **Read Optimization Layer**로서만 동작하며, 데이터의 영속성이나 정합성의 주체가 되지 않는다.
- 본 문서는 구현 전 단계의 **Plan**이며, 승인 시점까지 어떠한 코드도 작성하지 않는다.

## 2. Scope

### In Scope
- **Session Projection 구조 정의**: UI/Client가 빈번하게 조회하는 데이터의 구조화
- **Read-Through 전략**: Cache Miss 시 PostgreSQL 기반 복구 메커니즘
- **Cache Invalidation**: 상태 변경 시 Projection 갱신/무효화 타이밍
- **Redis Down Policy**: Redis 장애 시 System Behavior (Graceful Degradation)
- **Authority Constraints**: PostgreSQL vs Redis 책임 경계 명문화
- **TTL & Eviction**: 데이터 수명 주기 정책

### Out of Scope
- **Write-Back Cache**: Redis에 먼저 쓰고 나중에 PG에 반영하는 행위 (절대 금지)
- **PostgreSQL Schema Change**: DB 구조 변경 없음
- **Domain Model Change**: Engine/Domain 로직 변경 없음
- **Snapshot Contract**: 기존 Snapshot 불변성 계약 수정 없음
- **RAG/Candidate/Prompt Cache**: CP2, CP3, CP4에서 다룸

## 3. Core Principles (불변 원칙)

1.  **PostgreSQL is the Only Authority**
    - 모든 데이터의 진실(Truth)은 PostgreSQL에 있다.
    - Redis Projection은 PostgreSQL 데이터를 기반으로 생성된 **파생 뷰(Derived View)**이다.
    - Redis 데이터가 유실되어도 PostgreSQL에서 100% 복구 가능해야 한다.

2.  **No Write-Back**
    - 모든 쓰기(Write) 요청은 반드시 PostgreSQL에 먼저 커밋되어야 한다.
    - `Redis -> PostgreSQL` 방향의 동기화는 존재하지 않는다.

3.  **Redis is Optional**
    - Redis 장애는 서비스 장애가 아니다.
    - Redis 연결 실패 시 즉시 PostgreSQL로 Fallback하여 서비스를 지속한다.

### 3.1 Projection Authority Restrictions (Explicit Limits)
Projection(Redis)은 **UI Read Optimization 전용 View**이며, 다음 영역에서 **절대 사용되지 않는다**:

- **상태 전이(State Transition) 판단**: `APPLIED` -> `IN_PROGRESS` 등의 판단은 오직 PG의 상태를 기준으로 한다.
- **Engine 의사결정 로직**: 질문 순서 결정, 면접 종료 판단 등 Engine의 핵심 로직은 Projection을 신뢰하지 않는다.
- **정책 결정 (Policy Decision)**: Mode(Actual/Practice), Job Policy, Snapshot 관련 모든 판단은 PG 데이터를 기준으로 한다.
- **평가 계산 (Evaluation)**: 점수 산출 및 합격/불합격 여부는 PG 데이터만을 근거로 한다.
- **Admin Query의 기준 데이터**: 관리자 조회 시 필터링이나 정렬의 기준(Truth)으로 사용되지 않는다.
- **Domain 객체 대체**: Domain Logic 수행 시 Projection DTO를 Entity 대신 사용할 수 없다.

**결론적으로, 모든 의사결정은 반드시 PostgreSQL Aggregate 기반으로 수행되며, Projection은 Authority로 승격될 수 없다.**

## 4. Projection Architecture

### 4.1 Projection Data Structure
- **Key**: `proj:session:{session_id}`
- **Value**: JSON Serialized Object (UI Optimized View)
    - `session_id`
    - `status` (APPLIED, IN_PROGRESS, etc.)
    - `current_question` (if exists)
    - `progress` (answered_count / total_count)
    - `mode` (ACTUAL / PRACTICE)
    - `updated_at` (Timestamp)
- **Note**: 민감 정보나 Full History는 포함하지 않고, "현재 상태"를 빠르게 보여주기 위한 필드 위주로 구성한다.

### 4.2 Read-Through Strategy
1.  **Request**: Client 요청 -> API -> Service
2.  **Try Redis**: `GET proj:session:{session_id}`
    - **Hit**: Return Projection
    - **Miss**:
        1.  **Load from PG**: Repository에서 Aggregate 로드
        2.  **Reconstruct**: Domain Entity -> Projection DTO 변환
        3.  **Write to Redis**: `SETEX proj:session:{session_id} <TTL> <JSON>`
        4.  **Return**: 결과 반환
3.  **Error Handling**: Redis 조회/쓰기 실패 시 무시하고 PG 데이터 반환

### 4.3 Cache Stampede & Concurrency Strategy
**Selected Strategy: Option A (No Lock)**

- **정책 정의**: 동시 다발적 Read Miss 발생 시, **별도의 Lock 없이 중복 재생성(Redundant Reconstruction)**을 허용한다.
- **선택 이유**:
    - **Simplicity**: Projection은 단순 View 생성이므로 재생성 비용이 상대적으로 낮다.
    - **Avoid Helper Dependency**: Read 경로에서 Redis Lock 획득 대기로 인한 Latency 증가나 Deadlock 위험을 원천 배제한다.
    - **Availability First**: Redis 장애 또는 지연 시에도 PG 부하만 감당하면 즉시 응답 가능하다.
- **Fail-Fast / Idempotency와의 관계**:
    - CP0의 `RedisConcurrencyManager`(Write Lock)와는 무관하다. (Write는 Lock 필수, Read Projection은 Lock 불필요)
    - Projection 재생성은 Side Effect가 없는 Idempotent Operation이므로 중복 실행되어도 무해하다.

### 4.4 Write Policy (Write-Through / Invalidate)
- **Trust Source**: PostgreSQL Transaction Commit
- **Action**: DB 커밋 성공 후, Redis Projection **무효화(DEL)** 또는 **갱신(SET)**
- **Policy Choice**: **Invalidate First (DEL)**
    - 데이터 일관성을 위해 갱신보다는 삭제를 우선한다.
    - 다음 Read 요청 시 최신 데이터로 자연스럽게 재구성(Lazy Loading)된다.

## 5. Cache Invalidation & TTL

### 5.1 Invalidation Triggers
- **State Transition**: 상태 변경 (e.g., IN_PROGRESS -> COMPLETED)
- **Snapshot Update**: 질문 생성, 답변 제출 등으로 Snapshot 변경 시
- **Admin Action**: 관리자 강제 종료 등

### 5.2 TTL (Time-To-Live) strategy
- **Default TTL**: 30분 (세션 활성 시간 고려)
- **Reason**:
    - 불필요한 메모리 점유 방지
    - Invalidation 로직 실패 시 최후의 정합성 보장 수단(Eventual Consistency)

## 6. Redis Down Handling (Graceful Degradation)

- **Scenario**: Redis Connection Timeout / Refused
- **Behavior**:
    - Log Warning (Error가 아님)
    - Bypass Redis -> Direct PostgreSQL Query
    - 사용자 경험 저하 없음 (Latency 약간 증가 허용)
- **Circuit Breaker**: (Optional) 연속 실패 시 일정 시간 동안 Redis 시도 중단 가능

## 7. 문서 반영 계획 (Documentation Update Plan)

CP1 승인 후 구현 단계에서 아래 문서를 업데이트한다.

### 7.1 TASK_QUEUE.md
- **Current**:
    ```markdown
    ## DONE (CP0)
    ### TASK-027 Redis 세션 상태 도입
    ...
    - **Future CP (Not Started)**:
      - CP1: Projection Cache
    ```
- **Update To**:
    ```markdown
    ## ACTIVE
    ### TASK-027 / CP1 Session Projection Cache
    - **Status**: ACTIVE
    - **Goal**: Session Runtime Read Optimization
    - **Scope**: Projection Def, Read-Through, Invalidation, Fallback
    ```

### 7.2 CURRENT_STATE.md
- **Phase 9** 섹션에 **CP1: Projection Cache** 항목 추가
- 정의된 Projection 구조, 캐싱 전략, Authority 원칙 명시

## 8. 승인 게이트 (Approval Gates)

구현 착수 전 아래 조건이 만족되어야 한다.

- [ ] 본 Plan 문서가 사용자에게 승인됨
- [ ] CP0(PostgreSQL Authority) 원칙이 유지됨을 확인
- [ ] Write-Back이 포함되지 않았음을 확인
- [ ] Redis 장애 대응 전략이 포함됨을 확인
- [ ] **Projection이 Engine 의사결정에 사용되지 않음이 명문화됨**
- [ ] **Stampede 전략(No Lock)이 정의되고 Authority 침해가 없음이 확인됨**
- [ ] **PostgreSQL Authority 침해 가능성이 제거됨**
