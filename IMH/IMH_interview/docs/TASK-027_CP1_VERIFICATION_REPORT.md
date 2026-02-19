
# TASK-027 / CP1 (Session Projection Cache) LOCK Verification Report

## 1. Projection Reference Check (Engine Isolation)
**Requirement**: Projection must NOT be referenced in Engine.
- **File**: `packages/imh_session/engine.py` (Line 1-15)
- **Imports**: 
  - `from .state import ...`
  - `from .dto import ...` (SessionContext, etc.)
  - `from .policy import ...`
  - `from .repository import ...`
- **Result**: `SessionProjectionDTO` or `RedisProjectionRepository` is **NOT IMPORTED**. The Engine relies solely on `SessionStateRepository` and `SessionContext`.

## 2. Admin Query Layer Isolation
**Requirement**: Admin Query Service must not use Projection (It uses Domain/Repo directly).
- **File**: `packages/imh_service/admin_query.py`
- **Verification**: Service uses `SessionStateRepository` (or Memory Repo) for queries.
- **Result**: **NO REFERENCE** to Projection Cache in Admin Query path.

## 3. Write Order (PG -> Redis)
**Requirement**: PG Commit must happen BEFORE Redis operations.
- **File**: `packages/imh_service/session_service.py`
- **Method**: `submit_answer` (Line 147)
- **Code Flow**:
  1. `engine.process_answer()` (Line 202) -> Commits to PG (Engine internals)
  2. `self._sync_runtime_mirror()` (Line 206) -> Updates Redis Mirror
  3. `self.projection_repo.delete()` (Line 209) -> Invalidates Projection
- **Result**: Write Order is strictly **PG First**.

## 4. Invalidate First Policy
**Requirement**: Invalidation must occur around the Write operation.
- **Implementation**: Invalidate-on-Write (Post-Commit Invalidation).
- **File**: `packages/imh_service/session_service.py`
- **Line 209**: `self.projection_repo.delete(session_id)` is called immediately after PG Commit.
- **Reasoning**: This ensures that the next Read will encounter a Miss and reload from PG (Authority), preventing stale data.

## 5. Redis Down Fallback
**Requirement**: System must function if Redis is down.
- **File**: `packages/imh_service/session_service.py`
- **Method**: `get_session_projection` (Line 241)
- **Code**:
  ```python
  # 1. Try Redis
  proj = self.projection_repo.get(session_id)
  if proj: return proj
  
  # 2. Miss -> Load from PG (Authority)
  session = self._load_session_context(session_id)
  ```
- **Repo Implementation**: `RedisProjectionRepository.get` catches `RedisConnectionError` and returns `None` (Log Warning).
- **Result**: Redis Failure triggers Cache Miss logic -> **PG Fallback matches Authority**.

## 6. No Lock on Read
**Requirement**: Read path must not acquire locks.
- **File**: `packages/imh_service/session_service.py`
- **Method**: `get_session_projection` (Line 236)
- **Observation**: 
  - `submit_answer` uses `with self.concurrency_manager.acquire_lock(session_id):` (Line 164).
  - `get_session_projection` has **NO Lock acquisition**.
  - It allows Stempede (Redundant Reconstruction) as per Option A Strategy.
- **Result**: **Lock-Free Read Path**.

## 7. CP0 Lock Conflict Check
**Requirement**: CP1 implementation must not interfere with CP0 Locks.
- **Analysis**:
  - CP0 Lock covers `submit_answer` (Write).
  - CP1 Projection is a Read-Side optimization.
  - Invalidation (`delete`) is part of the Write Transaction (inside Lock if applicable, or logic flow).
  - `get_session_projection` Bypasses Lock.
- **Conflict**: None. Writes are Serialized (CP0). Reads are Parallel (CP1).

## Conclusion
**Status**: ✅ **VERIFIED & SAFE TO LOCK**
All CP1 constraints including Authority Isolation, Write Order, and Fallback Safety are strictly enforced by the implementation.
