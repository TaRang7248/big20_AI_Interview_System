from typing import List

from fastapi import APIRouter, Depends, HTTPException

from packages.imh_history.dto import HistoryMetadata
from packages.imh_report.dto import InterviewReport
from packages.imh_history.repository import HistoryRepository

from IMH.api.dependencies import get_history_repository

router = APIRouter()

@router.get("", response_model=List[HistoryMetadata])
def list_reports(
    repository: HistoryRepository = Depends(get_history_repository)
):
    """
    List user's interview history.
    Returns metadata summaries sorted by newest first.
    """
    try:
        results = repository.find_all()
        return results
    except Exception as e:
        # In production, log error properly
        raise HTTPException(status_code=500, detail="Failed to retrieve report history")

@router.get("/{interview_id}", response_model=InterviewReport)
def get_report(
    interview_id: str,
    repository: HistoryRepository = Depends(get_history_repository)
):
    """
    Get detailed interview report by ID.
    Returns full report JSON structure.
    """
    report = repository.find_by_id(interview_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return report
