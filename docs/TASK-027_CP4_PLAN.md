# TASK-027 / CP4 – Prompt Composition Cache Plan Only

본 문서는 TASK-027의 Checkpoint 4 (CP4) 단계인 Prompt Composition Cache 도입을 위한 계획(Plan) 문서이다.
이 문서는 Redis를 통한 Prompt 구성 비용 절감을 목표로 하되, 기존 시스템의 Authority 및 정합성 계약을 철저히 준수하는 것을 원칙으로 한다.

## 전제 조건 (Prerequisites)

본 계획은 다음 전제 조건하에 수립된다.

-   **CP0 ~ CP3 LOCKED**: 이전 단계의 모든 계약과 구현은 변경 불가능한 상태(LOCKED)이다.
-   **PostgreSQL Authority 절대 침해 금지**: 모든 데이터의 원본 권한은 PostgreSQL에 있다.
-   **Write Order (PG → Redis) 변경 금지**: 반드시 PG에 먼저 쓰고, 그 후 Redis에 반영한다.
-   **No Write-Back 계약 유지**: Redis의 데이터는 절대 PG로 역류하지 않는다.
-   **Snapshot Double Lock 구조 변경 금지**: 기존 Snapshot 보호 메커니즘을 유지한다.
-   **Job Policy Freeze 계약 침해 금지**: Job 실행 시 확정된 Policy는 변경되지 않는다.
-   **Evaluation Schema 변경 금지**: 평가 로직 및 스키마는 본 작업의 범위가 아니다.
-   **Redis는 Read Optimization Layer이다**: Redis는 저장소가 아닌 최적화 계층이다.
-   **Redis는 결과 저장소가 아니다**: 최종 결과는 반드시 PG에 저장된다.

---

## 1. CP4 Scope 정의

### 1.1 In Scope (포함 범위)
-   **Prompt Composition 결과 캐싱 전략**: LLM 호출 직전 완성된 프롬프트 텍스트의 캐싱.
-   **Cache Key 설계 원칙 (개념 수준)**: Snapshot ID 등을 포함한 Key 구조 원칙 수립.
-   **Snapshot 기반 Cache Segmentation 전략**: Snapshot 변경에 따른 캐시 분리 전략.
-   **TTL 전략 정의**: 캐시의 생명주기 및 만료 정책.
-   **Redis Down 대응 정책**: Redis 장애 시 Fail-Open 처리.
-   **Evaluation Engine 및 Result 정합성 보호 전략**: 평가 결과의 무결성 보장.

### 1.2 Out of Scope (제외 범위)
-   **Engine 구조 변경**: 기존 Evaluation Engine 로직 수정 불가.
-   **Service Layer 수정**: Core Service 로직 변경 불가.
-   **Snapshot 구조 변경**: Snapshot Entity 및 프로세스 수정 불가.
-   **Evaluation Schema 수정**: Database Schema 변경 불가.
-   **PostgreSQL 테이블 변경**: 어떠한 Table 변경도 없음.
-   **Write Order 변경**: 기존 Write Order 로직 수정 불가.
-   **Policy Engine 변경**: Policy 관련 로직 수정 불가.

---

## 2. Prompt Cache Authority 제한 명문화

Prompt Cache는 성능 최적화를 위한 보조 수단이며, 어떠한 권한(Authority)도 가지지 않는다.

1.  **Prompt Cache는 Derived Data이다**: 원본 데이터가 아니며, 언제든 PG 데이터로부터 재생성 가능하다.
2.  **Cache는 언제든 폐기 가능해야 한다**: 데이터 유실이 시스템 정합성에 영향을 주지 않아야 한다.
3.  **Cache는 평가 점수 산출 근거가 아니다**: 평가는 반드시 원본 Snapshot과 Schema를 기준으로 수행된다.
4.  **Cache 미존재 시 반드시 원본 Snapshot + PG 데이터 기반 재구성해야 한다**: Fallback 로직이 필수적이다.
5.  **Cache는 절대 Evaluation 결과를 선행 생성하지 않는다**: 평가는 실시간으로 Engine에 의해 수행되어야 한다.

---

## 3. Session Snapshot과의 관계 정의

Prompt Cache는 Session Snapshot에 강하게 종속되지만, Snapshot 그 자체는 아니다.

1.  **Prompt Cache는 Snapshot의 복사본이 아니다**: Snapshot 데이터를 기반으로 생성된 가공물(Outcome)이다.
2.  **Snapshot ID를 Key 분리 기준으로 사용한다**: 동일 세션이라도 Snapshot ID가 다르면 다른 캐시로 취급한다.
3.  **Snapshot 변경 시 Cache 자동 무효화 전략을 정의한다**: Snapshot 버전이 올라가면 이전 캐시는 즉시 무효화되거나 접근 불가능해야 한다.
4.  **동일 Session이라도 Snapshot Version이 다르면 Cache 재사용 금지한다**: 과거 Snapshot 기반의 프롬프트가 현재 평가에 사용되어서는 안 된다.
5.  **Snapshot Immutable 계약 유지 전략을 명시한다**: 캐시 적용 과정에서 Snapshot의 불변성을 해치는 어떠한 시도도 금지한다.

---

## 4. Cache Invalidation 정책

데이터 정합성을 위해 적극적이고 보수적인 무효화(Invalidation) 정책을 적용한다.

1.  **Snapshot Version 기반 무효화**: Snapshot ID 변경 시 해당 세션의 기존 캐시는 논리적으로 무효화된다.
2.  **Persona 변경 시 무효화**: 인터뷰 페르소나 설정 변경 시 관련 캐시는 모두 폐기된다.
3.  **Job Policy Snapshot 변경 시 무효화**: Job Policy가 변경되면 기존 프롬프트 캐시는 사용할 수 없다.
4.  **Interview Mode 변경 시 무효화**: 모드 변경(예: 연습 -> 실전) 시 캐시는 공유되지 않는다.
5.  **TTL 기반 자연 소멸 전략**: 불필요한 메모리 점유를 막기 위해 적절한 TTL을 설정하여 자연 소멸시킨다.
6.  **Manual Invalidation 경로 정의**: 운영자 개입이나 긴급 상황 시 특정 캐시를 강제로 날릴 수 있는 경로를 확보한다.

---

## 5. Redis Down 처리 정책

Redis는 보조 계층이므로, 장애가 전체 서비스 장애로 이어져서는 안 된다.

1.  **Redis 장애 시 Prompt Composition은 반드시 정상 동작해야 한다**: 캐시가 없으면 원본 로직을 통해 프롬프트를 생성한다.
2.  **Cache 접근 실패는 WARN 로그만 남긴다**: Error 레벨이 아닌 Warn 레벨로 로깅하여 모니터링하되, 프로세스는 진행한다.
3.  **Fail-Open 전략을 적용한다**: Redis 연결 실패 예외를 Catch하여 무시하고, 원본 로직을 수행(Pass-through)한다.
4.  **Redis 의존으로 인해 세션이 실패하면 안 된다**: 사용자의 인터뷰 진행에 영향을 주지 않아야 한다.
5.  **PG Authority 경로는 절대 영향받지 않는다**: PG에 데이터를 쓰고 읽는 Core Path는 Redis 상태와 무관하게 동작해야 한다.

---

## 6. Evaluation Engine 및 Result 정합성 보호 전략

평가(Evaluation)는 시스템의 핵심 가치이므로, 캐시 도입이 결과에 영향을 주어서는 안 된다.

1.  **Prompt Cache는 Evaluation Input을 변경하지 않는다**: 캐시된 데이터가 입력값을 변조해서는 안 된다.
2.  **Cache 사용 여부에 관계없이 동일 Snapshot → 동일 Evaluation 결과를 보장한다**: 캐시 미스/히트 상황에서 동일한 결과가 나와야 한다.
3.  **Deterministic 입력 유지 전략을 명시한다**: 프롬프트 생성 로직은 항상 결정론적(Deterministic)이어야 하며, 캐시는 이를 그대로 저장해야 한다.
4.  **Evidence Data는 반드시 PG 기반 데이터에서 생성한다**: 감사(Audit)나 증적 자료는 캐시가 아닌 PG 원본 데이터로 생성한다.
5.  **Cache된 Prompt가 Evidence Source가 되지 않도록 명문화한다**: 캐시 데이터는 신뢰할 수 있는 Source of Truth가 아니다.

---

## 7. Write Order 보호 전략

데이터 흐름의 일관성을 위해 Write Order를 엄격히 준수한다.

1.  **Prompt Cache는 Write Order 체계에 포함되지 않는다**: Prompt는 Read 시점에 생성되어 캐싱되는 Read-Through 또는 Lazy-Loading 구조이므로, Transactional Write Order와는 무관해야 한다. (단, 무효화는 Write 시점에 발생 가능)
2.  **PG → Redis 순서를 변경하지 않는다**: 데이터 변경 발생 시 PG Commit이 먼저이고, 그 후 Redis 갱신/무효화가 일어난다.
3.  **Cache Write는 비권위적 보조 행위임을 명시한다**: 캐시 쓰기 실패가 트랜잭션 롤백을 유발하지 않는다.
4.  **Redis에만 존재하는 데이터가 생기지 않도록 제한한다**: 모든 데이터는 PG에서 복원 가능해야 한다.

---

## 8. 승인 게이트 (Approval Gates)

본 Plan에 따른 구현은 다음 승인 기준을 모두 만족해야만 완료로 인정된다.

### 승인 기준:
1.  **PostgreSQL Authority 침해 없음이 명문화되었는가**: 코드로 검증 가능해야 함.
2.  **Snapshot Immutable 계약 유지가 보장되었는가**: Snapshot 변조 없음 확인.
3.  **No Write-Back 원칙 위반 가능성이 제거되었는가**: 역방향 데이터 흐름 부재 확인.
4.  **Evaluation 결과 비결정성 요소가 제거되었는가**: 동일 입력-동일 출력 보장.
5.  **Redis Down 시 시스템 정상 동작이 보장되었는가**: Fail-Open 테스트 통과.
6.  **CP0~CP3와의 충돌이 없는가**: 기존 계약 준수 확인.

**위 승인 조건을 만족한 이후에만 IMPLEMENT 단계로 전환한다.**

---

## 9. 보강 섹션: 운영 안정성 및 보안 강화 (Supplementary Section)

본 섹션은 초기 CP4 Plan의 계약 및 원칙을 유지하면서, 운영 안정성, 보안, 성능, 관측 가능성 측면을 구체적으로 보강한 내용이다.

### 9.1 Cache Key 입력요소 완전성 선언

Prompt 구성의 정합성을 보장하기 위해 Cache Key는 다음 요소를 반드시 포함해야 한다. Key 구성 요소 중 하나라도 변경되면 기존 Cache는 재사용할 수 없다. 이는 Key 불완전성으로 인한 Cache 오염을 방지하기 위함이다.

**필수 포함 논리적 입력 요소:**
-   **Snapshot ID / Snapshot Version**: 세션 상태의 고유 식별자.
-   **Persona 세부 설정**: 인터뷰 대상 페르소나의 ID 및 설정 버전.
-   **Interview Mode**: 연습(Practice) 모드와 실전(Real) 모드의 구분.
-   **Job Policy Snapshot**: 해당 세션에 적용된 Job Policy의 불변 스냅샷.
-   **Prompt Template Version**: 시스템 프롬프트 및 템플릿의 버전 정보.
-   **LLM 모델 식별자**: 호출 대상 LLM 모델의 정확한 식별자 (버전 포함).
-   **RAG 사용 여부 및 관련 전략 버전**: RAG 사용 유무 및 Retrieval 전략의 버전.

### 9.2 Cache Stampede / Thundering Herd 방지 전략

고트래픽 상황에서 TTL 만료 시 발생할 수 있는 대규모 동시 요청(Stampede)을 방지하기 위한 전략을 수립한다.

-   **TTL 만료 시 동시 재생성 방지**: 동일 Key에 대한 동시 프롬프트 생성 요청을 제어해야 한다.
-   **Single-flight 또는 동시성 제어 적용**: 동일 Key에 대한 요청이 몰릴 경우, 하나만 실제 생성을 수행하고 나머지는 결과를 공유받는 패턴(Single-flight 등)을 적용한다.
-   **TTL Jitter 적용**: 모든 Cache가 동시에 만료되지 않도록 TTL에 임의의 시간(Jitter)을 추가하여 만료 시점을 분산시킨다.
-   **보수적 최적화**: 성능 최적화가 시스템 안정성을 해치지 않도록, 동시성 제어 실패 시에는 과감히 캐시를 포기하고 개별 생성하는 Fallback을 허용한다.

### 9.3 Prompt Cache 보안 및 개인정보 보호 원칙

Prompt에는 민감 정보가 포함될 수 있으므로 철저한 보안 원칙을 준수한다.

-   **민감 정보 취급 주의**: Prompt에는 사용자 발화 및 PII가 포함될 수 있음을 인지하고 관리한다.
-   **최소 필요 범위 저장**: 전체 Context를 무조건 저장하는 것이 아니라, 재사용 효용이 높은 최종 Prompt Text만 캐싱한다.
-   **운영 로그 원문 제외**: 어플리케이션 로그에 캐시된 Prompt 원문을 절대 남기지 않는다. 로그에는 식별자, 해시값, 길이, 요약 정보만 기록한다.
-   **최소 권한 원칙**: Redis 접근 권한은 필요한 서비스 계정에만 최소한으로 부여한다.
-   **TTL 기반 자동 소멸**: Prompt Cache는 영구 저장하지 않으며, TTL 만료 시 자동 소멸되도록 설정한다.

### 9.4 메모리 보호 및 최대 크기 정책

Redis 메모리 자원의 안정성을 위해 캐시 크기를 제한한다.

-   **최대 크기 제한**: 캐싱 대상 Prompt의 크기(Byte 또는 Token 수)에 상한을 둔다.
-   **상한 초과 시 캐시 생략**: 설정된 크기를 초과하는 초대형 Prompt는 캐싱하지 않고 매번 생성한다. 이는 Redis 메모리 고갈을 방지하기 위함이다.
-   **기능 실패 아님**: 캐시 미적용은 최적화가 수행되지 않은 것일 뿐, 기능 오류가 아니다.

### 9.5 관측 가능성 (Observability) 및 성공 지표 정의

시스템 운영 상태를 파악하기 위해 다음 지표를 추적 및 관측한다. 단, 이 지표들은 운영 모니터링 용도이며 Evaluation 결과에는 영향을 주지 않는다.

-   **Cache Hit Rate / Miss Rate**: 캐시 효율성 측정.
-   **Prompt Composition Latency (p50 / p95)**: 캐시 적용 전후의 생성 시간 비교.
-   **Redis Error Rate**: Redis 연결 또는 명령 실패 비율.
-   **Redis Fallback Rate**: Redis 오류로 인해 원본 로직으로 Fallback한 비율.
-   **LLM 호출 수 변화 추이**: 캐시 적용으로 인한 LLM 호출 감소량 확인.

### 9.6 롤백 및 비활성화 전략

예상치 못한 문제 발생 시 즉각적인 대응을 위한 전략을 마련한다.

-   **Feature Toggle 기반 비활성화**: 운영 중 설정 변경만으로 Prompt Cache 기능을 즉시 비활성화(OFF)할 수 있어야 한다.
-   **즉시 복귀 (System Fallback)**: 비활성화 시 시스템은 즉시 캐시 없는 기존 로직으로 동작해야 한다.
-   **Cache Flush 절차 정의**: 문제 발생 시 오염된 캐시를 일괄 삭제할 수 있는 운영 절차(Command 등)를 마련한다.
-   **Redis 장애 시 자동 우회**: Redis 연결 장애나 타임아웃 발생 시, 시스템은 자동으로 캐시 계층을 우회(Bypass)하여 서비스 중단을 막아야 한다.
-   **정합성 유지**: 롤백이나 비활성화가 진행되어도 Evaluation 결과의 정합성은 완벽하게 유지되어야 한다.

---

## 10. 보강 섹션: Logical Prompt Version Identifier (Supplementary Section)

본 섹션은 "Cache Key 입력요소 완전성"을 확보하기 위한 필수 요소인 **Logical Prompt Version Identifier**에 대해 정의한다. 이는 Prompt Template의 변경 사항을 추적하기 위한 논리적 장치이다.

### 10.1 Logical Prompt Version Identifier 정의

현재 시스템에는 파일 기반의 Prompt Template 관리 체계가 존재하지 않으나, Prompt 변경 탐지는 Cache 정합성에 필수적이다. 따라서 다음 정의를 따른다.

-   **부재 명시**: 현재 물리적인 Prompt Template Versioning System은 존재하지 않는다.
-   **CP4 필수 요구사항**: 모든 Prompt Composition Logic은 Cache Key 생성 시 **"Logical Prompt Version Identifier"**를 반드시 포함해야 한다.
-   **식별자 성격**:
    -   **Logical Constant**: 코드 상의 Prompt 문자열이나 Template 구조가 변경될 때마다 개발자가 수동으로 증가시키거나 변경해야 하는 논리적 상수(String or Hash)이다.
    -   **Independent Layer**: Session Snapshot Version, Job Policy Version, LLM Model Version과는 별개로 관리되는 독립적인 식별자이다.

### 10.2 목적 명시

이 식별자의 도입 목적은 오직 Cache의 신선도(Freshness) 유지에 있다.

-   **Cache 오염 방지(Anti-Corruption)**: 애플리케이션 배포로 인해 Prompt 로직이 변경되었음에도, 과거 버전의 Prompt로 생성된 캐시(Stale Cache)가 반환되는 것을 방지한다.
-   **재사용 불가 원칙**: Logical Prompt Version이 변경되면, 이전 버전의 식별자로 생성된 모든 Prompt Cache는 즉시 접근 불가능(Key Mismatch) 상태가 되어야 한다.

### 10.3 CP4 범위 한정 선언

본 식별자는 Cache Key 구성을 위한 최소한의 장치이며, 거창한 버전 관리 시스템 도입을 의미하지 않는다.

-   **Scope Limitation**: 이 작업은 Feature로서의 "Prompt Versioning System" 도입이 아니라, **"Cache Key Integrity"**를 위한 내부 식별자 선언이다.
-   **No Authority**: 이 식별자는 평가(Evaluation) 로직이나 점수 산출의 근거(Authority)가 되지 않는다.
-   **PG Authority 생략**: 이 식별자는 Redis Cache Key 생성에만 사용되며, PostgreSQL Schema에 저장되거나 관리될 필요는 없다. (Code Level Constant로 충분함)

### 10.4 승인 게이트 보강

CP4 구현 승인(Implementation Approval) 시 다음 항목을 추가로 검증해야 한다.

-   **[ ] Cache Key Integrity Check**: 구현된 Cache Key 생성 로직에 `LOGICAL_PROMPT_VERSION` 또는 이에 준하는 식별자가 포함되어 있는가?
-   **[ ] Version Bump Policy**: Prompt 코드 수정 시 해당 식별자를 변경해야 함이 주석이나 개발 가이드로 명시되었는가?
