from typing import Any, List
from datetime import datetime
from packages.imh_dto.session import SessionResponseDTO, QuestionDTO, SessionListDTO


class SessionMapper:
    """
    Explicit Mapper to convert Domain Entities (Session, Question) to DTOs.
    Ensures no domain objects leak into the API layer.
    """

    @staticmethod
    def to_dto(session: Any) -> SessionResponseDTO:
        # Calculate progress
        # Check if session is Context or Entity
        # SessionContext has 'completed_questions_count'
        # SessionEntity might have 'question_queue' etc.
        
        # Defensive property access
        total = 0
        if hasattr(session, 'config') and hasattr(session.config, 'total_question_limit'):
            total = session.config.total_question_limit
        elif hasattr(session, 'question_queue'):
            total = len(session.question_queue)

             
        current_idx = 0
        if hasattr(session, 'completed_questions_count'):
            current_idx = session.completed_questions_count
        elif hasattr(session, 'current_question_index'):
            current_idx = session.current_question_index
            
        progress = (current_idx / total * 100) if total > 0 else 0.0

        # Map current question if exists
        current_q_dto = None
        # SessionContext doesn't have current_question object directly usually, 
        # unless enriched. 
        # For Phase 6 Service Layer, we might need to look it up or plain ignore if not in context.
        # Imh_session.engine.context doesn't seem to have current_question object.
        # But for 'get_session', usually we want it.
        # Strategy: If it's pure context, we might skip it or would need to load it.
        # For this Plan Scope, we map what's available.
        if hasattr(session, 'current_question') and session.current_question:
            q = session.current_question
            current_q_dto = QuestionDTO(
                id=str(q.id) if hasattr(q, 'id') else "unknown",
                content=q.content if hasattr(q, 'content') else "",
                type=str(q.type) if hasattr(q, 'type') else "TEXT",
                time_limit_seconds=q.time_limit if hasattr(q, 'time_limit') else 60,
                sequence_number=current_idx + 1
            )
        
        # Handle created_at / started_at
        created_at_dt = datetime.now()
        if hasattr(session, 'created_at') and session.created_at:
            created_at_dt = session.created_at
        elif hasattr(session, 'started_at') and session.started_at:
            created_at_dt = datetime.fromtimestamp(session.started_at)


        return SessionResponseDTO(
            session_id=str(session.session_id),
            status=str(session.status.value) if hasattr(session.status, 'value') else str(session.status),
            created_at=created_at_dt,
            current_question=current_q_dto,
            total_questions=total,
            progress_percentage=round(progress, 1)
        )


    @staticmethod
    def to_list_dto(sessions: List[Any]) -> SessionListDTO:
        return SessionListDTO(
            sessions=[SessionMapper.to_dto(s) for s in sessions],
            total_count=len(sessions)
        )

    @staticmethod
    def to_projection_dto(session: Any) -> "SessionProjectionDTO":
        from packages.imh_dto.projection import SessionProjectionDTO
        
        # Calculate progress
        total = 0
        if hasattr(session, 'config') and hasattr(session.config, 'total_question_limit'):
            total = session.config.total_question_limit
        
        answered = 0
        if hasattr(session, 'completed_questions_count'):
            answered = session.completed_questions_count
            
        progress_dict = {
            "answered": answered,
            "total": total
        }

        # Current Question (Simplified)
        current_q_simple = None
        if hasattr(session, 'current_question') and session.current_question:
            q = session.current_question
            current_q_simple = {
                "id": str(q.id) if hasattr(q, 'id') else "unknown",
                "type": str(q.type.value) if hasattr(q, 'type') and hasattr(q.type, 'value') else "UNKNOWN"
            }
            
        return SessionProjectionDTO(
            session_id=str(session.session_id),
            status=str(session.status.value) if hasattr(session.status, 'value') else str(session.status),
            current_question=current_q_simple,
            progress=progress_dict,
            mode=str(session.config.mode.value) if hasattr(session, 'config') and hasattr(session.config, 'mode') else "UNKNOWN",
            updated_at=datetime.utcnow()
        )

