# TASK-027 CP0 Implementation Notes

## 1. Infrastructure
- **Redis Client**: `packages/imh_core/infra/redis.py` (Singleton, Connection Pool)
- **Config**: Add `REDIS_URL`, `REDIS_HOST`, `REDIS_PORT` to `IMHConfig`.
- **Errors**: Add `RedisConnectionError`, `LockAcquisitionError` to `IMHBaseError`.

## 2. Control Layer (Concurrency)
- **Location**: `packages/imh_service/concurrency.py`
- **Class**: `RedisConcurrencyManager` (Replaces file-based logic)
- **Mechanism**: `redis.lock` with blocking=False (Fail-Fast).
- **TTL**: `lock_timeout` (default 30s).
- **Idempotency**: Implemented as a separate check or part of the lock? 
    - Plan: `IdempotencyGuard` class in `concurrency.py` or `session_service.py` using Redis `SETNX`.

## 3. Runtime Mirror (State)
- **Location**: `packages/imh_service/infra/redis_runtime_store.py`
- **Responsibility**: Mirroring Session Scope (Step, Status, Timer).
- **Write Order**: `SessionService` orchestrates `Engine` (PG Save) -> `RedisRuntimeStore.save` (Redis Mirror).
- **TTL**: `SESSION_TIMEOUT` (e.g. 30 min).

## 4. Integration Strategy
- **SessionService**:
    - Inject `RedisRuntimeStore`.
    - Update `submit_answer`:
        1. Acquire Redis Lock.
        2. Load Context (PG).
        3. Engine Process (PG Commit via Repo).
        4. **Redis Mirror Update** (New).
        5. Return DTO.
    - Implement `hydrate_session` method.

## 5. Hydration Logic
- Triggered on App Startup or Manual Recovery.
- Reads `SessionStateRepository` (PG).
- Writes to `RedisRuntimeStore` (Overwrite).
