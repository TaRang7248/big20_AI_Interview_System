# TASK-031_PLAN: Snapshot Immutability 실행 계획 (Contract Reinforced Version)

본 문서는 Phase 10 안정화 기준에 따라 **Snapshot DB 레벨 불변성 강제 및 갱신 차단**을 위한 최종 실행 계획이다. 본 계획은 시스템 전체의 **완성형 무결성 헌장(Integrity Charter)**으로서 기능하며, 모든 구현은 본 문서의 계약을 준수해야 한다.

---

## 0. 최상위 원칙 (Top Principles)

### 0.1 보호 대상 정의 및 확장 통제
- **보호 대상 (Protected)**: 
    - **Level 1 Template**: `job_policy_snapshot`
    - **Level 2 Instance**: `session_config_snapshot`
- **확장 통제 선언**: 
    - 상기 명시된 필드 외의 신규 필드는 자동 보호 대상이 되지 않는다.
    - Snapshot 계열 필드의 추가 및 보호 대상 확장은 별도의 **Phase 단위 승인 절차**를 거쳐야 한다.

### 0.2 정책 목적: 영속 기록 불변성
- 본 정책은 메모리 객체의 불변성이 아닌, **영속 저장소(DB)에 기록된 데이터의 물리적 불변성**을 강제한다.
- 관리자나 시스템의 실수로 인한 데이터 오염조차 DB 레벨의 방어 기제에 의해 거부되어야 한다.

### 0.3 Overwrite 전략: Physical Prevention
- **전략**: **Storage Block**. 저장소 계층에서 Snapshot 필드에 대한 `UPDATE` 시도 자체를 성공시키지 않는다.
- **동시성 무력화 (Concurrency Neutralization)**: Snapshot Overwrite는 허용되지 않으며, 발생 시 즉시 탐지 및 차단되어야 한다.

### 0.4 Snapshot 생성 원자성 (Atomicity)
- Snapshot 생성은 세션 생성 트랜잭션의 일부로 **원자적(Atomic)**으로 처리되어야 한다.
- 트랜잭션의 부분 성공(Partial Commit)은 허용되지 않으며, Snapshot과 세션 메타데이터는 운명을 같이한다.

---

## 1. Canonical Serialization 계약 (System Contract)

### 1.1 계약 및 책임 (Contract & Responsibility)
- **Canonical Serialization 승인 의무**: 직렬화 포맷의 변경은 단순 코드 배포가 아닌 **데이터 계층 아키텍처 변경**으로 간주하며, 사전 승인 및 바이트 단위 하위 호환성 분석 리포트가 필수이다.
- **오탐과 변조의 통합 차단**: 시스템은 물리적 바이트 차이가 발생하는 모든 경우를 **잠재적 변조 시도(Potential Tampering)**로 판단하여 즉시 차단(Fail-Fast)해야 한다.
- **사고 등급 분기 기준**: 차단 후 사후 분석을 통해 '값(Value)의 본질적 변경'이 확인되면 **Sev-1(Critical)**로, '표현(Representation)만의 차이'가 확인되면 **Sev-2(Major)**로 분류하여 대응한다. Sev-1은 즉시 격리 및 온콜 호출 대상이다. Sev-2는 격리 대상은 아니나, 지정 기한 내 분석 및 보고 대상이다.
- **변경의 책임**: 직렬화 로직 변경으로 인한 장애 발생 시, 이는 "오탐"이 아니라 변경 주체의 **"하위 호환성 검증 실패"**로 규정한다.
- **비교 기준 고정**: Canonical 정책이 변경되지 않는 한, Snapshot 비교 기준 또한 변경될 수 없다.
- **승인된 직렬화 변경 (Approved Canonical Change)**: 정상적인 배포, 라이브러리 교체, 직렬화 정책 변경에 의한 바이트 차이는 **"승인된 직렬화 변경"**으로 정의하며, 이는 감사 로그에 명시적 승인 기록(Approved Record)이 존재할 경우에 한해 예외적으로 허용된다. 단, 승인 기록이 부재할 경우 모든 불일치는 L3 위반으로 간주된다.

### 1.2 Strict Policy 체크리스트
- [ ] 직렬화 로직 변경 시, 기존 Snapshot과의 바이트 단위 일치 여부를 검증하는 절차가 존재하는가?
- [ ] 값은 동일하나 직렬화 결과가 다른 경우(공백, 정렬 등)에도 시스템이 이를 예외 없이 차단하는가?
- [ ] 차단된 데이터와 원본 데이터를 비교하여 오탐/변조 여부를 사후 판단할 수 있는 감사 로그가 남는가?

---

## 2. Layered Defense 구조 (Layered Defense Structure)

### 2.1 계층별 계약 (Layer Contracts)
- **L1 경고 조건 (Memory Consistency)**: 메모리에 로드된 Snapshot 객체가 저장 시점까지 원본 상태를 유지하지 못하고 변경이 감지될 경우, 비즈니스 로직의 결함으로 간주하여 **WARNING** 등급의 로그를 남겨야 한다.
- **L2 무시 조건 (Silent Preservation)**: Silent Preservation은 DB 값을 변경하지 않는다는 의미이며, 변경 시도(Log/Event)는 반드시 기록된다. 즉, 변경은 무시하되 기록은 남겨야 한다.
- **L3 위반 조건 (Persistence Violation)**: 애플리케이션 경로, 관리자 도구, 운영 스크립트 등 **수단과 방법을 불문하고**, 영속 저장소의 Snapshot 데이터에 대한 물리적 갱신 시도가 발생하는 즉시 이를 **위반(Violation)**으로 판정하고 트랜잭션을 롤백해야 한다.
- **시도 기준 방어 (Attempt Basis)**: L2와 L3는 값이 실제 변경되었는지(Change)가 아닌, 변경 시도가 발생했는지(Attempt)를 기준으로 작동한다. 따라서 기존 값과 동일한 값으로 `UPDATE`를 시도하더라도, Snapshot 컬럼이 쿼리에 포함된 것만으로도 계약 위반으로 간주한다. `UPSERT` 구문에서도 `DO UPDATE SET` 절에 Snapshot 컬럼이 포함되면 즉시 위반이다.

### 2.2 방어선 체크리스트
- [ ] L1 단계에서 메모리 상의 객체 변경 시도를 감지하여 경고 로그를 남기는가?
- [ ] L2 계층이 Snapshot 변경 요청을 무시하고 기존 데이터를 안전하게 보존하는가?
- [ ] 운영자가 직접 DB에 접속하여 UPDATE를 시도하더라도 L3 방어선에 의해 차단되는가?
- [ ] L2에서 Snapshot 변경 시도가 발생한 경우, 반드시 관측 가능한 기록(로그/이벤트)이 남는가?

---

## 3. Quarantine (Local Isolation) 정책

### 3.1 격리 및 기록 계약 (Isolation Contract)
- **Quarantine 정의**: 격리 상태는 해당 세션에 대해 **Read(조회)는 허용하되, Write(상태 전이 및 저장)는 전면 거부**됨을 의미한다. Quarantine은 상태 전이 로직을 변경하지 않으며, 쓰기 요청을 거부하는 운영 가드 상태일 뿐이다.
- **기록의 권위 (Authority Record)**: 격리 상태 정보는 반드시 시스템의 **권위 있는 상태 저장소(Authoritative Source)**에 영속적으로 기록되어야 하며, 휘발성 캐시나 메모리에만 존재해서는 안 된다.
- **운영 개입의 투명성**: 격리 해제, 세션 무효화, 강제 종료 등 운영자의 모든 개입 결정은 **"누가(Operator), 언제(Timestamp), 왜(Reason)"**를 포함한 감사 증적(Audit Trail)이 남아야만 실행 가능하다.

### 3.2 격리 정책 체크리스트
- [ ] 격리 상태가 캐시(Redis)가 아닌 영속 저장소(DB)의 권위 있는 레코드에 기록되는가?
- [ ] 격리된 세션에 대한 쓰기 요청이 비즈니스 로직 단계에서 확실하게 거부되는가?
- [ ] 운영자의 강제 개입 시 사유 입력 없이는 실행이 불가능하도록 절차가 마련되어 있는가?

---

## 4. 검증 설계 (Verification Strategy)

### 4.1 성공 판단 계약 (Success Contract)
- **성공 판단 기준 (Rejection Criteria)**: 검증의 성공은 단순히 "값이 변하지 않음"을 확인하는 것을 넘어, **"시스템이 변경 시도를 능동적으로 거부하고 실패 신호(Signal)를 발생시켰음"**을 관측해야 한다. 거부 신호(Signal)는 "요청이 성공으로 처리되지 않았음"이 외부적으로 확인 가능한 형태로 관측되어야 한다.
- **동시성 방어 입증**: 경쟁 상태(Race Condition) 시뮬레이션 후, 모든 트랜잭션이 종료된 시점에서 Snapshot의 **물리적 상태가 변경되지 않았음을 입증해야 한다.**
- **직렬화 엄격성 검증**: 직렬화 포맷 불일치 시나리오(D)에서도 L3 위반(C)과 동일한 수준의 **거부 신호 및 트랜잭션 롤백**이 관측되어야 하며, 이를 통과시키는 유연함은 허용되지 않는다.

### 4.2 검증 체크리스트
- [ ] 테스트가 "예외 발생 없음"이 아니라 "특정 거부 신호 발생"을 성공 조건으로 검증하는가?
- [ ] 동시성 테스트 후, Snapshot의 물리적 상태가 어떠한 방식으로도 변경되지 않았음을 확인하는가?
- [ ] 직렬화 포맷이 다를 경우(예: 공백 추가)에도 L3 위반과 동일하게 강력하게 차단되는가?

---

## 5. Authority First 정합성 (Consistency)

- **Authority vs Evidence**: 현재 상태(Authority) 갱신이 과거 증거(Capture)를 침해하려 할 경우, **Evidence Wins** 원칙에 따라 트랜잭션을 롤백한다.
- **Evidence vs Correction 분리**: Snapshot은 수정되지 않는다. 정정은 별도 기록으로만 허용된다.

---

## 6. 비범위 (Out of Scope)

- Snapshot 스키마 구조 변경.
- State Contract 및 Redis 관련 정책 변경.
- 평가 알고리즘 로직 변경.
- Correction Management Layer 구현.
