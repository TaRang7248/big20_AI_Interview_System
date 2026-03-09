# TASK-025: RAG Fallback Engine 통합 (Plan Only)

본 문서는 **TASK-025 "RAG Fallback Engine 통합"**을 위한 설계 및 검토 항목을 정의합니다.  
현재 단계는 **Plan Only**이며, 실제 구현(코드 작성)은 포함되지 않습니다.  
모든 설계는 `IMH/IMH_Interview/docs/` 기반의 기존 계약(Phase 5~6)을 절대적으로 준수합니다.

---

## 1. TASK-025 Plan Outline

### 1.1 목적 (Purpose)
- **RAG Fallback**: LLM 기반 질문 생성 실패, 품질 저하, 또는 응답 지연 시 즉시 **질문은행(Static QBank)**의 검증된 질문을 대체(Fallback)로 사용하여 면접 흐름의 끊김을 방지합니다.
- **Phase 7 목표**: Session Engine의 안정성을 유지하면서 동적 질문 생성 능력을 통합합니다.

### 1.2 기존 계약 및 제약 요약 (Constraints)
- **변경 금지 (Immutable Context)**:
  - **Phase 5**: Session State Contract (상태 전이 흐름), Snapshot Double Lock (세션 불변성), Job Policy Freeze.
  - **Phase 6**: Service Layer (Command/Query 분리), Fail-Fast Policy (동시성 제어), API Boundary.
- **Engine 경계**: Session Engine은 정책 결정의 주체이며, RAG/QBank는 수동적 공급자(Provider) 역할만 수행합니다.

### 1.3 범위 (Scope)
- **In-Scope**:
  - RAG Fallback Trigger 정책 정의 (언제 Fallback 할 것인가)
  - `Generated Origin` 질문의 Session Snapshot 통합 구조 명세
  - Static QBank와의 Fallback 연결 인터페이스 설계
- **Out-of-Scope**:
  - PGVector 등 물리적 벡터 DB 도입 (추후 Phase 8)
  - 고도화된 프롬프트 엔지니어링 (기능 동작 중심)
  - TTS/STT 등 멀티모달 통합 (기능 우선순위 상 후순위)
  - **Static QBank로의 승격(Promotion)**: Generated 질문은 이번 단계에서 영구 자산화하지 않음.

### 1.4 용어 정의
- **Source**: 질문의 출처 (STATIC_BANK vs GENERATED).
- **Generated Origin**: LLM/RAG를 통해 실시간 생성된 질문. Snapshot 저장 시 Value Object로 고정되어야 함.
- **Fallback**: 생성 실패 시 Static Source로 전환하는 행위.

### 1.5 Architecture Decisions (Immutable Rules) [보강]
**이 섹션의 내용은 구현 단계에서 절대 변경할 수 없는 불변 규칙입니다.**

1.  **Fallback 결정권 (Decision Authority)**
    - Fallback 발생 여부 및 경로 선택의 최종 결정권은 **Session Engine 정책 흐름**에 있다.
    - Provider/RAG 계층은 결과(success/failure/context)만 반환하며, **정책 판단을 수행하지 않는다**.
    - Fallback은 상태 전이(State Contract)를 유발하지 않는다.
    - 동일 상태에서 **질문 공급(Source)**만 달라질 수 있다.

2.  **Freeze 계약 보호 (Freeze Protection)**
    - **Publish 이후 Job Policy Freeze는 변경 불가 기준선이다.**
    - RAG Fallback 또는 Generated Origin은 평가 스키마를 변경하지 않는다.
    - Generated 질문은 Freeze된 평가 규칙을 소비할 뿐, 수정하지 않는다.

---

## 2. 통합 설계 체크리스트 (Design Checklist)

### 2.1 Engine 흐름 불변 조건
- [ ] **상태 전이 영향 없음**: 질문을 가져오는 과정(RAG vs Static)이 Session State(`IN_PROGRESS`) 전이 로직에 영향을 주어선 안 된다.
- [ ] **Fail-Fast 준수**: RAG Latency가 길어질 경우, 전체 트랜잭션을 잡고 있지 않고 적절한 Timeout 내에 Fallback 하여 Fail-Fast 원칙을 지키는가?
- [ ] **Command 단일 경로**: 질문 생성 요청 또한 `SessionService` -> `Engine` command 경로를 따른다.

### 2.2 Snapshot/Freeze 침범 금지 조건
- [ ] **Self-Contained Snapshot (Value Object)**: `Generated Origin` 질문이 세션에 추가될 때, 외부(LLM/VectorDB)에 대한 링크가 아닌 **질문 내용 전체(Value)**가 스냅샷에 저장되는가?
- [ ] **재현성 보장 (Minimal Repr)**: 생성 당시의 Context 해시 등 최소한의 근거가 포함되어, 나중에 생성 근거를 추적할 수 있는가?

### 2.3 Question Bank 정합성 조건
- [ ] **Soft Delete 필터링**: Fallback 대상이 되는 Static 질문이 현재 `Soft Deleted` 상태라면 후보군에서 제외되는가?
- [ ] **Source 식별**: 세션 객체 내에서 해당 질문이 `Static`인지 `Generated`인지 명확히 구분되는가?
- [ ] **Local Asset Only**: Generated Origin은 **Session-local 자산**이며, Static Question Bank에 승격(promote)되지 않음을 보장하는가?

---

## 3. RAG Fallback 의사결정 포인트 (Decision Points)

### 3.1 Fallback 트리거 조건
- **Explicit Failure**: LLM Provider가 에러(5xx, Connection Refused)를 반환할 때.
- **Latency Timeout**: 설정된 시간(예: 3초) 내에 생성이 완료되지 않을 때.
- **Validation Failure**: 생성된 질문이 JSON Schema(필수 필드 누락 등)를 위반할 때.
- **Policy Blocking**: 생성된 내용이 금칙어/안전 정책(Safety Guardrail)에 걸렸을 때.

### 3.2 성공/실패 정의 및 관측
- **성공(Normal)**: 유효한 `Generated Question` 객체 반환. 로그 레벨 `INFO`.
- **실패(Fallback)**: 위 트리거 조건 발생 -> `Static Question` 반환. 로그 레벨 `WARN` (운영 모니터링 대상).
- **치명적 실패(Critical)**: Fallback 조차 실패(Static 질문 고갈 등). 로그 레벨 `ERROR`.
  - **최종 Fallback**: 예측 가능하고 Snapshot 독립적인 **"안전 질문 세트(Safe Fallback Set)"**를 정의하여 반환해야 한다. (세션 중단 방지 최후의 보루)

### 3.3 Engine vs Service 경계 (Immutable Rule)
- **단일 판단 주체**: Fallback 여부 및 경로 선택의 **단일 판단 주체는 Session Engine**이다.
- **Provider 역할 제한**: Provider는 생성 결과(success/failure/context)만 반환하며, 어떠한 정책 판단도 수행하지 않는다.
- **Service 역할 제한**: Service Layer는 오케스트레이션만 담당하며, Fallback 정책 판단을 수행하지 않는다.
- **Engine 권한**: 오직 Engine만이 질문 공급 전략(RAG 또는 Static)을 선택할 수 있다.
- **상태 보존**: Fallback은 상태 전이를 유발하지 않는다. 동일 상태(`IN_PROGRESS`)에서 질문 Source(`GENERATED` -> `STATIC`)만 변경된다.

---

## 4. Generated Origin 확장 전략

### 4.1 확장 단계
- **Level 1 (Current)**: 세션 스냅샷 내에만 존재하는 **Session-local** 자산.
- **Promotion Ban**: TASK-025 범위에서 Generated 질문은 **Static QBank로 승격(Promote)하지 않는다**.
- **Soft Delete Compliance**: Generated Origin은 Question Bank의 Soft Delete 정책에 영향을 주거나 받지 않는다.

### 4.2 필수 메타데이터 요구사항 (Snapshot 오염 방지) [보강]

**Snapshot에 포함될 수 있는 허용 항목 (Allowed Metadata):**
- `origin_type`: "GENERATED"
- `model_identifier`: 모델명 (예: gpt-4o)
- `policy_version`: 참조한 정책 버전
- `generation_timestamp`: 생성 시각
- `reference_resource_hash` or `id`: 참조 문서의 해시 또는 ID (Minimal Reference)
- `deterministic_hash`: 재현성을 위한 시드 또는 해시

**Snapshot에 포함되어선 안 되는 금지 항목 (Forbidden):**
- 원문 RAG 컨텍스트 전체 텍스트 덤프 (용량 및 보안 이슈 방지)
- 외부 링크 의존 텍스트 (시간 경과에 따른 Link Rot 방지)
- 세션 외부에서 시간 경과에 따라 변경 가능한 데이터 (Mutable External State)

### 4.3 세션 스냅샷과의 관계 (불변성)
- Generated 질문은 생성 직후 세션에 편입되며, 이후 **수정/삭제가 불가능한 Value Object**로 취급된다.
- QBank에 별도 저장되지 않더라도 세션 데이터만으로 온전히 조회 가능해야 한다.

---

## 5. 검증전략 (Verify Strategy)

`scripts/verify_task_025.py`에 포함될 시나리오 목록:

1.  **[Scenario: Normal Generation]**: Mock LLM이 정상 응답을 줄 때, 세션에 `Generated` 타입 질문이 저장되는지 검증.
2.  **[Scenario: Explicit Fallback]**: Mock LLM이 에러를 던질 때, `Static` 타입 질문(Fallback)이 저장되는지 검증.
3.  **[Scenario: Schema/Safety Violation Fallback]**: LLM이 잘못된 JSON을 주거나 금칙어를 포함할 때, Fallback이 작동하는지 검증.
4.  **[Scenario: Latency Fallback]**: LLM 응답이 Timeout을 초과할 때, Fallback이 작동하는지 검증.
5.  **[Scenario: Critical Failure Safety]**: Static 질문마저 고갈되었을 때, "Safe Fallback Set"이 반환되는지 검증.
6.  **[Scenario: Snapshot Independence]**: 세션 저장 후, Mock Provider 설정을 바꿔도 이미 저장된 세션의 질문(Generated)이 변하지 않는지 검증.

---

## 6. 리스크 및 가드레일 (Risks & Guardrails) [보강]

- **Risk**: RAG 과정에서 외부 I/O(Vector Search)로 인해 전체 API 응답 속도가 느려짐.
  - **Guardrail**: **Strict Timeout** 설정 필수. (Fail-Fast).
  - **Guardrail**: 백그라운드 생성(Async Prefetch) 고려 (단, 이번 단계에선 복잡도상 제외 가능. 동기 타임아웃으로 제어).

- **Risk**: 생성된 질문의 퀄리티 저하(Hallucination).
  - **Guardrail**: **Rubric Validator**.
    - Validator는 **형식/스키마/안전성** 검증만 수행한다.
    - **평가/채점 기능이 아니다**.
    - 평가 정책, 점수 산정 로직, Freeze 계약을 변경하지 않는다.

- **Risk**: 스냅샷 용량 증가.
  - **Guardrail**: Generated 질문의 메타데이터는 최소한으로 유지(Context 전체 덤프 금지, 해시/ID 위주).
