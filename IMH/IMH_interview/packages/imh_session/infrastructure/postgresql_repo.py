"""
PostgreSQL implementation of SessionStateRepository for TASK-026.

This module provides PostgreSQL-based persistence for Session state,
replacing the in-memory MemorySessionRepository while maintaining the same interface.

TASK-026 Contract Compliance:
- Maintains existing SessionStateRepository interface
- Does NOT modify Engine/Service/API boundaries  
- Does NOT contain Freeze/Snapshot/State Contract logic (storage only)
- Preserves DTO/Mapper separation
"""

import asyncio
import json
import logging
from typing import List, Optional
from datetime import datetime

import asyncpg  # type: ignore

from packages.imh_session.dto import SessionContext, SessionQuestion
from packages.imh_session.repository import SessionStateRepository
from packages.imh_session.state import SessionStatus

logger = logging.getLogger("imh_session.postgresql")


class PostgreSQLSessionRepository(SessionStateRepository):
    """
    PostgreSQL-based implementation of SessionStateRepository.
    
    Stores session state in the 'sessions' table with JSONB format for snapshots.
    Maintains compatibility with MemorySessionRepository interface.
    """
    
    def __init__(self, conn_config: dict):
        """
        Initialize with PostgreSQL connection configuration.
        
        Args:
            conn_config: Dict with keys: host, port, user, password, database
        """
        self.conn_config = conn_config
    
    def _get_event_loop(self):
        """Get or create event loop for async operations"""
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
    
    async def _get_connection(self):
        """Create database connection"""
        conn = await asyncpg.connect(**self.conn_config)
        
        # Configure JSONB codec to handle Python dict automatically
        await conn.set_type_codec(
            'jsonb',
            encoder=json.dumps,
            decoder=json.loads,
            schema='pg_catalog'
        )
        return conn
    
    def save_state(self, session_id: str, context: SessionContext) -> None:
        """
        Save or update session state to PostgreSQL.
        
        Contract: Stores complete SessionContext (including snapshots).
        Does NOT modify state or apply any business logic.
        
        Args:
            session_id: Session identifier
            context: SessionContext DTO containing all session data
        """
        loop = self._get_event_loop()
        loop.run_until_complete(self._async_save_state(session_id, context))
    
    async def _async_save_state(self, session_id: str, context: SessionContext) -> None:
        """Async implementation of save_state"""
        conn = await self._get_connection()
        try:
            # Convert context to dict for JSON storage
            if hasattr(context, 'model_dump'):
                context_dict = context.model_dump(mode='json')
            else:
                context_dict = context.dict() # V1 support

            # Extract fields for structured columns
            status_value = context.status.value if hasattr(context.status, 'value') else str(context.status)
            mode_value = getattr(context, 'mode', 'ACTUAL')
            if hasattr(mode_value, 'value'):
                mode_value = mode_value.value
            
            # L2 Guard: Use fetchrow to inspect preserved state (RETURNING)
            # Upsert session
            row = await conn.fetchrow(
                """
                INSERT INTO interviews (
                    session_id, user_id, job_id, status, mode,
                    job_policy_snapshot, session_config_snapshot,
                    questions_history, answers_history,
                    applied_at, started_at, completed_at, evaluated_at,
                    created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4::session_status, $5::interview_mode,
                    $6, $7, $8, $9,
                    $10, $11, $12, $13,
                    $14, $15
                )
                ON CONFLICT (session_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    -- L2/L3 Guard: Snapshots are EXCLUDED from update to enforce immutability
                    -- job_policy_snapshot = EXCLUDED.job_policy_snapshot,
                    -- session_config_snapshot = EXCLUDED.session_config_snapshot,
                    questions_history = EXCLUDED.questions_history,
                    answers_history = EXCLUDED.answers_history,
                    started_at = EXCLUDED.started_at,
                    completed_at = EXCLUDED.completed_at,
                    evaluated_at = EXCLUDED.evaluated_at,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING job_policy_snapshot, session_config_snapshot
                """,
                session_id,
                getattr(context, 'user_id', None),
                getattr(context, 'job_id', None),
                status_value,
                mode_value,
                json.dumps(getattr(context, 'job_policy_snapshot', None)),
                json.dumps(getattr(context, 'session_config_snapshot', None)),
                json.dumps(context_dict.get('question_history', [])),
                json.dumps(context_dict.get('answers_history', [])),
                getattr(context, 'applied_at', None),
                getattr(context, 'started_at', None),
                getattr(context, 'completed_at', None),
                getattr(context, 'evaluated_at', None),
                getattr(context, 'created_at', datetime.now()),
                datetime.now()
            )
            
            logger.info(f"Session state saved: {session_id}")

            # L2 Guard Verification: Check for Silent Preservation
            if row:
                input_policy = getattr(context, 'job_policy_snapshot', None)
                input_config = getattr(context, 'session_config_snapshot', None)
                
                # Database returns dicts (via jsonb codec) OR strings (if codec inactive/json type)
                db_policy = row['job_policy_snapshot']
                if isinstance(db_policy, str):
                    db_policy = json.loads(db_policy)
                    
                db_config = row['session_config_snapshot']
                if isinstance(db_config, str):
                    db_config = json.loads(db_config)
                
                # Check for unauthorized mutation attempt (Attempt Basis)
                # Note: We compare the input object vs the preserved DB object.
                if input_policy != db_policy or input_config != db_config:
                    logger.error(
                        f"L2 GUARD: Snapshot mutation attempt detected (Silent Preservation). "
                        f"Session: {session_id}. "
                        f"Input differs from Storage used. Update ignored."
                    )
            
        except Exception as e:
            logger.exception(f"Failed to save session state {session_id}: {e}")
            raise
        finally:
            await conn.close()
    
    def get_state(self, session_id: str) -> Optional[SessionContext]:
        """
        Retrieve session state from PostgreSQL.
        
        Contract: Returns SessionContext if exists, None otherwise.
        Does NOT apply any filtering or business logic.
        
        Args:
            session_id: Session identifier
            
        Returns:
            SessionContext if found, None otherwise
        """
        loop = self._get_event_loop()
        return loop.run_until_complete(self._async_get_state(session_id))
    
    async def _async_get_state(self, session_id: str) -> Optional[SessionContext]:
        """Async implementation of get_state"""
        conn = await self._get_connection()
        try:
            row = await conn.fetchrow(
                """
                SELECT session_id, user_id, job_id, status, mode,
                       job_policy_snapshot, session_config_snapshot,
                       questions_history, answers_history,
                       applied_at, started_at, completed_at, evaluated_at
                FROM interviews
                WHERE session_id = $1
                """,
                session_id
            )
            
            if not row:
                return None
            
            # Reconstruct SessionContext
            # Note: This is a minimal reconstruction. In production, you'd need
            # to properly reconstruct all SessionContext fields based on its actual structure.
            # Derived fields (calculated from history since not stored in DB columns)
            questions = json.loads(row['questions_history']) if row['questions_history'] else []
            answers = json.loads(row['answers_history']) if row['answers_history'] else []
            
            # Derived Runtime State Logic
            q_len = len(questions)
            status_enum = SessionStatus(row['status'])
            completed_count = len(answers)
            if not answers and q_len > 0:
                 if status_enum == SessionStatus.COMPLETED:
                      completed_count = q_len
                 else:
                      completed_count = q_len - 1

            context_data = {
                'session_id': row['session_id'],
                'user_id': row['user_id'],
                'job_id': row['job_id'],
                'status': SessionStatus(row['status']), # Convert string back to enum
                'mode': row['mode'],
                'job_policy_snapshot': json.loads(row['job_policy_snapshot']) if row['job_policy_snapshot'] else None,
                'session_config_snapshot': json.loads(row['session_config_snapshot']) if row['session_config_snapshot'] else None,
                'applied_at': row['applied_at'],
                'started_at': row['started_at'],
                'completed_at': row['completed_at'],
                'evaluated_at': row['evaluated_at'],
                # Derived Runtime State
                'current_step': q_len,
                'completed_questions_count': completed_count,
            }
            
            # Helper to restore SessionQuestion objects
            # context_data['question_history'] = [SessionQuestion(**q) for q in questions] # Pydantic v2 might handle list of dicts if field type is List[SessionQuestion]
            # But let's be explicit if needed. The DTO defines it as 'list' (default factory), 
            # but usually it stores objects.
            # ShadowReader compares dicts. If MemoryRepo stores objects, we should restore objects.
            # However, SessionContext definition in DTO says: question_history: List[SessionQuestion] (my recent fix made this specific)
            # So passing dicts might fail if not parsed. 
            # But SessionContext(**data) parses sub-models.
            context_data['question_history'] = questions
            context_data['answers_history'] = answers
            
            ctx = SessionContext(**context_data)
            
            # Restore current_question if active
            if questions and len(answers) < len(questions):
                # Last question is not answered yet
                # We assume the last question in history is the current one
                last_q_data = questions[-1]
                ctx.current_question = SessionQuestion(**last_q_data)
                
            return ctx
            
        except Exception as e:
            logger.exception(f"Failed to retrieve session {session_id}: {e}")
            return None
        finally:
            await conn.close()
    
    def update_status(self, session_id: str, status: SessionStatus) -> None:
        """
        Update session status.
        
        Contract: Updates only the status field.
        Does NOT validate state transitions (that's Engine's responsibility).
        
        Args:
            session_id: Session identifier
            status: New SessionStatus value
        """
        loop = self._get_event_loop()
        loop.run_until_complete(self._async_update_status(session_id, status))
    
    async def _async_update_status(self, session_id: str, status: SessionStatus) -> None:
        """Async implementation of update_status"""
        conn = await self._get_connection()
        try:
            status_value = status.value if hasattr(status, 'value') else str(status)
            
            await conn.execute(
                """
                UPDATE interviews
                SET status = $1::session_status, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = $2
                """,
                status_value,
                session_id
            )
            
            logger.info(f"Session status updated: {session_id} -> {status_value}")
            
        except Exception as e:
            logger.exception(f"Failed to update session status {session_id}: {e}")
            raise
        finally:
            await conn.close()
    
    def find_by_job_id(self, job_id: str) -> List[SessionContext]:
        """
        Find all sessions for a given job.
        
        Contract: Returns list of SessionContext for the job.
        Does NOT filter by status (returns all).
        
        Args:
            job_id: Job identifier
            
        Returns:
            List of SessionContext
        """
        loop = self._get_event_loop()
        return loop.run_until_complete(self._async_find_by_job_id(job_id))
    
    async def _async_find_by_job_id(self, job_id: str) -> List[SessionContext]:
        """Async implementation of find_by_job_id"""
        conn = await self._get_connection()
        try:
            rows = await conn.fetch(
                """
                SELECT session_id, user_id, job_id, status, mode,
                       job_policy_snapshot, session_config_snapshot,
                       questions_history, answers_history,
                       applied_at, started_at, completed_at, evaluated_at
                FROM interviews
                WHERE job_id = $1
                ORDER BY created_at DESC
                """,
                job_id
            )
            
            results = []
            for row in rows:
                try:
                    context_data = {
                        'session_id': row['session_id'],
                        'user_id': row['user_id'],
                        'job_id': row['job_id'],
                        'status': SessionStatus(row['status']),
                        'mode': row['mode'],
                        'job_policy_snapshot': json.loads(row['job_policy_snapshot']) if row['job_policy_snapshot'] else None,
                        'session_config_snapshot': json.loads(row['session_config_snapshot']) if row['session_config_snapshot'] else None,
                        'question_history': json.loads(row['questions_history']) if row['questions_history'] else [],
                        'answers_history': json.loads(row['answers_history']) if row['answers_history'] else [],
                        'applied_at': row['applied_at'],
                        'started_at': row['started_at'],
                        'completed_at': row['completed_at'],
                        'evaluated_at': row['evaluated_at'],
                    }
                    results.append(SessionContext(**context_data))
                except Exception as e:
                    logger.warning(f"Failed to parse session {row['session_id']}: {e}")
                    continue
            
            return results
            
        finally:
            await conn.close()
