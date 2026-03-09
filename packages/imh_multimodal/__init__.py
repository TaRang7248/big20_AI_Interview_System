"""
TASK-M: imh_multimodal package
Multimodal Integration (Real-time MVP) for IMH AI Interview system.

Scope:
  - multimodal_observations table & Redis Streams (Sprint 1)
  - CPU Workers: Vision, Emotion, Audio (Sprint 2)
  - GPU Worker: STT + GPU Mutex (Sprint 3)
  - E2E Verification & Fast Gate (Sprint 4)

Authority contracts (immutable):
  - PostgreSQL is the single authority store.
  - Redis is runtime/IPC/Projection Cache. No Write-Back.
  - Workers MUST NOT modify core session state or snapshots.
"""
