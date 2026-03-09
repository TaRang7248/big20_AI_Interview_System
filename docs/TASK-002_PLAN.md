# TASK-002 Plan: imh_core 최소 패키지 구성 (config / errors / dto)

## 1. 현 상태 스캔 결과

### 1.1 문서 기반 상태 요약
- **CURRENT_STATE.md**:
    - 프로젝트는 현재 초기 단계(Phase 0 ~ 1 진입 전)이며, 운영/통제 기반 구조를 확정하는 것이 최우선 목표입니다.
    - `packages/imh_core` 위치가 핵심 로직 공유를 위한 표준으로 정의되어 있습니다.
    - 현재 로깅(logging) 기반 구축(TASK-001)이 완료된 것으로 파악됩니다.
- **TASK_QUEUE.md**:
    - TASK-002는 `config`, `errors`, `dto`의 최소 코어 확정과 로깅 유틸 연동 규약 표준화를 목표로 합니다.
    - 이후 TASK(Provider, FastAPI 엔트리 등)의 기반이 됩니다.

### 1.2 리포지토리 구조 분석
현재 `packages/imh_core` 디렉토리가 존재하며, 내부에는 `logging` 모듈만 포함되어 있습니다.
```text
IMH/IMH_Interview/packages/imh_core/
├── __init__.py
└── logging/  (TASK-001 산출물)
```

---

## 2. 목표 및 비목표 (Scope)

### 2.1 목표 (In Scope)
- **imh_core 패키지 내 필수 하위 모듈 설계 및 경계 확정**:
    - `config`: 환경 설정 관리 표준화 (단일 클래스)
    - `errors`: 공통 예외 클래스 및 에러 처리 체계 정의
    - `dto`: 데이터 전송 객체(DTO)의 기본 베이스 및 공통 스키마 정의
- **의존성 규칙 정의**: 모듈 간 참조 방향 및 외부 라이브러리 허용 범위 설정.

### 2.2 비목표 (Out of Scope)
- **비즈니스 로직 구현**: 면접 진행, 평가, 분석 로직 등은 포함하지 않습니다.
- **Provider 구현/연동**: LLM, STT 등의 구체적인 연동 코드는 제외합니다.
- **logging 모듈 수정**: `logging`은 TASK-001 완료 항목이므로 **코드를 수정하지 않습니다**. 단지 연동/사용 규약만 확인합니다.
- **환경별 Config 분기**: `MODE` (DEV/TEST/PROD)에 따른 로딩 전략은 이번에 구현하지 않고, 단순 구조로 유지합니다.

---

## 3. 패키지 경계 및 디렉토리 제안

### 3.1 제안 안 비교

| 항목 | (안 A) `packages/imh_core/...` | (안 B) `IMH/core/...` |
| :--- | :--- | :--- |
| **구조** | `IMH/IMH_Interview/packages/imh_core` | `IMH/IMH_Interview/IMH/core` |
| **특징** | 비즈니스 로직과 실행 환경(App)의 명확한 분리. 패키지 재사용성 극대화. | FastAPI 앱 내부 모듈로 배치. |
| **장점** | `packages/` 원칙 준수. 향후 MSA 분리나 타 프로젝트/스크립트 재사용 용이. | 앱 내부에서 import 경로가 짧아질 수 있음. |
| **단점** | 초기 진입 장벽이 약간 있을 수 있음 (경로 깊이). | **[원칙 위반]** `App/` 대신 `IMH/`를 실행 엔트리로 쓰는 규칙과 혼동 가능성. |

### 3.2 추천안: (안 A) `packages/imh_core`
**선택 근거**:
1.  **문서 원칙 준수**: `00_AGENT_PLAYBOOK.md`의 "Package-Centric" 원칙 준수.
2.  **명확한 경계**: Core 로직이 프레임워크나 실행 환경에 종속되지 않도록 분리.
3.  **현행 유지**: 이미 `logging` 모듈이 해당 위치에 존재함.

---

## 4. 세부 모듈 설계

### 4.1 config (환경설정)
- **파일 구조**: `packages/imh_core/config.py` (단일 모듈)
- **라이브러리**: `pydantic-settings` (FastAPI 생태계 표준).
- **구현 전략**:
    - `BaseSettings`를 상속받은 `IMHConfig` 클래스 **단일 정의**.
    - `.env` 파일 로딩 지원.
    - **주의**: `MODE` 환경변수에 따른 조건부 로직이나 상속 계층은 **이번 구현 범위에서 제외**합니다. (Simple is Best)
- **네이밍 규칙**: 대문자 스네이크 케이스 (예: `DB_URL`).

### 4.2 errors (예외 처리)
- **파일 구조**: `packages/imh_core/errors.py` (단일 모듈)
- **구조**:
    - `IMHBaseError(Exception)`: 최상위 부모 예외.
    - **속성**: `code` (식별자), `message` (메시지).
- **Logging 책임 명시**:
    - `errors` 모듈은 로깅 기능을 직접 수행하지 않습니다.
    - `logging` 모듈을 import는 하되, 이는 타입 힌팅이나 헬퍼 함수용이며, **`packages/imh_core/logging` 소스 코드는 절대 수정하지 않습니다.**

### 4.3 dto (데이터 전송 객체)
- **파일 구조**: `packages/imh_core/dto.py` (단일 모듈)
- **라이브러리**: `pydantic`.
- **책임 범위**: 순수 데이터 구조체 정의 (API Request/Response 베이스).

---

## 5. 공통 의존성 표준화 범위

### 5.1 허용/권장 라이브러리
- `pydantic`, `pydantic-settings`
- `typing`, `logging` (Standard config)

### 5.2 금지/주의 사항
- **순환 의존 금지**: `imh_core`는 상위 레이어(App, Feature packages)를 import 하지 않습니다.

---

## 6. 수용 기준 (Acceptance Criteria)

구조 혼선 방지를 위해 아래 **단일 파일 구조**로 산출물을 확정합니다.

1.  **파일 생성 확인**:
    - `packages/imh_core/config.py` (패키지 폴더 `config/` 아님)
    - `packages/imh_core/errors.py` (패키지 폴더 `errors/` 아님)
    - `packages/imh_core/dto.py` (패키지 폴더 `dto/` 아님)
    - *선택 근거*: 초기 단계에서 불필요한 `__init__.py` 및 폴더 깊이를 줄여 **직관적이고 가벼운 구조**를 유지하기 위함입니다.
2.  **동작 검증**:
    - `python -c "from packages.imh_core import config, errors, dto"` 성공.
    - `IMHConfig`가 `.env` 값을 정상적으로 읽어오는지 확인.
    - `IMHBaseError` 상속 클래스 동작 확인.
3.  **Logging 보존**:
    - `packages/imh_core/logging` 폴더 내용이 변경되지 않았음을 확인.

---

## 7. 작업 절차 (WBS 초안)

1.  **TASK-002-01**: `packages/imh_core/errors.py` 생성
    - `IMHBaseError` 정의.
2.  **TASK-002-02**: `packages/imh_core/dto.py` 생성
    - `BaseDTO` 정의.
3.  **TASK-002-03**: `packages/imh_core/config.py` 생성
    - `IMHConfig` 정의 (단일 클래스).
4.  **TASK-002-04**: 기본 동작 확인 (Ad-hoc Verification)
    - 정식 테스트 슈트가 아닌, **간단한 실행 스크립트**로 import 및 기본 객체 생성을 확인합니다.
5.  **TASK-002-05**: 문서 업데이트 (`DEV_LOG.md`)

---

## 8. 리스크 및 미결정 질문 목록

### 8.1 질문 (Resolved)
- **Q1. Config/DTO 구조**: **단일 파일(`module.py`)** 방식으로 확정. (Acceptance Criteria 반영)
- **Q2. Mode 분기**: **제외**. 단일 Config 클래스로 진행.

### 8.2 리스크
- **기존 호환성**: `logging` 모듈과의 합성을 주의해야 함 (Circular Import 방지).
