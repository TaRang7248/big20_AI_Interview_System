# TASK-020: 관리자 지원자 조회/필터 규격 (Plan)

이 문서는 관리자가 **공고(Job Posting) 단위**로 지원자 목록을 조회하고, 정책에 정의된 조건으로 필터링하기 위한 **규격과 API Contract**를 정의한다.  
현재 단계는 구현이 아닌 **설계(Plan)** 단계이며, 실제 코드는 작성하지 않는다.

---

## 1. 목적 정의

- **관리자(채용 담당자)**가 특정 공고에 지원한 지원자들의 상태(진행 중, 완료, 중단 등)와 결과(점수, 합불)를 효율적으로 조회할 수 있는 규격을 수립한다.
- 대량의 지원자 데이터 중 필요한 대상만 선별할 수 있는 **필터링 로직의 표준**을 정의한다.
- Frontend(관리자 대시보드)와 Backend(API) 간의 데이터 교환 규약(Contract)을 확정한다.

## 2. 정책 근거

본 계획은 다음 문서를 유일한 정책적 근거로 삼는다.

- **정책 문서**: `IMH/IMH_Interview/_refs/26.02.11(수)인터뷰 정책 스펙.md`
- **관련 섹션**: 
  - **#14. 관리자 필터/조회 정책** (핵심 근거)
  - **#14.3 면접 세션 상태값 정의** (Enum 기준)
  - **#3.1 실전 1차 AI 면접** (공고 기반 동작)

## 3. 관리자 조회 대상 엔티티 정의범위

조회 대상은 개별 유저가 아닌 **"특정 공고(Job Posting)에 종속된 면접 세션(Interview Session)"**들의 집합이다.

- **Root Aggregation**: `Job ID` (필수 파라미터)
- **Target Entity**: `Interview Session Summary` (단건 세션의 요약 정보)
- **관계**: 1 Job : N Sessions

목록 조회 시에는 리포트 전체 내용(JSON Full Dump)을 로딩하지 않으며, **목록 표시에 필요한 요약 정보(Meta Info)**만 반환함을 원칙으로 한다.

## 4. 필수 필터 계층 및 규격 (Query Parameter)

### 4.1 날짜 고정 필터 (Required)
- **기준 필드**: `started_at` (면접 시작 시각)만 사용한다.
- **APPLIED 처리**: `started_at`이 존재하지 않는 `APPLIED` 상태 세션은 **날짜 필터 적용 시 조회 결과에서 제외**한다.
  - 관리자가 "기간"을 설정했다는 것은 "해당 기간에 면접을 본 사람"을 찾겠다는 의도로 해석하며, 시작하지 않은 지원자는 제외한다.
- **동작**: `start_date <= started_at <= end_date`

### 4.2 상태 필터 및 중단 별칭 (Status Alias)
- **Status Enum**: `status=IN_PROGRESS,COMPLETED` 등 다중 선택 가능.
- **Alias (`is_interrupted`)**:
  - `is_interrupted=true` 파라미터는 `status=INTERRUPTED`와 동일한 의미이다.
  - **충돌 방지**: 두 파라미터가 동시에 전달될 경우, 내부적으로 `OR` 연산이 아닌 **"상태 집합의 합집합"**으로 처리하거나, 명시적으로 `status` 파라미터를 우선한다. (구현 시 Alias 파싱 로직에서 `INTERRUPTED`를 status 목록에 추가하는 방식으로 통일)

### 4.3 결과 필터 (Result) - EVALUATED Status Only
- **전제**: `result` 필터(`PASS`, `FAIL`)는 오직 `status=EVALUATED`인 세션에만 적용된다.
- **판정 근거**: Evaluation Engine이 산출한 최종 결과 필드(`grade` or `pass_fail`)를 기준으로 한다.
  - 본 Plan 문서는 점수 임계값(Threshold)을 정의하지 않으며, 이는 평가 엔진의 스키마를 따른다.
- **PENDING**: `COMPLETED` 상태이지만 평가 데이터가 없는 경우를 의미하며, `PASS/FAIL` 판정 대상이 아니다.

## 5. 검색 및 추천 필터 (Optional)

### 5.1 검색 (Keyword)
- **대상**: 지원자 이름, 이메일
- **제약 조건**:
  - **최소 길이**: 2글자 이상 입력 필수 (미만 시 400 Bad Request).
  - **이메일**: **정확 일치(Exact Match)**만 허용 (개인정보 보호 및 인덱스 효율성).
  - **이름**: 부분 일치(Partial Match) 허용.
  - **입력 정규화**: Trim 및 이메일 Lowercasing 필수 적용.
- **보안**: 검색 키워드는 로그 파일에 평문으로 남기지 않는다. (Masking 또는 Hash 처리)

### 5.2 약점 필터 (Weakness) - Deferred
- **Status**: **Phase 7(DB 인덱싱) 이후 별도 TASK로 이관됨.** (본 TASK 범위 아님)
- **제약**: 현재 단계에서 `weakness` 파라미터 전달 시 **400 Bad Request**로 명시적 거부한다.

## 6. 세션 상태 Enum 처리 방식

세션 상태는 **오직 정책 문서(#14.3)에 정의된 값**만을 사용한다.  
(근거: `IMH/IMH_Interview/_refs/26.02.11(수)인터뷰 정책 스펙.md`)

### Status Enum (Immutable Contract)
1. **APPLIED**: 지원 완료, 면접 시작 전
2. **IN_PROGRESS**: 면접 진행 중
3. **COMPLETED**: 정상 종료
4. **INTERRUPTED**: 비정상 중단
5. **EVALUATED**: 평가 및 점수 산출 완료

## 7. 정렬 및 페이징 (Pagination & Sorting)

- **Pagination**: `page` (default=1), `size` (default=20)
- **Sorting**: `sort_by=started_at` (default), `order=desc` (default)

## 8. 개인정보 노출 범위 (Response Summary DTO)

목록 조회 API (`GET /jobs/{job_id}/applicants`)의 응답은 **관리자 조회 목적에 필요한 최소한의 정보**만 노출한다.

```json
{
  "job_id": "string",
  "total_count": 100,
  "page": 1,
  "size": 20,
  "items": [
    {
      "session_id": "uuid",
      "applicant_name": "홍길동",  // 관리자 권한 필수
      "started_at": "timestamp",
      "status": "COMPLETED",     // Enum
      "result": "PENDING",       // PASS | FAIL | PENDING (EVALUATED 상태만 PASS/FAIL 가능)
      "score_total": 85,         // EVALUATED 상태만 노출, 아니면 null
      "is_interrupted": false
    }
  ]
}
```

## 9. 정책-엔진-조회 계층 간 경계

| 계층 (Layer) | 역할 (Role) | 책임 (Responsibility) |
|---|---|---|
| **Presentation** | 요약 및 변환 | DTO 변환, Alias(`is_interrupted`) 처리, 검색어 길이 검증 |
| **Application** | 조정 (Coordination) | `PENDING` 판단, `Evaluation Engine` 결과 매핑 |
| **Domain** | 규격 정의 | Status Enum, Job Policy 정합성 보장 |
| **Infrastructure** | Query 실행 | `started_at` 날짜 필터링, 이메일 Exact Match 실행 |

## 10. Phase 5 기존 엔진들과의 정합성 체크

- [ ] **Job Policy Engine**: 유효한 Job ID 여부 검증.
- [ ] **Interview Session Engine**: 저장된 상태값이 정책 Enum과 일치 보장.
- [ ] **Evaluation Engine**: `EVALUATED` 상태 데이터의 `pass/fail` 필드 존재 여부 확인.

## 11. 금지 사항 (정책 위반 방지)

1. **APPLIED 날짜 필터링 금지**: `started_at`이 없는 세션을 날짜 범위로 억지로 조회하려 하지 않는다.
2. **검색어 로깅 금지**: 이메일/이름 등 PII 검색어를 로그에 남기지 않는다.
3. **PASS/FAIL 조기 노출 금지**: `COMPLETED` 상태라도 평가 엔진 확정 전에는 `PENDING`으로 취급한다.
4. **연습 모드 혼입 금지**: 실전 모드 데이터만 조회한다.

---

이 문서는 TASK-020의 **최종 설계(Plan)** 산출물이며, 이후 구현 단계의 엄격한 기준점이 된다.
