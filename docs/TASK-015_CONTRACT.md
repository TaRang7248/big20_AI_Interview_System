# TASK-015: Report Consumption Standards (UI/Client Contract)

## 1. 개요 (Overview)
본 문서는 `IMH AI Interview` 시스템의 리포트 조회 API(TASK-014)를 소비하는 **UI 및 외부 Client를 위한 데이터 해석 규격(Contract)**입니다.
API Response(JSON)의 각 필드가 UI에서 어떻게 표현되어야 하며, 데이터 부재(Null) 시 어떻게 처리해야 하는지에 대한 **소비 측면의 책임과 약속**을 정의합니다.

---

## 2. 리포트 소비 주체 (Consumers)

| 주체 | 역할 | 데이터 소비 특징 | 권장 표현 방식 |
|---|---|---|---|
| **Candidate** | 면접 결과 확인 | **요약 중심**, 결과 지향 | 점수/등급/피드백 위주, 복잡한 데이터 숨김 |
| **Recruiter** | 평가 상세 분석 | **근거 중심**, 과정 지향 | 타임라인, 원본 매핑, 비교 분석 데이터 노출 |
| **System** | 데이터 연동 | **포맷 중심**, 무결성 지향 | Null Safe, 타입 엄격성 준수 |

---

## 3. 리포트 데이터 소비 가이드 (Consumption Guide)

### 3.1 요약 및 헤더 (Header & Summary)
- **종합 점수 (Total Score)**:
  - 범위: `0 ~ 100` (소수점 1자리까지 유효, 예: `85.5`).
  - 표현: 원형 차트 또는 게이지 바 권장.
  - **Null 처리**: 분석 실패 또는 진행 중인 경우 `0` 또는 `-`로 표시하되, "분석 중/산출 불가" 라벨 병기.
- **종합 등급 (Overall Grade)**:
  - 값: `S`, `A`, `B`, `C`, `F`.
  - 표현: 색상 코딩 권장 (S/A: Green/Blue, B: Yellow, C/F: Red/Gray).
- **면접 일시 (Timestamp)**:
  - 포맷: ISO 8601 (`YYYY-MM-DDTHH:mm:ss`).
  - UI 처리: Client의 로컬 타임존으로 변환하여 `YYYY. MM. DD. HH:mm` 형식으로 표시.

### 3.2 상세 분석 (Analysis Details)
- **영역별 점수 (Category Scores)**:
  - 4대 영역(직무, 문제해결, 의사소통, 태도)의 점수.
  - **Radar Chart** 시각화 권장.
  - 데이터 누락 시 해당 축을 `0`으로 처리하거나 차트 렌더링 제외.
- **타임라인 데이터 (Timeline Data)**:
  - `start_time` ~ `end_time` 구간 정보.
  - UI는 해당 구간을 클릭 시 원본 오디오/비디오의 해당 시점으로 **Seek** 기능 제공 권장.
- **피드백 및 인사이트 (Feedback & Insights)**:
  - 텍스트 줄바꿈(`\n`)을 그대로 렌더링.
  - `strength`(강점) / `weakness`(보완점) / `actionable`(조언) 구분하여 아이콘 또는 섹션 분리 표시.

### 3.3 근거 데이터 (Evidence)
- **매핑 (Mapping)**:
  - 모든 정량 점수 근처에 "상세 보기" 또는 "근거 확인" 버튼 배치 권장.
  - 근거 클릭 시 연관된 `transcript` 또는 `video_segment`로 이동.
- **데이터 부재 정책**:
  - `evidence` 필드가 빈 배열(`[]`)이거나 `null`인 경우, UI에서 "근거 데이터 없음"을 명시하고 링크 비활성화.

---

## 4. 책임 경계 (Boundaries of Responsibility)

### 4.1 Server (Backend) 책임
- **무결성**: `interview_id`, `total_score` 등 필수 필드의 존재 보장.
- **계산 완료**: UI에서 별도의 가중치 계산이나 합산 로직을 수행하지 않도록 **최종 계산된 값** 제공.
- **다국어 데이터 제공**: 필요 시 서버에서 번역된 텍스트 제공 (현재는 한국어 표준).

### 4.2 Client (Frontend) 책임
- **포맷팅**: 날짜/시간 포맷, 숫자 자릿수 포맷팅 (`85.50` -> `85.5`), 통화 표시.
- **시각화**: 차트 색상, 애니메이션, 반응형 레이아웃 처리.
- **예외 처리**: Optional 필드가 `null`일 때의 UI Fallback (기본값 표시 또는 섹션 숨김).
- **인터랙션**: 타임스탬프 클릭 시 미디어 플레이어 제어.

---

## 5. 안정성 및 확장성 원칙 (Stability & Extensibility)

### 5.1 필드 확장 (Extensibility)
- 리포트 JSON에 새로운 필드가 추가되더라도, 기존 UI는 **오류 없이 렌더링(Graceful Degradation)** 되어야 한다.
- 알 수 없는 필드(Unknown Fields)는 **무시(Ignore)** 하는 것을 기본 정책으로 한다.

### 5.2 하위 호환성 (Backward Compatibility)
- API 버전(`v1`) 내에서는 Breaking Change(필드 삭제, 타입 변경)를 지양한다.
- 필수 필드가 추가되어야 하는 경우, API 버전을 올리거나(`v2`), 기존 필드에 기본값을 채워서 호환성을 유지한다.

---

## 6. 결론 (Conclusion)
본 규격 문서는 `IMH AI Interview`의 리포트 데이터를 소비하는 모든 UI 및 Client가 준수해야 할 해석 지침입니다.
이 규격을 준수함으로써 Backend와 Frontend는 독립적으로 발전할 수 있으며, 일관된 사용자 경험을 제공할 수 있습니다.
