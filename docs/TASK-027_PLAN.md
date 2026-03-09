# TASK-027: Redis 도입 (Checkpoint 0) - Baseline Contract (v8)

> **v8 변경점 (Changelog)**:
> 1. **Pause/Resume**: Redis의 Pause는 상태 전이가 아닌 '운영 플래그'임을 명시하고, Resume 시 PG 스냅샷 불일치 시 Fail-Fast/Rehydrate 처리를 강제함.
> 2. **Lock TTL**: 만료 시 낙관적 실패가 아닌, PG Commit 단계의 정합성 검증을 통한 명확한 'Command 실패'로 규정.
> 3. **Hydration**: '상태 변경'이 아닌 'Mirror 복원'임을 명시하고, 불일치 판단 권한이 오직 PG에 있음을 선언.

이 문서는 **PostgreSQL**과 **Redis**의 역할 분담과 데이터 정합성을 보장하기 위한 **Checkpoint 0 (CP0)** 단계의 Baseline 계약을 정의한다.
CP0는 기능 구현이 아닌, **Runtime State Layer**와 **Control Layer**의 아키텍처 원칙을 확립하는 것에 목적이 있다.

---

## 1. CP0 Scope 정의

### 1.1 포함 범위 (In-Scope)
| Layer | 항목 | 설명 |
| :--- | :--- | :--- |
| **Runtime State** | Session Mirroring | 진행 중인 세션의 상태(Step, Timer)를 Redis에 단순 복제(Mirror)하여 조회 성능 확보 (No Write-Back)|
| **Control Layer** | Distributed Lock | `interview_id` 단위의 분산 락을 통한 동시성 제어 (TTL 기반) |
| | Idempotency | `request_id` 기반의 동일 Command 중복 실행 방지 및 결과 재반환 |
| **Contract** | Fail-Safe Policy | Redis 장애 시 시스템의 안전한 동작(Fail-Fast/Reject) 정의 |
| | Hydration | 서버 재기동 시 PostgreSQL → Redis 단방향 상태 복원 기준 수립 |

### 1.2 제외 범위 (Out of Scope - CP0 이후 단계)
> 다음 항목들은 CP0 단계에서 절대 다루지 않으며, CP1 이후의 확장 과제로 분류한다.

-   **Projection Cache**: 세션 뷰, 질문 목록 등의 Read-Through 캐싱.
-   **RAG / Candidate / Prompt Cache**: 벡터 검색 결과, 질문 후보군, 프롬프트 템플릿 등의 연산 캐싱.
-   **Statistical Analysis**: Redis 기반의 실시간 통계 집계.
-   **Dual Write Removal**: PostgreSQL 쓰기 제거 및 Redis 단독 쓰기 전환 (CP0에서는 절대 금지).
-   **PostgreSQL Schema Change**: 기존 테이블 구조 변경 없음.

---

## 2. PostgreSQL vs Redis 책임 경계 (Responsibility Boundary)

시스템의 데이터 무결성을 위해 두 저장소의 책임을 엄격히 분리한다.

### 2.1 PostgreSQL (The Only Source of Truth)
-   **영속성 보장**: 모든 비즈니스 데이터의 유일한 **영속 저장소(Persistent Store)**이다.
-   **결정 권한(Authority)**: 세션의 상태 전이(State Transition), 평가(Evaluation), 완료(Completion) 여부를 결정하는 유일한 기준이다.
-   **복구 기준점**: 시스템 재기동, Redis 데이터 유실, 정합성 불일치 발생 시 상태 복구의 **절대적 기준(Snapshot)**이다.

### 2.2 Redis (Transient Runtime State & Control)
-   **휘발성(Transient)**: 데이터 유실이 허용되는 **일시적 저장소**이다.
-   **경쟁 제어(Concurrency)**: API 요청의 순서 보장 및 동시 접근 차단(Lock)을 담당한다.
-   **고속 접근(Fast Access)**: 빈번한 상태 조회 요청을 처리하여 DB 부하를 경감한다.
-   **미확정 상태(Pending)**: 트랜잭션 완료 전의 임시 상태나 TTL이 필요한 단기 데이터를 관리한다.

### 2.3 불변의 법칙 (Immutable Rules)
1.  **No Write-Back**: Redis의 데이터 변경 사항은 **절대 PostgreSQL로 역방향 반영되지 않는다.**
2.  **Unidirectional Hydration**: 데이터 흐름은 항상 `PostgreSQL → Redis` 방향으로만 흐른다. (초기화 및 복구 시)
3.  **Prioritize Persistence**: PostgreSQL 트랜잭션 성공이 보장된 후에만 Redis 상태를 갱신한다.

---

## 3. Control Layer 계약

### 3.1 Distributed Lock Model
-   **Unit**: `interview_id` 단위로 Lock을 획득한다.
-   **TTL Strategy**:
    -   Lock 획득 시 **최소-필요 시간(Minimum Required Time)**만큼만 TTL을 설정한다.
    -   API 처리 시간 초과 시 Lock은 자동 해제되나, 이는 정상적인 작업 완료가 아님을 의미한다.
-   **Split-Brain Prevention**:
    -   Lock TTL 만료로 인해 Lock이 해제된 경우, 해당 작업은 **PostgreSQL Commit 단계에서 반드시 실패 처리**되어야 한다.
    -   낙관적 실패(Optimistic Failure)가 아닌, **PG 정합성 검증(Cas/Version Check)에 의한 명확한 Command Failure**로 규정한다.
-   **Release**: 작업 완료 즉시 명시적으로 해제(Release)한다.

### 3.2 Idempotency (멱등성)
-   **Key**: Client가 생성한 `request_id` (UUID)를 기준으로 중복 여부를 판단한다.
-   **Scope**: 상태를 변경하는 모든 Command (Next Step, Submit Answer 등).
-   **Behavior**:
    -   처리 중인 요청: `429 Too Many Requests` or `Wait`
    -   처리 완료된 요청: 저장된 성공 결과(Response)를 그대로 반환.
    -   최초 요청: 정상 처리 진행.

### 3.3 Fail-Fast Policy
-   **Lock Acquisition Failure**: `423 Locked` 또는 `503 Service Unavailable`을 즉시 반환한다. (대기열 없음)
-   **Redis Down**: Control Layer 기능(Lock/Idempotency)이 작동 불가능할 경우, **쓰기 요청을 전면 차단(Reject)**하여 데이터 오염을 방지한다.

---

## 4. Runtime Layer 계약

### 4.1 Write Order Protocol (절대 순서)
상태 변경 요청 처리 시 다음 순서를 엄격히 준수한다.

1.  **PostgreSQL Commit**: DB 트랜잭션을 통해 상태 변경을 영속화하고 커밋을 완료한다.
2.  **Redis Mirror Update**: 커밋된 최신 상태(Snapshot)를 Redis `RuntimeState` 키에 덮어쓴다(Overwrite).

> **주의**: 1번 실패 시 2번은 실행되지 않으며, 2번 실패 시(Redis 장애) 1번 성공은 유효하나, 다음 조회 시 Hydration을 통해 복구되어야 한다.

### 4.2 Mirroring & TTL Strategy
-   **Content**: 진행 중인 인터뷰의 필수 메타데이터 (Step, Status, Timer Start/Duration).
-   **TTL**: 마지막 활동(Activity) 기준 `Session Timeout` 시간(예: 30분)으로 갱신한다.

### 4.3 Pause / Resume Protocol (Operational State)
-   **Not a State Transition**: Pause는 Redis의 Runtime Flag 및 TTL 관리 범위의 "운영 상태"이며, **Phase 5 정의 State Transition(상태 전이)에 해당하지 않는다.**
-   **No Authority**: Pause 상태 진입/해제는 PostgreSQL의 `status`나 `snapshot`을 변경하지 않는다. Redis는 이 상태에 대한 결정 권한(Authority)이 없다.
-   **Resume Validation**: 재개(Resume) 시, 반드시 Redis 상태가 아닌 **PostgreSQL 최신 Snapshot과 대조하여 검증**해야 한다.
    -   **검증 성공**: Redis TTL 갱신 및 Runtime Flag 해제.
    -   **검증 실패**: 요청 즉시 **거부(Reject)** 및 현재 PG 상태 기반 **강제 재수화(Rehydrate)** 수행.

### 4.4 Hydration (Mirror Restoration)
-   **Definition**: Hydration은 "상태 변경"이 아니라, 유실되거나 오염된 Redis Mirror를 PG 기준으로 복구하는 **"복원 작업"**이다.
-   **Trigger**:
    1.  Redis Key Miss (데이터 유실)
    2.  **Inconsistency Detection** (정합성 불일치 감지)
-   **Authority**: 불일치 여부의 판단과 최종 데이터의 기준은 오직 **PostgreSQL**에 있다. Redis 데이터는 판단 근거가 될 수 없다.
-   **Action**: 무조건 PostgreSQL 데이터를 Redis에 **덮어쓰기(Overwrite/Set)** 한다. (Update나 Merge 금지)

---

## 5. 장애 및 멱등성 시나리오 (Scenarios)

검증 및 테스트 시 다음 시나리오를 반드시 확인해야 한다.

| No | 시나리오 | 기대 동작 (Expected Behavior) | 비고 |
| :--- | :--- | :--- | :--- |
| **1** | **PG 성공 / Redis 실패** | **성공 (Success)**. Client에게 정상 응답. <br> 다음 요청 시 Hydration으로 Redis 상태 자동 복구. | Redis는 보조 저장소임 |
| **2** | **PG 실패 / Redis 성공** | **발생 불가 (Impossible)**. <br> Write Order 계약에 따라 PG 실패 시 Redis 갱신 시도조차 없어야 함. | 코드 레벨 검증 필수 |
| **3** | **Lock 만료 후 실행** | **실패 (Failure)**. <br> Lock 해제 후 실행된 PG Commit 시도가 정합성 검증에서 탈락하며 실패 처리. | Split-Brain 방지 |
| **4** | **중복 요청 동시 도착** | **선행 요청 성공 / 후행 요청 거부**. <br> Idempotency Key 확인을 통해 중복 실행 방지. | 데이터 오염 방지 |
| **5** | **서버 재기동 직후** | **Hydration 수행**. <br> 첫 요청 처리 시 Redis Miss → PG 조회 및 Mirror 복원 → 정상 처리. | 무중단 서비스 |

---

## 6. CP0 승인 게이트 (Approval Gates)

다음 조건이 모두 충족되어야만 Checkpoint 0 이 구현 완료된 것으로 승인한다.

-   [ ] **PostgreSQL Contract Invariant**: 기존 PG 기반의 저장/조회 로직이 100% 유지되는가?
-   [ ] **Fixed Write Order**: 코드 상에서 `PG Commit` -> `Redis Update` 순서가 강제되어 있는가?
-   [ ] **No Write-Back Verified**: Redis 데이터를 PG로 Update하는 로직이 전무한가?
-   [ ] **Restart/Replay Safety**: Redis 전체 데이터 삭제 후에도 PG 데이터만으로 서비스 재개가 가능한가?
-   [ ] **Fail-Fast Compliance**: Redis 연결 끊김 시 쓰기 요청이 안전하게 거부(Safe Fail)되는가?

---

## 7. Documentation Gate (문서화 요구사항)

CP0 구현 진행 전/후로 다음 문서가 갱신되어야 한다. (실제 작성은 구현 단계에서 수행)

-   **TASK-027_PLAN.md**: 본 문서의 내용이 v8 이상으로 확정.
-   **CURRENT_STATE.md**: Redis 도입 상태(CP0) 및 아키텍처 다이어그램 업데이트.
-   **TASK_QUEUE.md**: TASK-027의 상태를 `ACTIVE` -> `IN_PROGRESS` -> `DONE` (CP0) 으로 단계적 반영.
