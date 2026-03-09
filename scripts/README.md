# Scripts Directory

This directory contains utility scripts for verification, testing, and migration.

## Verification Scripts (KEEP)
Run these scripts to verify system integrity and contract compliance.

- `verify_task_*.py`: Verify specific task requirements and contracts.
- `verify_integration_safety.py`: Verify integration safety (Checkpoint 1.5).
- `verify_dual_write.py`: Verify Dual Write integrity (Stage 3).
- `verify_loopback.py`: Verify Write -> Read integrity (Stage 3).
- `verify_restart_replay.py`: Verify persistence and hydration (Stage 3).
- `verify_rollback_safety.py`: Verify rollback capability (Stage 3).
- `verify_full_read_replay.py`: Deterministic stress test (Checkpoint 4.3).

## Migration Scripts (Restricted Usage)

> [!WARNING]
> These scripts are for migration/recovery only. DO NOT run in production without strict validation.

- `migrate_to_postgresql.py`: **Deprecated**. Used for initial migration. Re-use only for recovering test environments.
- `verify_migration.py`: **Operation Tool**. Use for verifying DB consistency after reconstruction.
- `reset_migration.py`: **TEST ENV ONLY**. Deletes all data. Requires `ENV=TEST`.

## Infrastructure & Setup
- `init_db.py`: Initialize database schema.
- `check_logging.py`: Infrastructure verification.
