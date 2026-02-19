
# CP2 Dynamic TTL Audit Report

## 1. PostgreSQL Authority
- **결과**: 준수
- **근거**:
  - `packages/imh_service/ttl_resolver.py`의 `PostgresTTLResolver`는 `SessionStateRepository`를 주입받아 사용합니다. (`state_repo.find_by_job_id(job_id)`)
  - Active Candidate 수는 Redis/Cache가 아닌, Authority(Session State Repo) 조회를 통해 산출됩니다. (Line 48-49)
  - `CachedQuestionGenerator`는 DB를 직접 조회하지 않고 `TTLContextResolver` 인터페이스만 호출하므로 Service Layer의 DB 직접 의존을 방지했습니다.

## 2. Layered Architecture
- **결과**: 준수
- **근거**:
  - `TTLContextResolver`는 추상 클래스(Interface)로 정의되어 Service Layer에 위치합니다. (Line 18)
  - `PostgresTTLResolver`는 이 인터페이스의 구현체로서 Infrastructure(Repository)에 대한 세부 사항을 캡슐화합니다.
  - `CachedQuestionGenerator` (Service/Decorator)는 `TTLContextResolver` 인터페이스에만 의존하며, 구체적인 구현(Postgres/Redis)을 알지 못합니다. (Line 26, 72)
  - 이는 의존성 역전 원칙(DIP)을 따르는 올바른 계층 구조입니다.

## 3. Fallback Safety
- **결과**: 안전
- **근거**:
  - `PostgresTTLResolver.resolve` 메소드는 `try...except` 블록으로 감싸져 있습니다. (Line 46-53)
  - Repository 조회 중 예외 발생 시 `logger.warning`을 기록하고 `active_count=0` (기본값)을 반환하여 안전하게 동작합니다.
  - `CachedQuestionGenerator.generate_question` 역시 Resolver 호출 실패를 `try...except`로 방어하며, 실패 시 `ttl_seconds = 86400` (24h Safety Default)를 사용합니다. (Line 79-80)

## 4. TTL Priority Logic
- **결과**: 명확
- **근거**:
  - `RedisRAGRepository.calculate_ttl` (Line 93-103) 구현:
    1.  `if is_debug: return TTL_DEBUG_SECONDS` (1h) - **최우선**
    2.  `if active_candidates > 100 or model_cost_high: return TTL_HIGH_TRAFFIC_SECONDS` (48h)
    3.  `return TTL_DEFAULT_SECONDS` (24h)
  - 이 로직은 Debug 모드가 트래픽보다 우선하도록 설계되어 있어 개발/테스트 시 혼선을 방지합니다.

## 5. Test Adequacy
- **결과**: 적절
- **근거**:
  - `scripts/verify_cp2.py`는 `unittest.mock`을 사용하여 외부 의존성(Redis, Real Generator, TTL Resolver)을 철저히 격리했습니다. (Line 20-38)
  - `test_dynamic_ttl_high_traffic`, `test_dynamic_ttl_debug_mode` 등을 통해 각 시나리오별 TTL 값이 올바르게 계산되어 `repo.save_async` (또는 `calculate_ttl`)에 전달되는지 검증합니다.
  - DB 연결 없이 로직 검증이 가능하므로 Regression 위험이 없습니다.

---

## 최종 판정

- **LOCK 승인 가능**
- 위반 사항 없음. 모든 계약 조건(Authority, Layering, Safety, Priority)을 충족함.
