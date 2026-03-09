# TASK-013: 리포트 저장 / 이력 관리 (Persistence & History) 계획

## 1. 개요 (Overview)
- **목표**: TASK-012에서 생성된 `InterviewReport`(JSON)를 영구적(Persistent)으로 저장하고, 이후 사용자가 자신의 면접 이력(History)을 조회할 수 있는 기반을 마련한다.
- **핵심 전략**: 현재 Phase에서는 복잡한 RDBMS 도입 대신, **File-system based JSON Repository** 패턴을 사용하여 "구현 편의상"과 "데이터 구조 유연성"을 확보한다. (No-DB Migration 정책 준수)
- **역할**: `InterviewReport`의 생명주기(Lifecycle) 중 "저장"과 "조회"를 담당하는 **Persistence Layer**.

## 2. 범위 (Scope)

### 2.1 포함 (In-Scope)
- **패키지 신설**: `packages/imh_history`
  - 리포트 저장, 조회, 이력 관리를 담당하는 독립 패키지.
- **저장소(Repository) 구현**:
  - **개념 인터페이스**: `HistoryRepository` (Interface)
  - **파일 기반 구현체**: `FileHistoryRepository` (Implementation)
    - `IMH/IMH_Interview/data/reports/` 디렉토리에 JSON 파일로 저장.
  - CRUD 인터페이스: `save()`, `find_by_id()`, `find_all()`.
- **데이터 구조 정의**:
  - **Storage Format**: `InterviewReport` 전체를 담은 JSON 파일.
  - **Metadata 전략**: 별도의 인덱스 파일(예: `index.json`)을 두지 않고, 목록 조회 시 **파일명(Timestamp)과 JSON 내부 필드를 실시간/캐시 파싱**하여 구성한다.
- **이력 관리 정책**:
  - `interview_id` 생성 규칙 (UUID v4 예정).
  - 파일명 규칙 (예: `{timestamp}_{interview_id}.json`).
- **Git 관리 정책**:
  - `IMH/IMH_Interview/data/` 디렉토리 자체는 유지하되, **`data/reports/` 내부의 모든 파일(.json)은 `.gitignore`에 포함**하여 저장소에 커밋되지 않도록 한다.

### 2.2 제외 (Out-of-Scope)
- **RDBMS / SQL DB 도입**:
  - SQLite, PostgreSQL 등 DB 엔진 설치 및 스키마 관리는 현재 단계에서 수행하지 않음.
- **UI 구현**:
  - 이력 리스트 화면, 상세 조회 화면 개발 제외.
- **User Management**:
  - 다중 사용자(회원가입/로그인) 구분 로직은 제외 (단일 사용자 가정 또는 `user_id`를 파라미터로 받되 고정값 사용).

## 3. 아키텍처 및 데이터 설계

### 3.1 디렉토리 구조 (Directory Structure)
```
IMH/IMH_Interview/
├── data/ (신규 생성)
│   └── reports/ (저장소 - git ignore)
│       ├── 20261010_120000_uuid-aaa-bbb.json
│       └── ...
└── packages/
    └── imh_history/ (신규 패키지)
        ├── __init__.py
        ├── dto.py          # HistoryMetadata 등
        └── repository.py   # HistoryRepository (ABC) / FileHistoryRepository (Impl)
```

### 3.2 데이터 저장 포맷
- **파일 경로**: `data/reports/{YYYYMMDD_HHMMSS}_{interview_id}.json`
- **파일 내용**: TASK-012에서 정의한 `InterviewReport` JSON 그대로 저장.
- **식별자 정책**:
  - `interview_id`: UUID v4
  - 정렬/필터링: 파일명에 포함된 Timestamp를 우선 사용한다.

### 3.3 책무 분리 (Responsibility)
| 계층 | 패키지 | 역할 | 비고 |
| :--- | :--- | :--- | :--- |
| **Domain** | `imh_eval`, `imh_report` | 리포트 생성, 점수 계산 | 기존 완료 |
| **Persistence** | **`imh_history` (New)** | **파일 IO, 저장, 검색** | **금번 구현** |
| **API** | `IMH/api/*` | 엔드포인트 노출 | 추후 TASK-014 |

## 4. 검증 계획 (Verification Plan)

### 4.1 Mock Data 기반 기능 검증 (`scripts/verify_task_013.py`)
1. **Mock Report 생성**:
   - `imh_report`의 DTO를 모방한 Mock Dictionary 생성.
2. **Save**:
   - `HistoryRepository.save(report)` 호출.
   - `data/reports/` 폴더에 파일 생성 여부 확인.
   - JSON 내용 무결성 확인.
3. **Load (Find By ID)**:
   - 저장된 ID로 조회 시 원본 데이터와 일치하는지 확인.
4. **List (Find All)**:
   - 저장된 파일 목록을 최신순으로 가져오는지 확인.
   - 요약(Summary) 정보가 정상 파싱되는지 확인.

### 4.2 예외 처리 검증
- 잘못된 ID 요청 시 `None` 또는 `NotFoundException` 처리 확인.
- 쓰기 권한/경로 에러 시 적절한 에러 로그(`logs/agent/*.log`) 남기는지 확인.

## 5. 작업 단계 (Work Breakdown)
1. **기반 마련**:
   - `IMH/IMH_Interview/data/reports` 디렉토리 및 `.gitignore` 설정.
2. **패키지 구현**:
   - `packages/imh_history/dto.py`: (`HistorySummary` 등)
   - `packages/imh_history/repository.py`: (`HistoryRepository` 인터페이스 및 `FileHistoryRepository` 구현)
3. **검증 스크립트 작성**:
   - `scripts/verify_task_013.py`
4. **DEV_LOG 업데이트**:
   - 변경 사항 기록.

## 6. 승인 요청
- **저장 방식**: DB 없는 "JSON 파일 저장 방식"을 Phase 4의 표준으로 승인 요청.
- **패키지명**: `imh_history` 사용 승인 요청.
