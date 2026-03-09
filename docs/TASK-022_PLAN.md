# TASK-022: 외부 진입점(API) 및 서비스 계층 통합 설계 (Plan)

이 문서는 **Phase 6: External Integration & Service Layer (서비스 통합)** 단계의 시작점으로서, Phase 5에서 확정된 핵심 엔진과 계약들을 외부 세계(Client/FE)와 안전하게 연결하기 위한 아키텍처 설계 문서이다.

> **Constraint Check**: 본 계획은 Phase 5의 [Job Policy Freeze], [Snapshot Double Lock], [State Contract]를 절대적으로 준수하며, 기존 Session Engine의 내부 로직을 변경하지 않는다.

---

## 1. 목적 및 범위 (Purpose & Scope)

### 1.1 목적
- **캡슐화 및 보호**: 핵심 비즈니스 로직(Session Engine/Policy)을 외부의 직접적인 접근으로부터 보호하는 **방어벽(Service Layer)**을 구축한다.
- **진입점 통일**: 클라이언트의 모든 요청을 일관된 방식(API Contract)으로 접수하고, 적절한 내부 엔진으로 라우팅하는 **단일 진입점**을 정의한다.
- **관심사 분리**: "HTTP 요청 처리(API)"와 "유스케이스 실행(Service)"과 "도메인 상태 변경(Engine)"의 책임을 명확히 분리한다.

### 1.2 범위 (In-Scope)
- **Layered Architecture 정의**: API Controller Layer ↔ Service Layer ↔ Domain(Engine) Layer 간의 의존성 방향 및 호출 규약.
- **Service Layer 역할 정의**: 트랜잭션 단위 설정, 세션 로딩, 도메인 메서드 호출 책임.
- **API Spec 전략**: 외부(Front-end)에 노출할 데이터 포맷(DTO) 변환 전략.
- **RAG/질문은행 경계 설정**: 실행 시점의 질문 출처(Source)에 대한 은닉화 전략.

### 1.3 비범위 (Out-of-Scope)
- 실제 API Endpoint 구현 코드 (FastAPI 데코레이터 등 상세 구현).
- 인증(Authentication) / 인가(Authorization)의 구체적 구현 로직.
- 프론트엔드 화면 설계.
- 기존 Phase 5 산출물(Job Policy, Session Engine, Evaluation Engine)의 내부 수정.

---

## 2. 아키텍처 계층 구조 (Layered Architecture)

외부 요청은 반드시 아래의 계층 순서를 통과해야 하며, 역방향 호출이나 계층 건너뛰기(Bypass)는 금지된다.

```mermaid
graph LR
    Client[Client / FE] --> API[API Layer<br>(Controller)]
    API --> Service[Service Layer<br>(Usecase)]
    Service --> Engine[Domain Layer<br>(Session Engine)]
    Service --> Repo[Persistence Layer<br>(Repository)]
    
    Engine -.-> Snapshot[Immutable Snapshot]
    Engine -.-> Policy[Job Policy]
```

### 2.1 API Layer (Interface Adapter)
- **책임**: 외부 세계와의 통신 규약(HTTP) 처리.
- **역할**:
  - 요청 유효성 검증 (Input Validation).
  - 인증 토큰 파싱 및 사용자 식별.
  - **Service Layer 호출**.
  - 도메인/서비스 결과를 HTTP Response(DTO)로 변환. 이때 DTO는 도메인 엔티티와 완전히 분리된 **독립 클래스**로 정의하며, 반드시 **명시적 매퍼(Mapper)**를 통해서만 변환한다.
- **제약**: 비즈니스 로직을 포함하지 않는다. `Session` 객체를 직접 조작하지 않는다. 단, Admin 조회 등 상태 변경이 없는 순수 조회(Query)는 Service Layer를 거치지 않고 Read-Only Repository에 직접 접근할 수 있다.

### 2.2 Service Layer (Application Business Rules)
- **책임**: 애플리케이션의 유스케이스(Use Case) 실행 및 흐름 제어.
- **역할**:
  - **Session Loading**: Repository를 통해 적절한 `Session` 객체를 복원.
  - **Concurrency Control**: 동시성 제어 (Redis 도입 전까지는 session_id 단위 **File/Memory Lock** 적용. 락 획득 실패 시 대기 없이 **즉시 에러(Fail-Fast)**를 반환하여 순차성을 보장).
  - **Engine Delegation**: 복원된 Session의 메서드(`submit_answer`, `start_session`) 호출.
  - **Event Publishing**: 상태 변경 후 후속 작업(평가 트리거 등)을 위한 이벤트 발행(옵션). (단, Phase 6에서는 외부 MQ 없이 **프로세스 내 동기 호출(In-Process)**로 한정한다)
- **제약**: 도메인 상태를 직접 변경(`session.state = 'DONE'`)하지 않고, **반드시 엔진의 메서드를 통해서만** 상태를 변경한다.

### 2.3 Domain Layer (Session Engine - Existing)
- **책임**: 핵심 비즈니스 규칙 및 상태 전이 보장 (Phase 5 Contract).
- **역할**:
  - `Job Policy Snapshot` 참조.
  - 상태 전이 무결성 검사.
  - Double Lock 정책 준수.

---

## 3. 핵심 통합 시나리오 (Key Integration Flows)

### 3.1 면접 세션 생성 (Start Interview)
1. **API**: `POST /api/sessions` 요청 수신 (Job ID 포함).
2. **Service**:
   - `JobPostingRepository`에서 **Published Job Policy** 조회.
   - (검증) 해당 Job이 유효하고, 유저가 지원 가능한지 확인.
   - **Engine 호출**: `SessionEngine.create_session(job_policy)`
   - 생성된 세션을 Repository에 저장.
3. **Engine**: Snapshot 생성 및 초기 상태(`APPLIED`) 설정. (Phase 5 준수)
4. **API**: 생성된 `session_id` 반환.

### 3.2 답변 제출 및 진행 (Submit Answer)
1. **API**: `POST /api/sessions/{id}/answers` 요청 수신 (Audio/Video/Text). (API Layer는 **물리적 파일 업로드 및 포맷 검증**을 전담한다)
2. **Service**:
   - `SessionRepository`에서 `session_id`로 세션 로드.
   - (검증) 요청자 == 세션 소유자 확인.
   - **Engine 호출**: `session.submit_answer(input_data)` (※ 파일 데이터 자체가 아닌 **참조 경로(Path)와 메타데이터**만 전달)
   - 변경된 세션 상태 저장.
3. **Engine**:
   - 현재 상태가 `IN_PROGRESS`인지 확인.
   - 답변 기록 및 **Next Step** 결정.
4. **API**: 다음 질문 정보(Next Question DTO) 또는 종료 플래그 반환.

---

## 4. 질문은행 및 RAG 통합 경계 (Content Boundary)

질문 생성의 원천(Source)이 고정형 질문은행인지, 실시간 RAG인지는 **API와 Service Layer에게 투명(Transparent)해야 한다.**

### 4.1 은닉화 전략 (Hiding Strategy)
- **Service Layer의 관점**: Service Layer는 오직 `session.get_current_question()`만을 호출한다.
- **Engine의 관점**: Engine은 초기화 시점에 확정된 **Snapshot(Question List or Generator Config)**을 참조한다.
- **RAG의 위치**: RAG 로직이나 질문은행 검색 로직은 Engine 내부(또는 Engine이 참조하는 Provider)에 위치하며, Service Layer는 이를 알 필요가 없다.

### 4.2 Snapshot 불변성 유지
- RAG를 사용하더라도, 어떤 질문이 생성되었는지는 **즉시 Session History에 기록**되며, 한 번 사용자에게 제시된 질문은 수정될 수 없다.
- 이는 Phase 5의 **Auditability(감사 가능성)** 원칙을 준수하기 위함이다.

---

## 5. 기존 계약 준수 확인 (Compliance Check)

| Phase 5 계약 | TASK-022 Plan 준수 방안 |
| :--- | :--- |
| **Job Policy Freeze** | Service Layer는 세션 생성 시점의 **Published Policy**만을 참조하며, 임의의 파라미터 주입을 금지함. |
| **Snapshot Double Lock** | API/Service는 이미 생성된 Snapshot 내부를 수정할 인터페이스를 제공하지 않음. 오직 `Session`의 메서드를 통해 상태 전이만 유발함. |
| **State Contract** | Service Layer는 Engine이 정의한 State Enum(`IN_PROGRESS`, `COMPLETED` 등)을 그대로 DTO에 매핑하여 반환함. 임의의 상태 조작 불가. |
| **Admin Query Isolation** | Admin API는 Service Layer를 거치지 않고, 별도의 [Query Service]를 통해 Read-Only Repository에 접근하도록 설계함 (Phase 6 후반부). |
| **Practice/Real Mode** | 모드 구분은 Session 객체 내부 속성으로 관리되며, Service Layer는 동일한 `submit_answer` 로직을 타지만 Engine 내부에서 폴리머피즘으로 동작 분기됨. |

---

## 6. 문서화 및 후속 작업 계획

### 6.1 docs 폴더 업데이트 대상
- `TASK-022_PLAN.md` (본 문서 생성)
- `TASK_QUEUE.md` (TASK-022 정의 업데이트 및 TASK-023 이후 일정 조정)
- `CURRENT_STATE.md` (Phase 6 진입 선언)

### 6.2 승인 및 진입 조건 (Exit Criteria)
본 Plan은 다음 조건 충족 시 승인된 것으로 간주하고 구현(Execution) 단계로 넘어간다.
1. 관리자(User)가 본 External Integration 설계에 동의.
2. 기존 엔진 코드 수정 없이 API/Service 구현이 가능함이 확인됨.
3. 질문은행/RAG가 Service Layer에 노출되지 않는 구조임이 확인됨.
