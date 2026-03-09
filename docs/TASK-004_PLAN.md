# TASK-004 Plan: FastAPI 최소 엔트리 + Healthcheck

## A. 현 상태 확인

### 1. 선행 TASK 완료 상태
- **[문서 근거: CURRENT_STATE.md]**:
    - **TASK-002 (imh_core)**: `packages/imh_core` 내 설정(`config`), 에러(`errors`), DTO(`dto`) 기반이 마련됨.
    - **TASK-003 (imh_providers)**: `packages/imh_providers` 내 추상화 계층 및 Mock 구현체가 준비됨.
- **[문서 근거: TASK_QUEUE.md]**: 현재 진행 가능한 **ACTIVE** 작업은 `TASK-004` (FastAPI 엔트리) 뿐임.

### 2. 목표 (Goal)
- **FastAPI 진입점(Entry Point)**: 애플리케이션 실행을 담당하는 `IMH/main.py` 생성.
- **헬스체크(Healthcheck)**: 서버 생존 여부를 확인하는 `/health` 엔드포인트 구현.
- **Core 연동**: `imh_core`의 설정 및 로깅 모듈을 엔트리에 연결.

---

## B. FastAPI 엔트리 책임 범위 정의

### 1. 역할 및 책임 (Role & Responsibility)
- **Thin Entry**: `IMH/main.py`는 오직 "애플리케이션 조립"과 "실행 설정"만 담당한다. 비즈니스 로직을 포함하지 않는다.
- **Lifecycle Management**: 앱 시작/종료 시점의 리소스 초기화(로깅 설정 등)를 관리한다.
- **Routing Assembly**: 도메인별 라우터(`api/`)를 메인 앱에 등록(`include_router`)한다.

### 2. 포함/제외 요소 (Scope)
- **[포함]**:
    - FastAPI 인스턴스 생성.
    - CORS 등 필수 미들웨어 설정.
    - 전역 예외 처리 핸들러 등록 (`imh_core.errors` 연동).
    - `/health` 라우터 등록.
- **[제외]**:
    - 실제 비즈니스 로직 (Controller/Service).
    - DB 연결 (추후 별도 모듈화).
    - 인증/인가 로직.

---

## C. Healthcheck 엔드포인트 설계

### 1. 명세 (Specification)
- **Method**: `GET`
- **Path**: `/health`
- **Response Format (JSON)**:
  ```json
  {
      "status": "ok",
      "version": "0.1.0",
      "timestamp": "2024-02-14T12:00:00Z"
  }
  ```
- **HTTP Status**: 200 OK

### 2. 범위 및 한계
- **Liveness Probe**: 애플리케이션 프로세스가 살아있고 요청을 받을 수 있는지만 확인한다.
- **No Deep Check**: DB나 외부 시스템 연결 상태까지 확인하지 않는다 (이는 추후 `/ready`로 분리).

---

## D. 디렉토리 및 모듈 배치 전략

### 1. 구조 제안
```text
IMH/IMH_Interview/
├── IMH/                  # FastAPI App (Presentation Layer)
│   ├── __init__.py
│   ├── main.py           # [NEW] 실행 진입점
│   └── api/              # [NEW] API 라우터 모음
│       ├── __init__.py
│       └── health.py     # [NEW] Healthcheck 라우터
├── packages/             # Core & Business Logic (Existing)
│   └── imh_core/         # Config, Logging, Errors
```

### 2. 전략적 이유
- **계층 분리**: `IMH/`는 API 진입점 역할만 수행하며, 핵심 로직은 `packages/`에 위임하여 재사용성을 높인다.
- **확장성**: 향후 `TASK-005` (Playground) 등 새로운 기능 추가 시 `IMH/api/playground/` 하위에 라우터를 추가하고 `main.py`에 등록하는 구조로 확장 가능하다.

---

## E. 로깅 연계 및 확장 전략

### 1. 로깅 연계 (Concept)
- **초기화**: `main.py`의 `lifespan` 이벤트 내에서 `imh_core.logging`을 초기화하여 전역 로거 설정을 적용한다.
- **에러 핸들링**: 전역 Exception Handler에서 `imh_core` 로거를 사용해 `stack_trace`를 파일에 기록한다.

### 2. 이후 TASK 연결 포인트
- **TASK-005 (Playground STT)**: `IMH/api/playground/stt.py` 라우터 추가 -> `main.py` 등록.
- **TASK-006 (Playground PDF)**: `IMH/api/playground/pdf.py` 라우터 추가 -> `main.py` 등록.

---

## F. 승인 기준 (Definition of Done)

### 1. Plan 승인 기준 (Plan DoD)
- [ ] **책임 범위**: `main.py`가 Thin Entry 원칙을 준수하는가?
- [ ] **구조**: `IMH/` 하위 구조가 확장성 있게 설계되었는가?
- [ ] **Healthcheck**: 응답 포맷이 명확히 정의되었는가?
- [ ] **로깅**: `imh_core`와의 연계 방식이 명시되었는가?

### 2. Implement 단계 DoD (예고)
- [ ] `IMH/main.py` 실행 시 FastAPI 서버가 정상 구동됨.
- [ ] `GET /health` 요청 시 200 OK와 JSON 응답 반환.
- [ ] 서버 실행/종료 로그가 `logs/runtime/` 내 파일에 기록됨.
- [ ] 검증 스크립트 실행 통과.

---

## G. Implement 단계 예고 (Artifacts)

승인 시 아래 파일들이 생성됩니다.

1.  `IMH/main.py` (신규)
2.  `IMH/api/__init__.py` (신규)
3.  `IMH/api/health.py` (신규)
4.  `scripts/verify_task_004.py` (신규 - 서버 실행 및 Healthcheck 검증)
