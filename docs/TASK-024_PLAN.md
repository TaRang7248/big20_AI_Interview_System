# TASK-024: 질문은행 구조 정비 (Question Bank Structure) [Plan Only]

본 문서는 `packages/imh_qbank` 패키지의 **역할, 책임, 계약**을 정의하는 문서입니다.  
구현 상세를 배제하고, **Phase 5 계약(Freeze / Snapshot)** 준수와 **Soft Delete 정책에 따른 세션 불변성** 확립을 목적으로 합니다.

---

## 1) 현 상태 근거 확인

### 아키텍처 경계 및 제약 사항
`docs/CURRENT_STATE.md` 및 `00_AGENT_PLAYBOOK.md`에 근거하여, 질문은행이 절대 침범해서는 안 되는 경계는 다음과 같습니다.

*   **Engine vs Question Bank**:
    *   **Engine**(`imh_session`, `imh_job`)은 세션의 상태 전이와 정책 결정권을 독점합니다.
    *   **Question Bank**(`imh_qbank`)는 Engine의 요청에 따라 **질문 후보(Candidates)를 공급하는 수동적 저장소** 역할에 머물러야 합니다.
    *   **근거**: `CURRENT_STATE.md` Section 6 (Service & API Boundary 확정).

*   **Snapshot & Freeze Contract**:
    *   세션이 생성되는 시점에 확정된 질문 목록은 세션 종료 시까지 절대 변하지 않아야 합니다.
    *   질문은행의 원본 데이터가 변경/삭제되더라도, 진행 중인 세션은 **격리된 불변 데이터**를 유지해야 합니다.
    *   **근거**: `CURRENT_STATE.md` Section 3 (Session & Policy Engine Layer).

*   **State Contract**:
    *   세션 상태(`APPLIED` -> `IN_PROGRESS`...)의 전이는 오직 `SessionEngine` 만이 수행할 수 있습니다.
    *   질문은행은 상태 전이 로직에 일절 관여하지 않습니다.

---

## 2) TASK-024 범위 정의

### 책임 (Responsibilities)
`packages/imh_qbank`는 다음을 책임집니다:

*   **질문 자산의 관리 (Mutable/Soft Delete)**: 질문 자산은 수정되거나 **논리적으로 삭제(Soft Delete)** 될 수 있습니다.
*   **후보군 제공 능력**: 태그, 직무, 난이도 등 다양한 조건에 부합하는 **유효한(Active)** 질문 후보군을 제공할 수 있어야 합니다.
*   **출처(Source) 식별성**: 제공하는 질문이 '사전에 정의된 자산(Static)'인지 '실시간 생성된 것(Generated)'인지 구분할 수 있어야 합니다.
*   **Fallback 가용성**: 동적 생성 실패 시 즉시 사용 가능한 대체 질문을 보장해야 합니다.

### 비책임 (Non-Responsibilities)
`packages/imh_qbank`는 다음을 책임지지 않습니다:

*   **세션 데이터 보존**: 이미 진행된 세션의 질문 데이터를 보존하는 책임은 Session Engine/Snapshot에 있으며, QBank는 관여하지 않습니다.
*   **세션 질문 선택**: 후보군 중 어떤 질문을 최종적으로 선택할지는 `JobPolicy`와 `SessionEngine`의 책임입니다.
*   **질문 평가**: 질문에 대한 답변 평가는 `EvaluationEngine`의 책임입니다.
*   **RAG 생성 로직**: 질문을 생성하는 행위 자체는 Provider 또는 RAG 모듈의 책임입니다.

---

## 3) 질문 저장 원칙 및 Source 계층 정의 (필수)

**"Soft Delete Policy vs Session Immutability"** 원칙을 준수하기 위한 계약입니다.

### 3.1 질문 삭제 정책 (Soft Delete Contract)
1.  **논리 삭제 원칙**: 질문은행의 자산 삭제는 **Soft Delete(논리 삭제)** 를 기본 정책으로 합니다. 원본 데이터는 시스템 내에 흔적이 남아야 합니다.
2.  **후보군 제외**: Soft Delete 처리된 질문은 **신규 세션**의 질문 후보군 제공 대상에서 즉시 제외되어야 합니다.
3.  **과거 세션 영향 없음**: Soft Delete 상태 변경은 **과거 세션 기록**에 어떠한 영향도 주지 않아야 합니다. 과거 세션은 질문은행의 삭제 여부와 무관하게 조회 및 재현이 가능해야 합니다.

### 3.2 세션 불변성 계약 (Session Immutability Contract)
1.  **참조 독립성 (Strict Independence)**: 세션에 포함된 질문은 질문은행에 대한 조회나 참조 없이, 그 자체로 **완전한 정보**를 포함해야 합니다. (Self-Contained)
2.  **불변 계약 (Immutable Contract)**: 세션이 시작된 이후, 세션 내의 질문 정보는 질문은행의 원본 수정이나 Soft Delete 여부에 관계없이 **기록 시점의 상태**를 완벽하게 유지해야 합니다.

### 3.3 변경 내성 계약 (Mutability Tolerance Contract)
1.  **Delete-Tolerant**: 질문은행에서 질문이 Soft Delete 되더라도, 해당 질문을 포함한 과거 세션은 **완전한 무결성**을 유지해야 합니다. 세션 데이터는 질문은행의 상태(Active/Deleted)에 의존하지 않습니다.
2.  **Edit-Tolerant**: 질문은행의 내용이 수정되더라도, 수정 전 생성된 세션의 질문 내용은 변경되지 않아야 합니다.

### 3.4 Source 계층 정의
출처 정의는 위 삭제 정책과 불변성 계약을 준수하는 형태로 정의됩니다.

1.  **Static Bank Origin (정적 원천)**:
    *   사전에 검증되고 등록된 질문입니다.
    *   Soft Delete 될 수 있으나, 세션에 기록된 순간부터는 **독립적인 불변 데이터**로 취급됩니다.
    *   세션 내에서는 원본의 Soft Delete 여부와 무관하게 영구적으로 유효한 데이터로 남습니다.

2.  **Generated Origin (생성됨)**:
    *   실시간으로 생성되었거나 외부 요인에 의해 유입된 질문입니다.
    *   생성 근거(Auditability)를 포함하며, 역시 세션 내에서 불변성을 가집니다.

---

## 4) 통합 포인트 정의

Engine/Service 계약을 준수하는 통합 원칙입니다.

### QBank Capability (후보 제공자)
*   **인터페이스 원칙**: "조건을 입력받아 **유효한(Active)** 후보 질문들을 반환한다"는 단일 목적에 집중합니다.
*   **수동적 역할**: QBank는 상위 계층의 요청에 수동적으로 응답하며, 세션의 상태나 정책을 제어하지 않습니다.
*   **검색 필터링**: 삭제된 질문(Soft Deleted)을 필터링하여 제공되지 않도록 보장해야 합니다.

### 경계 준수 통합 (Boundary Respect)
*   **의존성 방향**: `SessionEngine` -> `QBank`. QBank는 세션이나 엔진의 존재를 알지 못합니다.
*   **완전 분리 (Decoupling)**: 세션 스냅샷은 질문은행과 연결 고리(Link)가 끊어진 상태여야 합니다. (질문은행이 사라져도 세션은 남아야 함)

---

## 5) 검증 전략

TASK-024의 완료 여부는 "기존 계약의 보존", "경계 준수", "삭제 정책의 안전성"을 기준으로 검증합니다.

### 1. Phase 5/6 불변성 및 삭제 내성 검증
*   **Soft Delete 검증**: 질문을 Soft Delete 한 후, 신규 세션 후보군에는 나타나지 않지만, 이를 포함한 **과거 세션은 정상 조회**됨을 확인해야 합니다.
*   **Zero Regression**: QBank의 상태 변경이 기존 세션 로직에 영향을 주지 않아야 합니다.

### 2. 아키텍처 경계 검증
*   **우회 경로 차단**: API 계층이나 다른 모듈이 QBank의 내부 상태(Deleted Flag 등)를 직접 조작하지 않음을 확인해야 합니다.
*   **의존성 규칙 준수**: QBank가 Engine 로직에 의존하지 않음을 확인해야 합니다.

### 3. Phase 7(RAG) 확장성 보장
*   **구조적 유연성**: 향후 RAG 모듈이 통합될 때, QBank의 Source 정의가 동적 생성 질문을 수용할 수 있는지 확인합니다.

---

## 6) 리스크 및 의사결정 포인트

### Decision Point A: 데이터 저장소 전략
*   **선택지 A (파일 기반 저장소)**:
    *   *장점*: 버전 관리 용이, 기존 `imh_history`와 일관성 유지.
    *   *단점*: 데이터 증가 및 Soft Delete 필터링 시 I/O 성능/복잡도 고려 필요.
*   **선택지 B (인메모리/코드 기반)**:
    *   *장점*: 빠른 접근 속도.
    *   *단점*: 런타임 상태 관리 복잡성 증가.

### Decision Point B: 식별자(ID) 관리 전략
*   **선택지 A (시스템 생성 ID)**:
    *   *장점*: 전역 고유성 보장.
    *   *단점*: 가독성 부족.
*   **선택지 B (의미론적 ID)**:
    *   *장점*: 식별 용이.
    *   *단점*: 채번 규칙 관리 비용.
