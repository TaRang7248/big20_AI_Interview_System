# TASK-029_PLAN v1.1: 시스템 기준선 합치 및 아키텍처 보호 강화 (Baseline Alignment)

## 1. 개요

- **목적**: 문서(00_AGENT_PLAYBOOK.md, CURRENT_STATE.md, ERD 가이드)와 코드(DB Schema, DI, Repository) 사이의 불일치를 제거하고, PostgreSQL 단일 권위(Authority)를 실질적으로 확정한다.
- **Single Source of Truth (SSoT)**: **문서/ERD 기준(안 1)**으로 코드 및 DB를 강제 정렬한다.
- **리스크 수준**: **HIGH** (데이터 유실 가능성, 세션 복구 불가, 문서 기반 작업 시 오작동 위험 고조)
- **수행 원칙**:
  - 기능 추가가 아닌 기준선 합치 작업이다.
  - 핵심 계약(Authority, Snapshot, No Write-Back)은 절대 변경하지 않는다.
  - 데이터 파괴(DROP)는 개발 환경임을 감안하여 비파괴 정렬(Rename)이 불가능할 경우에만 예외적으로 허용한다.

---

## 2. 사실관계 확인 체크리스트 (Audit 결과)

본 작업 착수 전 아래 항목의 불일치 상태를 최종 확인한다.

1.  **DI 주입 상태 (`IMH/api/dependencies.py`)**
    - `get_session_history_repository()`가 `FileHistoryRepository`를 반환하고 있음. (문서상 PostgreSQL 전환 상태와 모순)
2.  **상태 영속화 결함**
    - `PostgreSQLSessionRepository.update_status`가 호출되더라도, `HistoryRepository` 인터페이스의 실제 구현(`postgresql_repository.py`)이 status 업데이트 로직 없이 로그만 남김.
3.  **테이블 네이밍 Drift (`scripts/init_db.py`)**
    - 코드: `sessions`, `reports` 사용.
    - 문서: `interviews`, `evaluation_scores` 기준.
4.  **Redis Miss 동작 결함 (`packages/imh_session/engine.py`)**
    - `_load_or_initialize_context` 로직이 Redis Miss 시 PG(Authority) 조회가 아닌 새 컨텍스트를 생성하여 데이터 정합성 파괴 위험이 있음.

---

## 3. SSoT 정렬 전략: [안 1] 문서/ERD 기준 합치

- **전략**: `00_AGENT_PLAYBOOK.md` 및 ERD 가이드에 명시된 명칭을 정답으로 확정하고 코드를 수정한다.
- **장점**: 설계 의도를 보존하고 에이전트의 문서 기반 판단 신뢰도를 100%로 복구한다.
- **단점**: SQL 쿼리 전반 및 DB 스키마 수정 비용 발생.

---

## 4. 세부 실행 계획

### 4.1 변경 대상 파일 및 내용

| 파일 경로 | 변경 내용 |
|:---|:---|
| `IMH/api/dependencies.py` | `PostgreSQLHistoryRepository` 주입 고정 및 Dual Write 로직 제거 준비 |
| `scripts/init_db.py` | 테이블명 정렬 (`sessions` -> `interviews`, `reports` -> `evaluation_scores`) |
| `packages/imh_session/infrastructure/postgresql_repo.py` | SQL 쿼리 내 테이블명 및 필드 매핑을 플레이북 기준으로 수정 |
| `packages/imh_history/postgresql_repository.py` | `update_interview_status`의 실제 DB UPDATE 쿼리 구현 |
| `packages/imh_session/engine.py` | `_load_or_initialize_context`에 Redis Miss 시 PG 데이터를 복구하는 **Hydration** 로직 추가 |

### 4.2 마이그레이션 및 롤백 전략
- **데이터 처리 원칙**: 비파괴 정렬(Rename/ALTER)을 기본 전략으로 한다.
- **DROP 허용 조건**: 해당 테이블에 **운영 가치가 있는 데이터가 없음을 코드 및 DB 직접 확인을 통해 명시적으로 검증한 경우에만** DROP을 허용한다. 확인 전 DROP은 절대 금지한다.
- **롤백**: Repository 및 DI 설정을 `git checkout`으로 복구하고 기존 테이블 스키마 복원.

---

## 5. 검증 방법 (Acceptance Criteria)

1.  **Schema Check**: `interviews`, `evaluation_scores` 테이블과 필수 컬럼이 DB에 정확히 생성되었는가?
2.  **DI Check**: 런타임 진입점에서 `PostgreSQLHistoryRepository`가 정상 주입되는가?
3.  **Persistence Check**: 인터뷰 상태 전이 명령 실행 후 PostgreSQL의 `interviews.status` 필드가 즉시 업데이트되는가?
4.  **Hydration Check**: Redis를 비운 후(`FLUSHALL`) 세션 재진입 시 PostgreSQL Authority 데이터를 기반으로 컨텍스트가 정상 복구되는가?

---

## 6. 완료 정의 (Definition of Done)

TASK-029는 아래 **4종 검증이 모두 Pass**되어야 DONE으로 판정한다.

| 검증 ID | 항목 | Pass 기준 |
|:---:|:---|:---|
| V-1 | **Schema Check** | `interviews`, `evaluation_scores` 테이블 및 필수 컬럼이 DB에 존재함 |
| V-2 | **DI Check** | 런타임에서 `PostgreSQLHistoryRepository`가 실제 주입됨 |
| V-3 | **Persistence Check** | 상태 전이 후 PostgreSQL `interviews.status` 필드가 즉시 업데이트됨 |
| V-4 | **Hydration Check** | Redis `FLUSHALL` 후 세션 재진입 시 PG Authority에서 정상 복구됨ㅤ|

4종 검증 전체 Pass + `CURRENT_STATE.md` 내 HIGH_RISK 항목 해소 확인 시 DONE.
