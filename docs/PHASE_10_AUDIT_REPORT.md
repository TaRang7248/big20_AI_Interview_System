# PHASE_10_AUDIT_REPORT
(IMH AI 면접 시스템 - Phase 10 2차 운영 안정성 심층 감사 공식 보고서)

- 감사 일자: 2026-02-19
- 감사 버전: TASK-029 완료 직후 (Baseline Alignment 완료 상태)
- 감사 기준 문서: `docs/CURRENT_STATE.md`, `docs/00_AGENT_PLAYBOOK.md`
- 감사 담당: 코딩 에이전트 (안티그래비티)
- 이모지 금지, 상태 ENUM: DONE / ACTIVE / BACKLOG / HOLD / LOCKED / DISABLED

---

## 감사 범위

| 계약 ID | 계약명 |
|:---:|:---|
| C-1 | 인터뷰 상태 전이 계약 |
| C-2 | PostgreSQL Authority 계약 |
| C-3 | 평가 엔진 기계적 산출 계약 |
| C-4 | 질문 태그 무결성 계약 |
| C-5 | Snapshot Double Lock 계약 |
| C-6 | Redis <-> PostgreSQL 동기화 계약 |

---

## 1. 계약별 분석

---

### C-1. 인터뷰 상태 전이 계약

**계약 정의**
(PLAYBOOK §3.5, CURRENT_STATE §2.2)
인터뷰 상태 전이는 오직 SessionEngine 메서드 호출을 통해서만 수행한다.
허용 순서: APPLIED -> IN_PROGRESS -> COMPLETED/INTERRUPTED -> EVALUATED.

**실제 코드 분석**

참조 파일: `packages/imh_session/engine.py`

| 메서드 | 진입 가드 | 허용 상태 | 거부 동작 |
|:---|:---|:---|:---|
| `start_session()` L143 | `if status != APPLIED` | APPLIED | `logger.warning` + `return` |
| `_complete_current_step()` L192 | `if status != IN_PROGRESS` | IN_PROGRESS | `logger.error` + `return` |
| `resume_session()` L270 | `if status != INTERRUPTED` | INTERRUPTED | `logger.warning` + `return` |
| `resume_session()` L274 | `policy.can_resume_from_interruption()` | INTERRUPTED + Policy 허용 | `logger.error` + `return` |
| `terminate_session()` L248 | 없음 (내부 전용, 진입점 가드를 통해 보호) | IN_PROGRESS 경유 후 도달 | - |

**COMPLETED 재실행 시나리오 (심층)**

시나리오: `start_session()`을 COMPLETED 상태의 세션에 호출.
- L143: `self.context.status != SessionStatus.APPLIED` 조건 참(COMPLETED != APPLIED).
- L144: `logger.warning(f"Session {self.session_id} cannot start from {self.context.status}")` 실행.
- L145: `return` 실행. 예외 발생 없음.
- 결과: 상태 변경 없음. 경고 로그 기록됨. silent return이 아니라 warning 로그가 남는 구조.

**COMPLETED -> start_session 이후 하위 메서드 도달 가부:**
`start_session()`이 L145에서 `return`하므로 `_update_status()`, `_commit_state()`에 도달하지 않는다.

**PG -> Hot Storage 전이 순서 (심층):**
`_update_status()` L282-287:
```
L283: self.context.status = new_status         # 1. 메모리 컨텍스트 갱신
L285: self.state_repo.update_status(...)        # 2. Hot Storage(Redis/Memory) 갱신
L287: self.history_repo.update_interview_status(...)  # 3. PG 갱신
```
PG 갱신 실패 시 시나리오:
- `_async_update_interview_status()` L238 `except`: `logger.exception()` + `raise`.
- `raise`가 `update_interview_status()` L222 `loop.run_until_complete()`를 통해 상위로 전파.
- `_update_status()` L287 호출부로 예외 전파.
- `_update_status()`에 `try/except` 없음. 예외가 호출 메서드(`start_session`, `terminate_session` 등)로 전파.
- 호출 메서드에도 별도 `try/except` 없음. 결과 상태: Hot Storage는 갱신 완료, PG는 미갱신. 상태 불일치 발생.
- 단, 이후 `_load_or_initialize_context()` Hydration 경로(L57)에서 PG 기준 상태로 덮어씀. 재시작 시 자기 치유.
- 치유 조건: `pg_state_repo`가 주입된 경우에만(`Optional`, `None` 허용). `pg_state_repo=None`이면 Hydration 없음.

**예외 처리 트랜잭션 여부:**
`_update_status()` 내 Hot Storage + PG 두 쓰기 연산은 단일 트랜잭션 없음. 원자성 보장 없음.

**판정: 구조적 위험 (PG 장애 시 HOT/COLD 불일치, 자기 치유 조건부)**

---

### C-2. PostgreSQL Authority 계약

**계약 정의**
(PLAYBOOK §3.1, CURRENT_STATE §2.5)
PostgreSQL이 유일한 권위 저장소. Redis에서 PG로의 Write-Back 영구 금지.
TASK-029 완료: sessions->interviews, reports->evaluation_scores RENAME.

**실제 코드 분석**

**No Write-Back 경로 확인:**
- `engine.py` 전체: Redis -> PG 방향 쓰기 코드 없음.
- Hydration (`_load_or_initialize_context()` L65-66): PG -> `self.state_repo.save_state()` (Hot Storage 방향). 역방향 없음.
- `postgresql_repo.py` `save_state()` L99: `INSERT INTO interviews ... ON CONFLICT DO UPDATE`. PG를 직접 갱신하는 경로. Redis 읽기 없음.

**save_state ON CONFLICT 구조:**
`postgresql_repo.py` L113-122:
```sql
ON CONFLICT (session_id) DO UPDATE SET
    status = EXCLUDED.status,
    job_policy_snapshot = EXCLUDED.job_policy_snapshot,
    session_config_snapshot = EXCLUDED.session_config_snapshot,
    questions_history = EXCLUDED.questions_history,
    answers_history = EXCLUDED.answers_history,
    started_at = EXCLUDED.started_at,
    completed_at = EXCLUDED.completed_at,
    evaluated_at = EXCLUDED.evaluated_at,
    updated_at = CURRENT_TIMESTAMP
```
`job_policy_snapshot`이 UPSERT 갱신 대상에 포함됨.
이후 C-5(Snapshot Double Lock)에서 별도 분석.

**update_interview_status 예외 처리:**
`postgresql_repository.py` L238-240:
```python
except Exception as e:
    logger.exception(...)
    raise
```
예외 발생 시 스택트레이스 로깅 후 상위로 `raise`. 예외 무시 없음. 단, Hot Storage와 원자적 롤백 불가.

**판정: 위반 없음 (No Write-Back 준수, PG Authority 구현 완료, 경미 위험: 비원자적 이중 갱신)**

---

### C-3. 평가 엔진 기계적 산출 계약

**계약 정의**
(CURRENT_STATE §2.1)
점수는 루브릭 기반 정량 산출. LLM 자유 평가 결과를 점수로 직접 저장 불가.

**실제 코드 분석**

참조 파일: `packages/imh_eval/rules.py`, `weights.py`, `engine.py`

**점수 범위 1-5 보장:**

| 함수 | 반환 범위 | 클램프 코드 |
|:---|:---:|:---|
| `calculate_knowledge_score()` | 1~5 | 분기별 명시적 반환, `min(score, 3)` 상한 적용 가능 |
| `calculate_problem_solving_score()` | 1~5 | 분기별 명시적 반환 |
| `calculate_communication_score()` | 3 or 5 | 분기별 명시적 반환 (최소값 3, 최대값 5) |
| `calculate_attitude_score()` L76 | 1~5 | `max(1, min(5, final_score))` 명시적 클램프 |

**가중치 합산 검증:**
`weights.py`:
- DEV: 0.4 + 0.3 + 0.2 + 0.1 = 1.0
- NON_TECH: 0.4 + 0.3 + 0.2 + 0.1 = 1.0
알 수 없는 category: `JOB_WEIGHTS.get(job_category, JOB_WEIGHTS["DEV"])` - DEV 기본값 적용.

**LLM 자유 평가 전환 여부:**
`eval/engine.py` L31: `rag_keywords_found: List[str]` - LLM 결과는 키워드 목록으로만 수신.
`calculate_knowledge_score()`는 `len(keyword_match)` 정수만 입력받음.
LLM 생성 텍스트가 점수로 직접 저장되는 경로 없음.

**communication_score 단일화 위험:**
`calculate_communication_score(star_structure=False)` -> 고정 반환 3.
STAR 미감지 시 답변 내용, 길이, 어휘와 무관하게 3점 고정. 설계 기록(`DECISIONS.md` 등)에 명시된 의도적 단순화인지 확인 불가.
단, 계약 위반은 아님. 루브릭 기반 산출 계약 준수.

**판정: 위반 없음**

---

### C-4. 질문 태그 무결성 계약

**계약 정의**
(PLAYBOOK Appendix A, `_refs/질문태그설계.md` 기준)
tag_code는 문서에 정의된 값만 허용. 임의 문자열 저장 금지.

**실제 코드 분석**

**현재 사용 중인 tag_code 값 (eval/engine.py 하드코딩):**
- L47: `"capability.knowledge"`
- L59: `"capability.problem_solving"`
- L71: `"capability.communication"`
- L103: `"capability.attitude"`

**DB 레벨 제약 확인:**
`init_db.py` L169-177: `evaluation_scores` 테이블 DDL:
```sql
CREATE TABLE IF NOT EXISTS evaluation_scores (
    report_id VARCHAR(255) PRIMARY KEY,
    session_id VARCHAR(255) REFERENCES interviews(session_id),
    report_data JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```
tag_code 전용 컬럼 없음. report_data JSONB 안에 tag_code가 포함됨. JSONB 내부 값에 ENUM/FK/CHECK 제약 없음.

**결론:**
tag_code는 현재 eval/engine.py 내 하드코딩으로만 보호됨.
DB 레벨 ENUM, FK, CHECK CONSTRAINT 없음.
현재 외부 API를 통해 tag_code를 직접 지정하는 입력 경로 없음.
단, JSONB 컬럼 내 값은 DB 레벨에서 검증 불가.

**판정: 구조적 위험 (DB 레벨 제약 미존재, 현재 위반 경로는 없으나 향후 확장 시 위험)**

---

### C-5. Snapshot Double Lock 계약

**계약 정의**
(PLAYBOOK §3.4, CURRENT_STATE §2.2)
공고 발행 후 정책 동결(Freeze). 세션 시작 시 스냅샷 생성. 생성된 스냅샷은 수정 불가.

**실제 코드 분석**

**job_policy_snapshot ON CONFLICT 갱신 문제:**
`postgresql_repo.py` L115:
```sql
ON CONFLICT (session_id) DO UPDATE SET
    job_policy_snapshot = EXCLUDED.job_policy_snapshot,
```
`save_state()` 호출 시 `job_policy_snapshot`이 갱신 대상에 포함됨.

**갱신 발생 조건:**
`engine.py` `_commit_state()` L291: `self.state_repo.save_state()` 호출 -> `postgresql_repo.save_state()` 호출.
`_commit_state()`는 `start_session()` L156, `_complete_current_step()` L234, `resume_session()` L280에서 호출.

**실질 위험 평가:**
`context.job_policy_snapshot`은 세션 생성 시 `config.job_policy_snapshot`에서 1회 복사됨.
이후 Engine 내에서 `job_policy_snapshot`을 변경하는 코드 없음.
`save_state()` UPSERT 시 동일한 값으로 덮어씀.

단, UPSERT SQL이 `job_policy_snapshot`을 갱신 대상으로 열어두는 한, 향후 `context.job_policy_snapshot` 수정 코드가 추가되면 DB에도 반영됨. DB 레벨 Immutable 보장 없음.

**스냅샷 저장 시점 확인:**
`postgresql_repo.py` `save_state()`: UPSERT 시 스냅샷 포함.
세션 생성 흐름: `SessionService.create_session()` -> `Engine.__init__()` -> `_load_or_initialize_context()` -> `start_session()` -> `_commit_state()` -> `save_state()`.
최초 저장 시점은 `start_session()` 이후 `_commit_state()` 실행 시.

**판정: 구조적 위험 (DB 레벨 Immutable 보장 없음, UPSERT가 snapshot 갱신 대상 포함. 현재 코드에서 실제 변경 경로는 없으나 SQL 구조가 열려 있음)**

---

### C-6. Redis <-> PostgreSQL 동기화 계약

**계약 정의**
(PLAYBOOK §3.2, §3.3, CURRENT_STATE §2.6)
Redis는 런타임 제어/캐시 전용. PG 저장 성공 후 Redis 반영. PG가 권위. Redis Miss 시 PG Hydration.

**실제 코드 분석**

**저장 순서:**
`_update_status()`:
1. L283: 메모리 컨텍스트 갱신
2. L285: `state_repo.update_status()` (Hot Storage)
3. L287: `history_repo.update_interview_status()` (PG)

Hot Storage 갱신이 PG 갱신보다 선행함.

**Redis 장애 시 시나리오:**
Redis가 완전 불응 상태일 때 `state_repo.update_status()` L285 예외 발생.
예외가 `_update_status()` L285 호출부로 전파.
L287 `history_repo.update_interview_status()` (PG 갱신)에 도달하지 않음.
결과: PG 미갱신. 양쪽 모두 갱신 실패. 최후 기록 상태 유지.
이 경우 Authority 계약 위반 발생하지 않음(PG와 Hot Storage 모두 이전 상태 유지).

**PG 장애 + Hot Storage 정상 시나리오:**
L285 성공, L287 실패.
Hot Storage = 신규 상태, PG = 구 상태. 불일치.
`pg_state_repo` 주입 시 재시작 후 Hydration으로 PG 기준 복구.
단: `pg_state_repo=None`이면 Hydration 미작동. Hot Storage 기반으로 지속. 이 상태가 롤백까지 지속되면 Authority 계약 위반.

**chat_history JSONB 구조 (심층):**
`postgresql_repo.py` L131: `json.dumps(context_dict.get('question_history', []))` -> `questions_history` JSONB.
`L132`: `json.dumps(context_dict.get('answers_history', []))` -> `answers_history` JSONB.
`interviews` 테이블에 `questions_history`, `answers_history` 컬럼 각각 존재.
PLAYBOOK Appendix A 규정: `chat_history: {role, content, timestamp, question_id?}` 배열.
실제 저장 구조: SessionContext.model_dump() 결과, 필드명이 question_history(복수형 아님)로 저장.
컬럼명: questions_history. context_dict key: question_history. 불일치.

`context_dict.get('question_history', [])` 조회 시: Pydantic model_dump()가 `question_history` 키 반환하면 정상.
`SessionContext` DTO 정의에서 필드명이 `question_history`이면 일치. 별도 확인 필요.

JSONB 인덱스: `init_db.py`에 `questions_history`, `answers_history` 컬럼에 대한 인덱스 없음.
존재하는 인덱스: `idx_interviews_job_id`, `idx_interviews_status`, `idx_interviews_user_id`.
부분 조회(jsonb 경로 조회): 현재 코드에서 JSONB 내부 경로 SELECT 없음. 전체 row 조회 후 Python에서 파싱.
Row size 증가: 세션이 길어질수록 `questions_history`, `answers_history` JSONB row 크기 증가. PostgreSQL TOAST 자동 압축 적용되나 조회 시 전체 역직렬화 발생.

**Live Hydration 검증 결과:**
2026-02-19 16:15:18: `scripts/verify_live_task_029.py` - Hydration PASS. Redis FLUSHALL 후 PG Authority에서 status=COMPLETED 복구 확인.

**판정: 구조적 위험 (저장 순서 Hot->PG, PG 장애 + pg_state_repo=None 조건에서 Authority 위반 가능. chat_history 인덱스 없음)**

---

## 2. 위험 등급 분류

| 위험 ID | 계약 | 내용 | 등급 |
|:---:|:---:|:---|:---:|
| R-1 | C-1, C-6 | `_update_status()` 비원자적 이중 갱신 (Hot Storage -> PG 순서). PG 장애 시 Hot/Cold 불일치. `pg_state_repo=None`이면 Hydration 미작동으로 Authority 위반 지속 가능. | MEDIUM |
| R-2 | C-4 | `tag_code` DB 레벨 ENUM/CHECK 제약 없음. 현재 삽입 경로는 eval/engine.py 하드코딩으로 제한되나 DB 레벨 보장 없음. | LOW |
| R-3 | C-5 | `save_state()` UPSERT SQL이 `job_policy_snapshot`을 갱신 대상으로 열어둠. DB 레벨 Immutable 보장 없음. 현재 코드 내 실제 변경 경로 없음. | LOW |
| R-4 | C-6 | `questions_history`, `answers_history` JSONB 컬럼 인덱스 없음. 세션 데이터 증가 시 전체 row 조회 방식. | LOW |
| R-5 | C-3 | `calculate_communication_score(star_structure=False)` 고정 반환 3. STAR 미감지 시 답변 품질 무관 일률 3점. 루브릭 계약 위반은 아니나 평가 해상도 제한. | LOW |

---

## 3. 계약별 판정 표

| 계약 | 판정 | 위험 ID |
|:---|:---:|:---:|
| C-1 인터뷰 상태 전이 | 구조적 위험 | R-1 |
| C-2 PostgreSQL Authority | 위반 없음 (경미 위험 포함) | R-1 |
| C-3 평가 엔진 기계적 산출 | 위반 없음 | R-5 |
| C-4 질문 태그 무결성 | 구조적 위험 | R-2 |
| C-5 Snapshot Double Lock | 구조적 위험 | R-3 |
| C-6 Redis <-> PG 동기화 | 구조적 위험 | R-1, R-4 |

---

## 4. 최종 운영 판정

### 내부 테스트 한정 가능

**판정 근거:**

1. CRITICAL, HIGH 등급 위험 없음. 전체 위험 MEDIUM 1건, LOW 4건.
2. MEDIUM 위험(R-1): PG 장애 시 상태 불일치 가능. `pg_state_repo` 주입 완료 시 Hydration 자기 치유 동작. Live 검증 통과(2026-02-19). 단, `pg_state_repo=None` 구성 시 Authority 위반 방치 가능.
3. PostgreSQL Authority, No Write-Back, State Transition Guard 3개 핵심 계약은 현재 코드 내 실제 위반 경로 없음 확인.
4. 외부 사용자가 직접 평가 결과, 태그, 스냅샷을 조작하는 API 경로 없음 확인.
5. 세션 데이터 규모가 제한적(내부 테스트 수준)인 경우 JSONB 인덱스 미존재는 허용 범위.

**외부 운영 불가 조건:**
- R-1: PG 장애 복구 절차(pg_state_repo 주입 보장) 운영 문서화 전.
- R-2: tag_code DB 레벨 제약 없는 상태에서 외부 API 확장 시.
- R-3: UPSERT에서 job_policy_snapshot 갱신 차단 전.

---

*본 보고서는 2026-02-19 기준 TASK-029 완료 상태의 코드를 감사한 결과이다.*
*코드 변경 발생 시 본 보고서의 유효성은 소멸된다.*
