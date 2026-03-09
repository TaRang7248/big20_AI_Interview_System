# TASK-015: Report Consumption Standard Definition Plan

## 1. 개요 (Overview)
본 문서는 **TASK-015: 리포트 소비 규격 정의**를 수행하기 위한 계획서입니다.
이미 구현된 리포트 조회 API(TASK-014)의 결과를 UI 및 외부 Client가 올바르게 해석하고 소비하기 위한 **규격(Contract)**을 정의하는 것을 목표로 합니다.
본 단계에서는 실제 코드를 작성하거나 스키마를 변경하지 않으며, 오직 **소비 규격 문서**에 포함될 내용과 정의 방향성을 수립합니다.

---

## 2. 리포트 소비 주체 식별 계획 (Consumer Identification)
규격 정의 시, 데이터를 소비하는 주체별로 필요한 정보의 깊이와 형태를 구분하여 정의할 계획입니다.

### 2.1 Candidate UI (지원자용)
- **주요 정의 대상**:
    - 기술 점수, 태도 점수 등 **요약된 결과 지표**.
    - 합격/불합격 여부 또는 등급.
    - 개선을 위한 **High-level 피드백**.
- **설계 관점**:
    - 복잡한 원시 데이터(Raw Data) 노출 최소화.
    - 긍정/부정 피드백의 직관적 전달 방식.

### 2.2 Recruiter/Admin UI (채용담당자용)
- **주요 정의 대상**:
    - 전체 면접 타임라인 및 구간별 상세 데이터.
    - 평가 근거(Evidence)로 활용될 **Raw Data 연결**.
    - 다른 지원자 또는 이전 면접과의 비교 지표.
- **설계 관점**:
    - 드릴다운(Drill-down) 가능한 상세 데이터 구조.
    - 정량적 수치와 정성적 분석의 매핑 로직.

### 2.3 외부 Client (API Consumer)
- **주요 정의 대상**:
    - 시스템 연동을 위한 **표준화된 데이터 포맷**.
    - 기계 가독성(Machine Readability)을 보장하는 구조.

---

## 3. 리포트 데이터 소비 목적 구분 계획 (Consumption Purpose)
데이터의 용도에 따라 UI가 어떻게 렌더링해야 하는지에 대한 가이드를 수립합니다.

### 3.1 요약 및 결과 표시 (Summary View)
- 전체 종합 점수(Overall Score) 산출 및 표시 기준.
- "한 눈에 보기"를 위한 핵심 KPI(Key Performance Indicator) 선정.

### 3.2 상세 분석 열람 (Detail Analysis)
- 문항별(Question-wise) 분석 데이터 표시 규격.
- 오디오/비디오/텍스트 멀티모달 데이터의 **Timeline Sync** 규격.

### 3.3 비교 및 히스토리 (History & Comparison)
- 동일 지원자의 과거 면접 기록과 비교(Trend Analysis).
- 지원자 간 점수 분포 비교(Relative Analysis).

---

## 4. UI / Client Contract 범주 정의 계획 (Contract Categories)
Client가 데이터를 안전하고 일관되게 처리하기 위한 기술적 규약을 수립합니다.

### 4.1 필드 필수/선택 여부 (Mandatory vs Optional)
- **Mandatory**: 모든 리포트에 반드시 존재하는 필드 (예: 종합 점수, 면접 ID).
- **Optional**: 분석 실패, 데이터 부족 등으로 없을 수 있는 필드 (예: 특정 구간의 감정 데이터).
- **Null Safety**: UI에서 Null 처리 또는 기본값(Default Value) 처리가 필요한 영역 식별.

### 4.2 데이터 소비 방식 구분
- **정량 점수 (Quantitative)**: 점수 스케일(0~100, 1~5 등) 및 백분위 해석 가이드.
- **정성 피드백 (Qualitative)**: 텍스트 톤앤매너, 하이라이팅, 줄바꿈 등 텍스트 렌더링 규칙.
- **근거 데이터 (Evidence)**: 원본 미디어의 특정 timestamp와 분석 결과의 매핑 규격.

### 4.3 시간 흐름 정보 (Timeline)
- 시계열 데이터(Timeline Data)의 정렬 및 보간(Interpolation) 규칙.
- 차트 시각화를 위한 데이터 포인트 규격.

---

## 5. 책임 경계 및 안정성 정의 계획 (Responsibilities & Stability)

### 5.1 Server vs Client 책임 경계
- **Server 책임**:
    - 데이터의 무결성(Integrity) 및 정합성 보장.
    - 계산된 파생 데이터(Derived Data) 제공 (UI 연산 최소화).
- **Client 책임**:
    - 로케일(Locale) 기반 포맷팅 (날짜, 통화, 숫자).
    - 시각적 표현(차트 컬러, 인터랙션) 및 UX 로직.

### 5.2 안정성 및 확장성 원칙
- **필드 확장성 (Extensibility)**:
    - 향후 새로운 분석 모델 추가 시, Client 수정 없이 데이터를 수용할 수 있는 유연한 구조 설계 (예: Generic Key-Value Lists).
- **하위 호환성 (Backward Compatibility)**:
    - 구 버전 앱/Client가 신규 리포트 데이터를 조회했을 때의 처리 정책 (Unknown Field Ignore 등).
