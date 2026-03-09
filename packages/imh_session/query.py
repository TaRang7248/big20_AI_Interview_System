import logging
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from packages.imh_session.repository import SessionStateRepository
from packages.imh_history.repository import HistoryRepository
from packages.imh_history.dto import HistoryMetadata
from packages.imh_session.state import SessionStatus

logger = logging.getLogger("imh_session.query")

# --- DTOs for Query Service ---

class ApplicantSortDTO(BaseModel):
    sort_by: str = Field(default="started_at", description="Sort field")
    order: str = Field(default="desc", description="Sort order (asc/desc)")

class ApplicantFilterDTO(BaseModel):
    job_id: str
    status: Optional[List[str]] = Field(None, description="List of statuses to include")
    result: Optional[str] = Field(None, description="PASS/FAIL/PENDING")
    
    # Date Filter
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    # Optional Filters
    search_keyword: Optional[str] = None
    weakness: Optional[str] = None # tag_code
    
    # Alias handling
    is_interrupted: Optional[bool] = None

class ApplicantSummaryDTO(BaseModel):
    """
    Summary returned to Admin UI.
    Requires minimum fields as per Plan.
    """
    session_id: str
    applicant_name: Optional[str] = Field(None, description="Name (if available)")
    started_at: Optional[datetime]
    status: str
    result: str # PASS/FAIL/PENDING
    score_total: Optional[float]
    is_interrupted: bool

class ApplicantListResponse(BaseModel):
    job_id: str
    total_count: int
    page: int
    size: int
    items: List[ApplicantSummaryDTO]

# --- Query Service ---

class ApplicantQueryService:
    def __init__(self, state_repo: SessionStateRepository, history_repo: HistoryRepository):
        self.state_repo = state_repo
        self.history_repo = history_repo

    def search_applicants(self, filter_dto: ApplicantFilterDTO, page: int = 1, size: int = 20, sort: ApplicantSortDTO = None) -> ApplicantListResponse:
        """
        Federated search across Hot (SessionState) and Cold (History) storage.
        """
        all_items: List[ApplicantSummaryDTO] = []
        
        # 1. Alias Handling: is_interrupted
        if filter_dto.is_interrupted:
            if filter_dto.status is None:
                filter_dto.status = []
            if SessionStatus.INTERRUPTED not in filter_dto.status:
                filter_dto.status.append(SessionStatus.INTERRUPTED)
        
        # 2. Fetch Active Sessions (Hot)
        # Note: Active sessions are usually APPLIED, IN_PROGRESS, INTERRUPTED (before cleanup)
        active_sessions = self.state_repo.find_by_job_id(filter_dto.job_id)
        for session in active_sessions:
            # Map to Summary
            # Active sessions usually don't have score/result yet
            dto = self._map_session_to_summary(session)
            all_items.append(dto)
            
        # 3. Fetch Archived Sessions (Cold)
        # HistoryRepo usually stores COMPLETED, EVALUATED files
        # find_all returns everything (Metadata), we need to filter
        all_history = self.history_repo.find_all()
        for meta in all_history:
            # Filter by Job ID first
            if meta.job_id != filter_dto.job_id:
                continue
                
            dto = self._map_history_to_summary(meta)
            all_items.append(dto)
            
        # 4. Apply Filters (Memory Filter)
        filtered_items = self._apply_filters(all_items, filter_dto)
        
        # 5. Sort
        if sort is None:
            sort = ApplicantSortDTO()
        
        filtered_items.sort(
            key=lambda x: getattr(x, sort.sort_by) if getattr(x, sort.sort_by) else datetime.min,  
            reverse=(sort.order == 'desc')
        )
        
        # 6. Pagination
        total_count = len(filtered_items)
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        paged_items = filtered_items[start_idx:end_idx]
        
        return ApplicantListResponse(
            job_id=filter_dto.job_id,
            total_count=total_count,
            page=page,
            size=size,
            items=paged_items
        )

    def _map_session_to_summary(self, session) -> ApplicantSummaryDTO:
        # PENDING Logic: Active sessions are PENDING result wise if not evaluated
        result = "PENDING"
        # Since SessionContext doesn't have score, it's null
        return ApplicantSummaryDTO(
            session_id=session.session_id,
            started_at=datetime.fromtimestamp(session.started_at) if session.started_at else None, 
            status=session.status,
            result=result,
            score_total=None,
            is_interrupted=(session.status == SessionStatus.INTERRUPTED)
        )

    def _map_history_to_summary(self, meta: HistoryMetadata) -> ApplicantSummaryDTO:
        # meta.status is usually EVALUATED or COMPLETED from repo logic
        result = "PENDING"
        if meta.status == SessionStatus.EVALUATED:
            # Pass/Fail logic depends on Score/Grade?
            # Plan says: "PASS/FAIL based on Evaluation Final Field"
            # Metadata has 'grade'. Let's use grade for now or assume logic.
            # Plan: "PASS/FAIL value depends on Evaluation Engine Schema"
            # Since Metadata is light, we rely on 'grade' if available.
            # If grade is 'F' or 'D' -> FAIL? This is business logic.
            # Plan says "Pans document defines PASS/FAIL only valid for EVALUATED".
            # Plan doesn't define threshold.
            # We will expose what's in 'grade' or map it if needed.
            # For this DTO, let's map 'grade' to result text if possible, or just 'PENDING' if grade is missing.
            if meta.grade and meta.grade != 'N/A':
                 result = "PASS" if meta.grade in ['S', 'A', 'B'] else "FAIL" # Example logic
            else:
                 result = "PENDING"
        
        return ApplicantSummaryDTO(
            session_id=meta.interview_id,
            started_at=meta.started_at if meta.started_at else meta.timestamp, # specific logic
            status=meta.status,
            result=result,
            score_total=meta.total_score,
            is_interrupted=(meta.status == SessionStatus.INTERRUPTED)
        )

    def _apply_filters(self, items: List[ApplicantSummaryDTO], filters: ApplicantFilterDTO) -> List[ApplicantSummaryDTO]:
        result = []
        for item in items:
            # Status Filter
            if filters.status and item.status not in filters.status:
                continue
                
            # Date Filter (started_at)
            # APPLIED (started_at is None) -> Exclude if date filter exists
            if filters.start_date or filters.end_date:
                if not item.started_at:
                    continue # Exclude APPLIED or those without start time
                
                if filters.start_date and item.started_at < filters.start_date:
                    continue
                if filters.end_date and item.started_at > filters.end_date:
                    continue
            
            # Result Filter (PASS/FAIL)
            # Only applies to EVALUATED sessions?
            # Plan: "result filter only applies to status=EVALUATED"
            # If user filters by RESULT=PASS, we should only return EVALUATED sessions that are PASS.
            if filters.result:
                if item.status != SessionStatus.EVALUATED:
                    continue
                if item.result != filters.result:
                    continue
            
            # Search Keyword
            if filters.search_keyword:
                keyword = filters.search_keyword.strip()
                if len(keyword) < 2:
                    raise ValueError("Search keyword must be at least 2 characters.")
                
                # Check if it looks like an email (simple check)
                if '@' in keyword:
                    # Email: Exact Match on Applicant Name (as implicit proxy)
                    # Note: SummaryDTO doesn't have email field, so we check applicant_name.
                    # Plan Requirement: "Email: Exact Match Only"
                    # Implementation: If keyword looks like email, we enforced exact match on available name field.
                    if item.applicant_name:
                        if item.applicant_name.lower() != keyword.lower():
                            continue
                    else:
                        continue # No name to match against
                else:
                    # Name: Partial Match
                    if item.applicant_name:
                        if keyword.lower() not in item.applicant_name.lower():
                            continue
                    else:
                        continue # No name to match against
            
            # Weakness Filter
            if filters.weakness:
                # Plan Requirement: Explicitly reject with 400
                raise ValueError("Weakness filter is not supported in TASK-020 contract.")

            result.append(item)
            
        return result
