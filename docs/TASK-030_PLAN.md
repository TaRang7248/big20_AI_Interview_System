# TASK-030_PLAN: 상태 저장 원자성 및 PostgreSQL 권위 선행 보장

본 문서는 TASK-030 수행을 위한 전략 및 계약 명확화 계획서이다. Phase 10 감사 결과 식별된 R-1 위험(비원자적 이중 갱신)을 해소하고, PostgreSQL Authority 선행 구조를 확정하는 것을 목적으로 한다.

---

## 1. 문제 정의 (Problem Statement)

### 1.1 현재 상태 저장 흐름 요약
현재 `InterviewSessionEngine._update_status`를 포함한 상태 변경 흐름은 다음과 같다:
1. **메모리(Memory Context)**: 상태 값 변경
2. **Hot Storage (Redis)**: `state_repo.update_status()` 호출 (즉시 반영)
3. **Authority (PostgreSQL)**: `history_repo.update_interview_status()` 호출 (영속화)

### 1.2 Authority 위반 가능 시나리오 정의
*   **권위 역전**: PostgreSQL(Authority) 저장 시도 전 또는 도중에 Redis(Hot Storage)가 먼저 갱신됨에 따라, 시스템 오류 발생 시 Redis가 PG보다 최신 상태를 가지는 "권위 역전" 현상이 발생할 수 있다.
*   **Dirty Read 위험**: 외부 관측자(Admin API 등)가 PG에 확정되지 않은 런타임 중간 상태를 Redis를 통해 조회하게 되어 데이터 정합성 신뢰도가 저하될 수 있다.

### 1.3 Hot Storage ↔ PG 불일치 케이스 식별
*   PG 저장 실패 시에도 Redis에는 변경된 상태가 남아 있어, 세션이 비정상적인 상태로 지속되는 케이스.
*   네트워크 지연 또는 타임아웃으로 인해 PG 확정 여부가 불분명한 상태에서 Redis Mirror만 성공한 케이스.

---

## 2. 위험 시나리오 분석

### 2.1 감사 보고서 R-1 ~ R-5 연관성
*   **R-1 (MEDIUM)**: 핵심 대응 대상. 비원자적 이중 갱신으로 인한 Hot/Cold 불일치 위험 제거.
*   **R-4 (LOW)**: 상태 저장 시 JSONB 데이터(채팅 이력 등)가 동시 갱신되므로, 원자성 실패 시 대규모 데이터 이력 정합성 훼손 가능성 존재.

### 2.2 구체적 위험 시나리오
*   **PG 저장 실패 후 Redis 성공**: Authority 원칙 위반. 재시작 전까지 잘못된 상태로 유지됨.
*   **Redis 성공 후 PG 실패**: 트랜잭션 롤백이 불가능한 구조에서 Hot Storage 오염 발생.
*   **세션 상태 전이 도중 예외 발생**: 상태 변경 메서드 중간에 예외가 발생할 경우, 메모리/Redis/PG 중 어디까지 반영되었는지 추적 불가.
*   **동시 요청 상황에서의 상태 꼬임**: 동일 세션에 대해 짧은 간격으로 요청이 올 때, PG에 기록되기 전 Redis 상태를 보고 다음 단계가 진행되는 잠재적 레이스 컨디션.

---

## 3. 원자성 보장 계약 정의 (Atomic Contract Definition)

### 3.1 상태 전이 순서 강제 (Order of Operations)
상태 저장 시 반드시 다음 순서를 지켜야 한다:
1.  **Stage 1: Authority Enforcement (PG)**: PG 트랜잭션 내에서 상태 및 이력을 원자적으로 영속화.
2.  **Stage 2: Hot Storage Mirroring (Redis)**: PG 커밋 성공 확인 후 Redis/Memory 반영.
3.  **Stage 3: Post-Commit Operations**: 관측 데이터(Projection/Stats) 갱신 및 외부 트리거 실행.
4.  **Stage 4: Lock Release**: 모든 확정 및 전파 작업 완료 후 런타임 락 해제.

### 3.2 Authority Enforcement Contract
*   **단일 트랜잭션 단위**: 세션 상태(`status`), 채팅 이력(`chat_history`), 갱신 시점(`progress_updated_at`)은 반드시 단일 PostgreSQL 트랜잭션 내에서 원자적으로 처리되어야 한다.
*   **엔진 통제권**: 트랜잭션의 시작과 종료(Commit/Rollback) 경계는 Repository Layer가 아닌 `InterviewSessionEngine` 레벨에서 명시적으로 통제한다.
*   **부분 Commit 금지**: 상태 정보 중 일부만 저장되거나, 이력 데이터 없이 상태만 갱신되는 "부분 성공" 상태를 철저히 차단한다.

### 3.3 동시성 제어 및 락 계약 (Concurrency Contract)
*   **락-전이 순서**: 런타임 분산 락(Redis Lock) 획득이 선행되어야 하며, PostgreSQL Authority 갱신 시도 전후로 해당 세션에 대한 원자적 점유를 유지한다.
*   **재진입 금지**: 동일 세션에 대해 이전 상태의 PG Commit이 완료되지 않은 상태에서 다음 상태로의 전이 요청은 즉시 거부한다.
*   **확정 상태 기반 전이**: 모든 상태 전이 결정은 오직 PG에 확정된(Committed) 최신 상태값을 기준으로만 수행한다.

#### Visibility Barrier Contract
*   **락 해제 시점**: 락 해제는 반드시 다음 조건이 모두 충족된 이후에만 수행한다:
    *   (a) PostgreSQL Commit 완료
    *   (b) Redis Hot Storage Mirroring 시도 (성공 여부와 무관하게 Authority 확정 시 성공으로 간주)
    *   (c) 외부 관측 가능 상태(Projection 등)가 PG 기준으로 최소한의 정합성을 확보
*   **전파 완료의 정의**: 락 해제를 위한 전파 완료(Propagation Completion) 정의는 **Authority(PG) 확정**을 최종 기준으로 한다.
*   **예외 케이스**: Mirroring 실패 시에도 락을 무기한 보류하지 않으며, 외부 관측은 **Projection Subset + Authority Dependency** 계약에 의해 안전하게 제한된 상태로 재개된다.
*   **관측 차단**: 락 해제 이전에는 어떠한 외부 트리거(Event 발행, Projection 갱신 요청, Admin Read Path)도 해당 세션의 "신규 확정 상태"를 관측할 수 없어야 한다. 락은 상태 전이의 시작부터 전파 완료까지를 보호하는 "가시성 장벽" 역할을 수행한다.
*   **External Triggers 정의**: Projection/Stats 갱신, Event 발행, Admin Read Path의 신규 상태 가시화에 영향을 주는 모든 후행 작업을 의미한다. 단, 단순 로깅 및 메트릭 수집은 이에 포함되지 않으며, Authority/Visibility 계약을 침범하지 않는 한 허용된다.

### 3.4 Panic / Rollback 정책
*   **Rollback 정의**: 원자성 실패 시의 롤백은 "PostgreSQL에 확정되지 않은 런타임 메모리 상태의 폐기"로 한정한다. 
*   **모델 보존**: 롤백 시 새로운 임시 상태값을 도입하지 않으며, 기존 상태 전이 엔진의 계약을 침범하지 않는다.
*   **Panic 정의**: 복구 불가능한 정합성 위협 감지 시, 상태 전이 모델을 변경하는 대신 "해당 세션의 운영 즉시 중단" 처리를 수행한다. 이는 비즈니스 로직이 아닌 시스템 운영 제어 계층의 동작이다.

### 3.5 Redis Mirroring 실패 판정 계약
*   **성공 판정 기준**: PostgreSQL Commit이 성공했다면, 이후 Redis Mirroring 단계에서 실패가 발생하더라도 해당 **상태 전이는 최종적으로 성공**한 것으로 간주한다. (Authority First 원칙)
*   **가용성 이슈 처리**: Mirroring 실패는 일시적인 "가용성 이슈"이며, 이후 Hydration으로 복구될 수 있다는 신뢰를 전파 완료 정의에 포함한다.
*   **최종 성공의 정의**: Authority(PG)에 기록된 값이 시스템의 최종 진실이며, 런타임 캐시(Redis)의 누락은 일시적 이슈로 취급한다.
*   **자기 치유**: Mirroring에 실패한 Redis 데이터는 다음 요청 시의 Hydration 또는 재시작 시의 Recovery 과정을 통해 PG 기준으로 반드시 복구되어야 함을 보장한다.

---

## 4. 정합성 보장 전략 (Consistency Enforcement Strategy)

### 4.1 Redis Miss Hydration과의 관계
*   Redis 데이터 유실 또는 불일치 감지 시, 항상 PostgreSQL(Authority)에서 데이터를 읽어와 Redis를 재구성(Hydration)한다.
*   Hydration은 상태 전이 시 PG 저장 단계 직후에 수행되는 "Mirroring"과 동일한 신뢰 수준을 가져야 한다.

### 4.2 Cold-Start Recovery Guarantee
*   서버 재시작(Cold-Start) 시, Redis의 어떠한 데이터도 신뢰하지 않으며 오직 PostgreSQL의 최종 상태만을 시스템의 유일한 진실로 수용하여 런타임을 재구성한다.
*   `pg_state_repo` 미주입 시 상태 갱신을 동반하는 모든 세션 동작을 거부(Guard)한다.

### 4.3 관측 / Projection 차단 및 부분 실패 범위

#### Projection Subset Contract
*   **부분 집합 원칙**: Projection(관리자 조회용 데이터, 통계 등)은 항상 PostgreSQL 확정 상태의 **"부분 집합(Subset)"**이어야 한다.
*   **선행 금지**: Projection은 어떠한 경우에도 PostgreSQL보다 앞선 상태(Future State)를 표현할 수 없다. 
*   **지연 허용**: 시스템 부하 등의 사유로 Projection 갱신이 지연되는 것은 허용되나, 이는 최신성(Freshness)의 문제이지 정합성(Consistency)의 위반이 아니다.
*   **목표**: Projection 데이터는 "최신성 보장"이 아니라 **"권위 종속성 보장(Authority Dependency)"**을 최우선 목표로 한다.
*   **Dirty Read 방지**: "PG에 없는 상태가 노출되는 현상(Dirty Read)"은 절대 허용되지 않으며, 단순한 지연(Stale Read)과 엄격히 구분한다.

---

## 5. 검증 전략 (Verification Strategy)

### 5.1 테스트 시나리오 목록
1.  **정상 흐름 검증**: PG Transaction Start -> Commit -> Redis Mirror -> Lock Release 순서 검증.
2.  **PG 장애 유도**: PG 저장 시 Exception 발생 시, Redis/Memory 갱신이 생략되고 기존 상태가 유지되는지 확인.
3.  **부분 실패 유도**: 이력 데이터만 누락되는 상황을 가정하여 전체 트랜잭션이 롤백되는지 검증.
4.  **동시성 검사**: Commit 이전 시점에 발생한 중복 요청이 락에 의해 차단되고 PG 데이터 오염이 없는지 확인.

### 5.2 불일치 확인 방법
*   저장 완료 후 PG와 Redis의 상태값을 직접 비교하는 Consistency Checker(Verification Script) 실행.
*   `scripts/verify_task_030.py`를 통한 자동화된 장애 주입 테스트.

---

## 6. 비범위 명확화 (Out of Scope)

*   **API 변경 없음**: 외부 노출 API 엔드포인트나 응답 스키마는 변경하지 않는다.
*   **평가 엔진 변경 없음**: 점수 산출 로직이나 루브릭은 본 작업의 범위가 아니다.
*   **Snapshot 구조 변경 없음**: `job_policy_snapshot` 등의 필드 구성은 변경하지 않는다. (TASK-031에서 별도 처리)
*   **세션 상태 계약 변경 없음**: 기존의 `APPLIED -> IN_PROGRESS -> COMPLETED` 상태 모델은 유지한다.
*   **신규 기능 추가 없음**: 알림, 메시징 등 새로운 기능적 요구사항은 포함하지 않는다.

---

## 7. Non-Regression Guarantee

*   본 계획의 모든 변경 사항은 TASK-029(Baseline Alignment)에서 확립된 PostgreSQL Authority 및 Redis Hydration 계약을 위반하지 않으며, 이를 더욱 강화하는 상위 집합적 성격을 가진다.
*   기존의 `postgresql_repo`와 `history_repo` 간의 책임 분리 모델을 존중하며, 엔진 레벨의 오케스트레이션만을 개선한다.

---

## 8. Exit Criteria / Acceptance Criteria

### 8.1 핵심 불변식 (Invariants)
*   [ ] **Authority Invariant**: 어떤 시점에도 Redis의 세션 상태가 PostgreSQL의 상태보다 선행(Ahead)하여 존재할 수 없다. (State(Redis) <= State(PG))
    *   *전제*: 상태는 전순서(orderable)인 finite enum이며, 비교는 "상태 단계(status)" 기준으로만 수행한다. 부가 진행도(질문 index 등)는 본 불변식의 비교 대상이 아니다.
*   [ ] **Observability Invariant**: PostgreSQL에 Commit되지 않은 중간 상태(In-flight state)는 Projection, 통계, 관리자 API를 통해 외부로 노출되지 않는다.
*   [ ] **Subset Invariant**: 프로젝션 데이터는 항상 PG 확정 데이터의 부분 집합이며, PG에 없는 가공된 상태를 표현하지 않는다.

### 8.2 검증 통과 요건
*   [ ] **장애 일관성**: PG Commit 실패 시 시스템은 항상 이전 확정 상태로 완벽히 롤백되며, Redis Mirroring 단계로 진입하지 않음을 확인한다.
*   [ ] **Authority 승리**: PG Commit 성공 후 Redis 반영 실패 시, 다음 요청 시점에 Hydration을 통해 Redis가 PG 기준으로 복구됨을 확인한다.
*   [ ] **순서 보장**: 로그 분석을 통해 `PG COMMIT` 메시지가 `REDIS UPDATE` 메시지보다 항상 먼저 기록됨을 확인한다.
*   [ ] **가시성 통제**: 락 해제 전에는 관리자 조회 경로가 신규 상태를 절대 인지하지 못함을 장애 주입을 통해 검증한다.

### 8.3 verify_task_030 시나리오 범위
*   **Scenario A**: 정상 상태 변경 시 PG -> Redis 순차 저장 기록 확인.
*   **Scenario B**: PG 저장 강제 에러 주입 시 Redis 상태 불변 확인.
*   **Scenario C**: PG 커밋 후 Redis 업데이트 강제 에러 주입 시, 최종 상태성공 판정 및 차후 Hydration 복구 확인.
*   **Scenario D**: 다중 스레드/프로세스 환경에서 락 획득 대기 중 PG 확정 전 상태 노출 차단 확인.
