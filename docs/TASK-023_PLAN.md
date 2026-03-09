# TASK-023 Plan: API Layer & Runtime Contract Definition

> **DISCLAIMER**: 본 문서는 구조 제안 문서가 아니며, 기존 Phase 5 계약 위에 API 진입 계층을 안전하게 얹기 위한 **계약 정의 문서**이다.

> **CRITICAL**: This plan strictly enforces the **Job Policy Freeze**, **Snapshot Double Lock**, **State Contract**, and **Service Layer Structure** established in Phase 5. Any deviation from these contracts is strictly prohibited.

---

## 3.1 목표 및 배경 요약 (Goal & Background)

### 3.1.1 목표
Phase 6의 핵심 목표인 **"외부 연동 계층 확장"**의 일환으로, TASK-022에서 구축된 Service Layer를 외부 요(Client)과 연결하는 **API Interface Layer**를 정의하고, 프레임워크 레벨의 **External Runtime Entry Point**의 책임과 경계를 확정한다.

### 3.1.2 배경
- **Service Layer 이후**: TASK-022를 통해 비즈니스 로직(Engine)과 유스케이스(Service)가 격리되었다. 이제 이를 외부 세상(Web/Mobile/3rd Party)에 노출할 **Interface Adapter**가 필요하다.
- **Entry Point 부재**: 현재는 단위 테스트 스크립트로만 실행 가능하다. 실제 서비스로서 동작하기 위한 **Application Bootstrap** 및 **Gateway**가 정의되어야 한다.

---

## 3.2 범위 정의 (Scope)

### 3.2.1 In Scope (포함)
1.  **API Layer Definition**:
    - **Session Interface**: 면접 진행 관련 진입점 (생성, 조회, 답변 제출).
    - **Admin Interface**: 관리자 조회 및 통계 진입점 (TASK-020/022 연동).
    - **Exception Mapping Contract**: Service/Domain Exception을 표준 프로토콜 상태(HTTP Status 등)로 변환하는 규칙 정의.
    - **DTO Mapping Contract**: Service DTO를 외부 응답 규격으로 변환하는 규칙 정의.
2.  **External Runtime Entry Point Contract**:
    - **Application Bootstrap Module**의 역할 정의.
    - **Dependency Composition Root**의 책임 정의.
3.  **API Data Contract**:
    - Request/Response Schema 명세 요구사항 정의.

### 3.2.2 Out of Scope (비포함)
- **Domain/Service Layer 변경**: 기존 Engine, Service, Policy, State 로직 수정 절대 금지.
- **Authentication/Authorization Details**: 구체 인증 메커니즘 구현 제외.
- **Frontend UI**: 화면 구현 없음.
- **Database Schema Changes**: 저장소 구조 변경 없음.
- **Orchestration Logic**: API Layer 내에서의 로직 조합 금지.

---

## 3.3 고정 계약 및 API Layer 금지 사항 (Contracts & Prohibitions)

본 프로젝트의 안정성을 위해 다음 계약사항은 **절대 변경 불가**하며, API Layer는 이를 엄격히 준수해야 한다.

### 3.3.1 Phase 5 고정 계약
- [ ] **Freeze at Publish**: 공고 게시(Publish) 시점의 Policy Snapshot은 세션 생성 시 불변으로 주입된다.
- [ ] **Snapshot Double Lock**: `JobPolicy`와 `SessionConfig` 스냅샷은 생성 후 절대 수정되지 않는다.
- [ ] **State Transition Contract**: `APPLIED` → `IN_PROGRESS` → `COMPLETED` / `INTERRUPTED` → `EVALUATED` 흐름은 오직 Engine에 의해서만 통제된다.
- [ ] **Admin Query Bypass**: 관리자 조회는 Command Service를 거치지 않고 Read-only 경로를 따른다.
- [ ] **Fail-Fast Concurrency**: 동시 요청 시 대기(Wait)하지 않고 즉시 반려(Fail-Fast)한다.

### 3.3.2 API Layer 금지 사항 (Strict Prohibitions)
- [ ] **No Interpretation**: API Layer는 Freeze/Snapshot/State Contract를 생성·변경·해석하지 않는다.
- [ ] **No State Logic**: API Layer는 상태 전이 판단(Next Step 결정 등)을 직접 수행하지 않는다.
- [ ] **No Direct Access**: API Layer는 Engine 또는 Repository를 직접 호출하거나 Import 하지 않는다.
- [ ] **No Lock Definition**: API Layer는 Lock 정책이나 메커니즘을 정의하지 않는다 (Service Layer 위임).

---

## 3.4 외부 런타임 진입점 정의 (External Runtime Entry Point)

**"런타임 프로세스 시작"**은 다음의 추상화된 단계를 의미한다.

1.  **Application Bootstrap**:
    - 런타임 환경 설정 로드 및 프로세스 초기화.
    - 실행 환경(Environment) 검증.
2.  **Dependency Composition Root**:
    - Persistence, Provider 등 인프라스트럭처 인스턴스 생성.
    - Service Layer 인스턴스 생성 및 의존성 주입(DI).
    - 싱글톤 객체(Concurrency Manager 등) 초기화.
3.  **Router Registration**:
    - 외부 요청을 처리할 핸들러(Router) 등록.
    - Exception Mapping 및 Middleware 등록.
4.  **Runtime Exposure**:
    - **ASGI 호환 런타임**을 통해 애플리케이션을 외부에 노출한다.

**경계 정의**:
- 외부 호출은 오직 **Router Module**에 정의된 규약을 통해서만 시스템에 진입한다.
- **Integration Verification Script**를 제외한 어떤 경로도 Service/Engine 내부로 직접 진입할 수 없다.

---

## 3.5 API Layer 책임 정의 (Contract)

API Layer는 **철저한 진입 어댑터(Entry Adapter)**로서 동작하며, 다음 원칙을 준수한다.

1.  **Pure Adapter Role**:
    - 모든 비즈니스 판단(유효성 검사 포함)은 Service Layer에 위임한다.
    - API는 오직 **Protocol Parsing** → **Service Call** → **Protocol Response Mapping** 만 수행한다.
2.  **Isolation from Domain**:
    - Service Layer가 반환한 Domain Entity를 그대로 외부로 노출하지 않으며, 정의된 Response Schema로 변환한다.
3.  **Statelessness**:
    - API 인스턴스는 상태를 가지지 않으며, 모든 상태 관리는 Service Layer를 통해 Persistence/Engine에 위임한다.

---

## 3.6 산출물 유형 정의 (Deliverables Types)

구체적인 파일 경로는 Execution 단계에서 확정하며, 본 Plan에서는 산출물의 유형만 정의한다.

1.  **Application Bootstrap Module**:
    - 애플리케이션 초기화 및 실행 진입점 코드.
2.  **Dependency Composition Root**:
    - DI 컨테이너 구성 및 의존성 주입 코드.
3.  **API Router Modules**:
    - Session 및 Admin 기능을 노출하는 라우팅 처리 코드.
4.  **Integration Verification Artifacts**:
    - 외부 요청 시뮬레이션을 통해 전체 통합 흐름을 검증하는 스크립트 및 결과물.

---

## 3.7 검증 전략: 실패 조건 (Failure Conditions)

검증은 "무엇이 성공인가"보다 **"무엇이 발생하면 실패인가"**를 기준으로 수행한다.

1.  **Policy Integrity Failure**:
    - Freeze된 Policy 값이 세션 진행 중 변경되면 실패.
    - Snapshot 내용이 재생성되거나 재정의되면 실패.
2.  **State Contract Failure**:
    - 허용되지 않은 State Transition이 발생하면 실패. (예: `APPLIED` 없이 `IN_PROGRESS` 진입 시도)
    - Engine을 거치지 않고 상태가 변경되면 실패.
3.  **Concurrency Policy Failure**:
    - Lock된 자원에 대해 대기(Wait)하거나 덮어쓰기가 발생하면 실패. (즉시 Fail-Fast가 아니면 실패)
4.  **Architecture Violation Failure**:
    - Admin Query가 Command Service 경로를 호출하면 실패.
    - API Layer에서 Repository 접근 로그가 발견되면 실패.
5.  **Integration Failure**:
    - 정의된 Request/Response Schema와 실제 응답이 불일치하면 실패.

---

## 3.8 리스크 및 해결 (Risks & Mitigation)

1.  **Service Layer 우회 위험**:
    - **Risk**: 개발 편의를 위해 API에서 Repo/Engine 직접 호출.
    - **Mitigation**: Composition Root에서 API Layer에는 Service 객체만 주입되도록 강제 구조화.
2.  **RAG/질문은행 경계 모호성**:
    - **Risk**: API가 질문의 출처(Source)를 알거나 제어하려 함.
    - **Mitigation**: API Request Contract에 질문 출처 관련 파라미터를 원천 배제. (Service/Engine 내부 결정 사안)
