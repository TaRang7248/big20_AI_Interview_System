# TASK-027 / CP4 Prompt Composition Cache Audit Report

## 1. Authority 감사
- **Status**: **SAFE**
- **Findings**:
  - `CachedPromptComposer`는 `real_composer`를 래핑(Wrapping)하며, Cache Miss 시 반드시 `real_composer`를 통해 프롬프트를 생성한다.
  - Redis는 조회 최적화(Read Optimization) 용도로만 사용되며, 비즈니스 로직의 의사결정(Decision Making)에 관여하지 않는다.
  - Redis 데이터가 없어도(None 반환 시) 시스템은 정상 동작(Fail-Open)한다.
  - Evidence Data 생성에 Cache가 아닌 원본 Context를 사용함을 확인했다.

## 2. Snapshot Immutable 감사
- **Status**: **SAFE**
- **Findings**:
  - `compose_prompt` 메서드는 `context` 딕셔너리를 읽기(Read-Only)만 수행하며, 수정하지 않는다.
  - Cache Key 생성 시 `snapshot_id`와 `job_policy_snapshot_hash`를 필수 요소로 포함하여, Snapshot 변경 시 Key가 변경됨을 보장한다.
  - `LOGICAL_PROMPT_VERSION`을 포함하여, 로직 변경 시에도 Key 충돌을 방지한다.

## 3. Write Order & No Write-Back 감사
- **Status**: **SAFE**
- **Findings**:
  - Prompt 생성(Read) 시점에 캐시 저장이 발생하므로, PG Write Transaction과 직접적인 순서 의존성이 없다. (Read-Through Pattern)
  - Redis에 저장된 데이터가 PostgreSQL로 역류(Write-Back)하는 코드는 존재하지 않는다.
  - `save_prompt` 내의 예외는 catch되어 로그만 남기므로(`warning`), Cache Write 실패가 메인 트랜잭션이나 로직을 중단시키지 않는다.

## 4. Deterministic 보장 감사
- **Status**: **SAFE**
- **Findings**:
  - `LOGICAL_PROMPT_VERSION` ("v1.0.0") 상수가 `constants.py`에 단일 정의되어 있다.
  - 입력 데이터(`input_data`) 해싱 시 `json.dumps(..., sort_keys=True)`를 사용하여 필드 순서와 무관하게 동일한 해시를 보장한다.
  - 동일 입력에 대해 결정론적(Deterministic)으로 Key가 생성된다.

## 5. Cache Key 완전성 감사
- **Status**: **Pass**
- **Components Checked**:
  - `prompt` (Prefix)
  - `LOGICAL_PROMPT_VERSION` (Version)
  - `snapshot_id` (Session Identity)
  - `persona_id` (Persona)
  - `interview_mode` (Mode)
  - `job_policy_snapshot_hash` (Policy Identity)
  - `model_id` (Model)
  - `input_hash` (Variable Inputs)
- **Conclusion**: 모든 필수 논리적 요소가 포함되어 있다.

## 6. 메모리 및 보안 감사
- **Status**: **CONDITIONAL SAFE** (Minor Risk Identified)
- **Findings**:
  - **Logging**: `Prompt Cache HIT: {key}` 형태로 Key만 로깅하며, Prompt 원문(Content)은 로그에 남기지 않는다. (Pass)
  - **TTL Jitter**: `repository.save_prompt`에서 `randint(0, 300)`을 통해 Jitter가 적용되어 있다. (Pass)
  - **Fail-Open**: `get_prompt` 실패 시 `None`을 반환하여 원본 로직으로 자연스럽게 넘어간다. (Pass)
  - **Max Size Limit**: 저장 전 Prompt 크기를 검사하여 일정 크기 이상 시 캐싱을 거부하는 로직이 **구현되어 있지 않다**. (Risk)
  - **Single-flight**: 동시 요청에 대한 Request Coalescing 처리가 없으며, TTL Jitter에만 의존한다. (Risk)

## 7. 관측 가능성 확인
- **Status**: **SAFE**
- **Findings**:
  - Cache Hit/Miss에 대한 INFO 로그가 존재한다.
  - Redis 연결 및 명령 실패 시 WARNING 로그가 남는다.
  - Latency 정보가 캐시 페이로드(`latency` 필드)에 저장되지만, 외부 메트릭으로 노출되지는 않는다. (현재 단계 허용 범위)

---

## 8. 최종 종합 보고 (Overall Verdict)

### Overall Verdict:
**CONDITIONAL SAFE**

### Critical Risk:
- 없음.

### Minor Risk:
1.  **Max Size Limit 미구현**: 초대형 프롬프트가 생성될 경우 Redis 메모리 사용량에 영향을 줄 수 있음. (Plan 내 "메모리 보호 정책" 항목 미충족)
2.  **Single-flight 미구현**: 고트래픽 상황에서 Cache Miss 발생 시 순간적인 경합(Stampede) 완화 장치가 TTL Jitter로만 한정됨.

### 계약 위반 여부:
**없음**
- Authority, Immutable, Write Order 등 시스템 무결성과 관련된 핵심 계약은 모두 준수됨.
- Minor Risk는 "운영 안정성 보강" 항목의 누락이며, 정합성 위반은 아님.
