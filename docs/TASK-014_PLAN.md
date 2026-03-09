# TASK-014: 리포트 조회 API 노출 – Report API Contract (Plan Only)

## 1. 개요 및 목적 (Objective)
- **목적**: 기 생성된 면접 리포트 및 이력 데이터를 외부(Client)에서 조회할 수 있도록 **인터페이스 계약(Contract)**을 수립한다.
- **핵심 과제**: 내부 저장 구조(Persistence Layer)와 외부 노출 구조(Presentation Layer) 간의 **책임 경계**를 명확히 하고, **조회 정책**을 결정한다.

## 2. 결정 필요 항목 (Decision Points)
승인을 위해 다음 항목들에 대한 의사결정을 요청합니다.

### 2.1 책임 경계 (Responsibility Boundary)
- **API Layer (Presentation)**:
  - 역할: HTTP 요청 수신, 입력값 검증, 응답 포맷팅, 표준 에러 매핑.
  - **제약**: 비즈니스 로직(점수 계산, 데이터 가공 등)을 **절대 포함하지 않는다**.
- **Persistence Layer (Repository)**:
  - 역할: 실제 데이터(JSON 파일) 조회, 물리적 IO 처리.
- **결정 사항**: API는 오직 데이터를 전달하는 **Pass-through** 역할만 수행하며, 데이터의 해석이나 가공은 하지 않는다.

### 2.2 리소스 식별 전략 (Resource Identification)
- **식별자 (Identifier)**:
  - 각 면접 리포트는 고유한 **UUID (interview_id)**로 식별한다.
- **URI 설계 원칙**:
  - 리소스 중심의 RESTful 경로를 채택한다. (예: `/reports/{interview_id}`)
- **결정 사항**: 저장소 내부적으로 사용되는 Timestamp나 파일 경로는 외부로 노출하지 않으며, 오직 UUID만을 공개 식별자로 사용한다.

### 2.3 데이터 노출 정책 (Data Exposure Policy)
- **목록 조회 (List View)**:
  - **경량화(Lightweight) 원칙**: 목록 조회 시에는 파일 전체를 읽지 않거나, 읽더라도 **요약 정보(Summary)**만 추출하여 반환한다.
  - **포함 항목**: 식별자, 면접 일시, 종합 점수, 등급, 주요 키워드(Tags).
  - **제외 항목**: 상세 피드백 텍스트, 차트용 데이터, 문항별 분석 결과.
- **상세 조회 (Detail View)**:
  - **완전성(Completeness) 원칙**: 특정 리포트 요청 시에는 **모든 정보**를 포함한 전체 JSON 구조를 반환한다.

### 2.4 쿼리 능력 범위 (Query Capability)
- **지원 기능**:
  - **정렬(Sorting)**: 최신순(내림차순) 정렬을 기본으로 제공한다.
  - **페이징(Pagination)**: 대량의 파일 조회를 대비해, Limit/Offset 기반의 슬라이싱을 지원한다.
- **미지원 기능 (Out of Scope)**:
  - **복합 검색**: 키워드 검색, 점수 구간 필터링 등 인덱싱이 필요한 검색 기능은 파일 시스템 기반에서는 제외한다.

## 3. 범위 정의 (Scope Definition)

### 3.1 In-Scope (수행할 것)
- **API Endpoint 정의**: 리소스 경로 및 허용 메서드(HTTP Method) 정의.
- **Data Contract 정의**: Client에게 전달될 JSON 응답 스키마(Schema) 설계.
- **Error Handling 표준**: 404(Not Found), 500(System Error) 등 상황별 HTTP 상태 코드 정의.

### 3.2 Out-of-Scope (수행하지 않을 것)
- **인증 및 인가 (Authentication)**: 사용자 식별(`user_id`)은 파라미터로 처리하거나 단일 사용자로 가정하며, 보안 로직(JWT, Session)은 구현하지 않는다.
- **리포트 생성 및 수정**: 본 TASK는 **Read-Only**이며, 리포트를 생성하거나 수정하는 기능은 포함하지 않는다.
- **데이터베이스 도입**: 별도의 검색 엔진이나 RDBMS 도입 없이, 파일 시스템을 데이터 소스로 유지한다.

## 4. API Contract 원칙 (Principles)
- **Stateless**: API 요청 간 상태를 공유하지 않는다.
- **Idempotent**: 조회(GET) 요청은 서버 상태를 변경하지 않으며, 여러 번 호출해도 동일한 결과를 보장한다.
- **Abstraction**: 클라이언트는 서버가 파일을 사용하는지 DB를 사용하는지 알 필요가 없도록, 내부 구현 상세를 API 응답에 노출하지 않는다.

## 5. 승인 후 구현 계획 (Next Steps)
본 Plan이 승인되면, 구현 단계에서 다음 작업을 수행합니다.

1. **Router 구현**: 정의된 URI 경로에 대한 핸들러 함수 작성.
2. **DTO 매핑**: Repository에서 반환된 엔티티를 API 응답용 DTO로 변환하는 로직 구현.
3. **Repository 연동**: `imh_history` 패키지의 기능을 주입(Dependency Injection)받아 연결.
