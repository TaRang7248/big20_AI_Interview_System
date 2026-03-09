from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

from IMH.api.schemas import (
    SessionCreateRequest, 
    SessionResponse, 
    AnswerSubmitRequest, 
    QuestionSchema
)
from IMH.api.dependencies import get_session_service
from packages.imh_service.session_service import SessionService
from packages.imh_dto.session import SessionResponseDTO, AnswerSubmissionDTO

router = APIRouter(prefix="/sessions", tags=["Session"])

@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    request: SessionCreateRequest,
    service: SessionService = Depends(get_session_service)
):
    """
    Start a new interview session based on a Job Posting.
    Contract: Uses Frozen Job Policy Snapshot.
    """
    try:
        dto = service.create_session_from_job(request.job_id, request.user_id)
        return _map_dto_to_response(dto)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    service: SessionService = Depends(get_session_service)
):
    """
    Get current session status.
    """
    dto = service.get_session(session_id)
    if not dto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return _map_dto_to_response(dto)

@router.post("/{session_id}/answers", response_model=SessionResponse)
def submit_answer(
    session_id: str,
    answer: AnswerSubmitRequest,
    service: SessionService = Depends(get_session_service)
):
    """
    Submit an answer for the current question.
    Delegates to Service Layer for Concurrency Control and Logic.
    """
    try:
        # Map API Schema to Service DTO
        # Logic: content depends on type
        content_val = answer.text_content if answer.answer_type == "TEXT" else (answer.file_path or "")
        
        submission_dto = AnswerSubmissionDTO(
            type=answer.answer_type,
            content=content_val,
            duration_seconds=answer.duration_seconds
        )
        
        dto = service.submit_answer(session_id, submission_dto)
        return _map_dto_to_response(dto)
        
    except ValueError as e:
        # Business Logic Error (e.g. Session not found, Wrong State)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BlockingIOError as e:
        # FAIL-FAST: Concurrency Lock Error
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


def _map_dto_to_response(dto: SessionResponseDTO) -> SessionResponse:
    # Helper to map strictly to API Contract
    current_q = None
    current_idx = 0
    
    if dto.current_question:
        # QuestionDTO has sequence_number
        current_idx = dto.current_question.sequence_number
        
        # Map QuestionDTO to QuestionSchema
        # QuestionDTO: id, content, type, time_limit_seconds, sequence_number
        current_q = QuestionSchema(
            sequence=dto.current_question.sequence_number,
            content=dto.current_question.content,
            q_type=dto.current_question.type # Assuming generic string or needs mapping
        )
        
    return SessionResponse(
        session_id=dto.session_id,
        status=dto.status, # DTO status is str or enum? DTO def says str.
        current_question_index=current_idx,
        total_questions=dto.total_questions,
        current_question=current_q,
        created_at=dto.created_at
    )
