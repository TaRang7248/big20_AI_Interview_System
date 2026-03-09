# TASK-012: 평가 결과 리포팅 / 해석 계층 설계 계획

## 1. 개요 (Overview)
- **목표**: TASK-011에서 산출된 **정량 평가 결과(Evaluation Result)**와 **근거 데이터(Evidence)**를 사용자에게 전달 가능한 **리포트 형태(Interview Report)**로 가공하고, 점수에 대한 **해석(Interpretation)**을 제공하는 계층을 설계한다.
- **역할**: `Evaluation Layer` (Raw Data/Score)와 `User Interface` (View) 사이의 **BFF(Backend For Frontend) 성격의 변환/해석 로직**을 담당한다.
- **위치**: `packages/imh_eval`의 출력을 입력으로 받아, 최종 응답 또는 저장용 리포트 포맷을 생성하는 `packages/imh_report` (신규 예정) 또는 `imh_analysis` 내의 리포팅 모듈.

## 2. 범위 (Scope)

### 2.1 포함 (In-Scope)
- **리포트 데이터 구조 설계**:
  - 사용자에게 보여질 최종 리포트의 JSON 구조 정의.
  - UI 렌더링에 최적화된 계층적 구조(Summary -> Details -> Insights).
- **해석 로직(Interpretation Strategy) 정의**:
  - 단순 점수(예: 4.0)를 등급(예: "우수") 또는 문장(예: "직무 이해도가 높습니다.")으로 변환하는 매핑/생성 로직.
  - `tag_code` 기반의 피드백 텍스트 매핑 규칙 수립.
- **데이터 변환(Transformation)**:
  - Evaluation Result(+Raw Analysis Data) → **Report Model** 로의 변환 파이프라인 설계.
- **품질 기준 정의**:
  - 리포트가 갖춰야 할 필수 항목(종합 점수, 영역별 분석, 강/약점) 정의.

### 2.2 제외 (Out-of-Scope)
- **UI 구현**:
  - 실제 화면(HTML/React 등) 개발 금지. (오직 데이터 구조만 설계)
- **리포트 영구 저장(Persistence)**:
  - DB 스키마 설계 및 Insert 로직은 TASK-012 범위가 아님. (단, 저장 가능한 JSON 구조를 만드는 것까지는 포함)
- **복잡한 LLM 기반 코멘트 생성**:
  - 현재 단계에서는 Rule-based 또는 Template-based 해석에 집중하며, 비용이 드는 LLM 기반의 자유 텍스트 생성은 구조상 'Placeholder'로만 두거나 제외한다.

## 3. 리포팅 계층 정의 (Responsibility)

### 3.1 책임 경계
| 계층 | 역할 (Role) | 데이터 예시 |
| :--- | :--- | :--- |
| **Analysis Layer** | 현상 관측 | "음성 떨림 30Hz", "시선 회피 5회" |
| **Evaluation Layer (Prev)** | 점수/근거 산출 | "태도 점수 3점 (감점 요인: 시선 불안)", `tag: attitude.gaze` |
| **Reporting Layer (This)** | **의미 전달/구조화** | **"시선 처리가 다소 불안하여 자신감이 부족해 보일 수 있습니다." (개선 제안 포함)** |
| **Presentation Layer (UI)** | 시각화 |Radar Chart 그리기, 텍스트 렌더링 |

### 3.2 입력/출력 정의 (I/O)
- **Input (From Evaluation Layer)**:
  - `EvaluationResult`: 영역별 점수(Scores), 태그(Tags), 근거 데이터(Raw Evidence).
  - `Metadata`: 면접자 정보(지원 직군, 경력 등), 질문 정보.
- **Output (To Client/Storage)**:
  - `InterviewReport`: UI가 소비하기 쉬운 구조화된 JSON.
  - 구성: Header(요약), Body(상세), Footer(종합 제언).

## 4. 리포트 구성 설계안 (Report Structure)

### 4.1 섹션 구조
1. **Executive Summary (종합 요약)**
   - **Total Score**: 100점 만점 환산 점수.
   - **Grade**: S/A/B/C/D 등급 (점수 구간별 매핑).
   - **Radar Chart Data**: 4대 영역(직무/문제해결/의사소통/태도)의 5각/6각 방사형 데이터.
   - **Keyword**: 지원자를 나타내는 핵심 키워드 3~5개 (Top Tags 기반).

2. **Detailed Analysis (영역별 상세 분석)**
   - 각 영역(4대 영역)에 대해:
     - **Sub Score**: 해당 영역 점수.
     - **Level Description**: 점수에 따른 수준 설명 (예: "직무 지식이 풍부합니다").
     - **Key Evidence**: 판단의 근거가 된 주요 관측 데이터 (예: "CS 관련 용어 15회 사용").
     - **Feedback**: `tag_code`에 매핑된 구체적 피드백 메시지.

3. **Strengths & Weaknesses (강점과 약점)**
   - **Top 3 Strengths**: 점수가 가장 높거나 긍정 태그가 많은 항목.
   - **Top 3 Weaknesses**: 점수가 낮거나 감점 태그가 식별된 항목.

4. **Actionable Insights (개선 가이드)**
   - 약점을 보완하기 위한 구체적인 **Action Item** 제안.
   - 예: "시선 처리가 불안정하므로, 카메라 렌즈를 응시하는 연습이 필요합니다."

## 5. 품질 기준 및 검증 전략 (Plan)

### 5.1 품질 기준 (Acceptance Criteria)
- **완전성 (Completeness)**: 루브릭의 4대 영역이 누락 없이 리포트에 포함되어야 한다.
- **해석 가능성 (Interpretability)**: 모든 수치 데이터(점수)는 반드시 그에 상응하는 텍스트 설명(등급 또는 코멘트)을 동반해야 한다.
- **구조적 안정성**: `tag_code`가 없거나 예외적인 평가 결과(0점 등)가 입력되어도 리포트 생성 과정이 중단되지 않고 "데이터 부족" 등으로 표기되어야 한다.

### 5.2 검증 계획
1. **Mock Data Test**:
   - `EvaluationResult`의 다양한 케이스(고득점/저득점/결측치 포함)를 Mocking 하여 주입.
2. **Schema Validation**:
   - 생성된 리포트 JSON이 사전에 정의할 `ReportSchema`와 일치하는지 검증.
3. **Rendering Simulation**:
   - 생성된 JSON을 눈으로 확인하여, UI에 표현될 텍스트가 자연스러운지 검토 (Human Review).

## 6. 리스크 및 의존성 (Risks & Dependencies)
- **`tag_code` 의존성**: TASK-011에서 정의한 태그 체계가 변경되면 리포팅 매핑 로직도 수정되어야 함. (→ `_refs` 문서 동기화 필수)
- **텍스트 길이 제어**: 모바일/웹 UI에서의 가독성을 위해 생성되는 텍스트(피드백/개선제안)의 길이를 적절히 제한하거나 요약 필드를 둬야 함.

## 7. 작업 단계 (Work Breakdown)
1. **리포트 스키마(DTO) 정의**: `packages/imh_report/dto.py` (예정)에 `InterviewReport` 구조 정의.
2. **해석/매핑 로직 구현**: 점수 → 등급 변환, 태그 → 메시지 변환 로직(`TagTranslator`) 구현.
3. **리포트 생성기 구현**: `ReportGenerator` 클래스 구현 (Input → Output 변환).
4. **검증 스크립트 작성**: `scripts/verify_task_012.py` 작성 및 테스트.
