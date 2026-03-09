import abc
import json
import os
import uuid
import glob
import logging
from datetime import datetime
from typing import List, Optional, Any

from packages.imh_report.dto import InterviewReport
from packages.imh_history.dto import HistoryMetadata

logger = logging.getLogger("imh_history")

class HistoryRepository(abc.ABC):
    """
    Abstract interface for Report Persistence.
    """
    @abc.abstractmethod
    def save(self, report: InterviewReport) -> str:
        """
        Save the report and return the generated interview_id.
        """
        pass

    @abc.abstractmethod
    def find_by_id(self, interview_id: str) -> Optional[InterviewReport]:
        """
        Find a report by its UUID. Returns None if not found.
        """
        pass

    @abc.abstractmethod
    def find_all(self) -> List[HistoryMetadata]:
        """
        Return a list of metadata for all stored reports, sorted by newest first.
        """
        pass


class FileHistoryRepository(HistoryRepository):
    """
    File-based implementation of HistoryRepository.
    Stores reports as JSON files in a specified directory.
    """
    def __init__(self, base_dir: str = "IMH/IMH_Interview/data/reports"):
        """
        Initialize with the base directory for storage.
        """
        self.base_dir = base_dir
        self._ensure_dir()

    def _ensure_dir(self):
        if not os.path.exists(self.base_dir):
            try:
                os.makedirs(self.base_dir, exist_ok=True)
            except OSError as e:
                logger.error(f"Failed to create directory {self.base_dir}: {e}")
                # We don't raise here, allow save() to fail explicitly later if needed, 
                # or maybe just log. But save() will fail if dir doesn't exist.

    def _generate_filename(self, timestamp: datetime, interview_id: str) -> str:
        # Format: YYYYMMDD_HHMMSS_{uuid}.json
        ts_str = timestamp.strftime("%Y%m%d_%H%M%S")
        return f"{ts_str}_{interview_id}.json"

    def _parse_filename(self, filename: str):
        # returns (timestamp, interview_id) or None
        # Expected format: 20261010_120000_uuid-aaa.json
        try:
            name, ext = os.path.splitext(filename)
            if ext != '.json':
                return None
            parts = name.split('_')
            # timestamp parts are parts[0] (YYYYMMDD) and parts[1] (HHMMSS)
            # uuid part is the rest joined (in case uuid has underscores, though standard uuid doesn't)
            # Format: YYYYMMDD_HHMMSS_uuid
            if len(parts) < 3:
                return None
            
            ts_str = f"{parts[0]}_{parts[1]}"
            timestamp = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            interview_id = "_".join(parts[2:])
            return timestamp, interview_id
        except Exception:
            return None

    def save(self, report: InterviewReport) -> str:
        # Check if interview_id is provided via raw_debug_info (from Dual Write Adapter)
        # This enables single ID generation principle
        if report.raw_debug_info and "_interview_id" in report.raw_debug_info:
            interview_id = report.raw_debug_info["_interview_id"]
            logger.debug(f"Using provided interview_id from Adapter: {interview_id}")
        else:
            # Fallback: Generate ID if not provided (standalone usage)
            interview_id = str(uuid.uuid4())
            logger.debug(f"Generated new interview_id: {interview_id}")
        
        now = datetime.now()
        
        filename = self._generate_filename(now, interview_id)
        filepath = os.path.join(self.base_dir, filename)
        
        try:
            # Save the report model dump
            data = report.model_dump(mode='json')
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            return interview_id
        except Exception as e:
            logger.exception(f"Failed to save report to {filepath}")
            raise e

    def find_by_id(self, interview_id: str) -> Optional[InterviewReport]:
        # Since filename includes timestamp, we can't directly map ID to filename without search
        # or enforcing a structure where ID is enough?
        # Plan says: "정렬/필터링: 파일명에 포함된 Timestamp를 우선 사용한다."
        # This implies we might not know the timestamp when looking up by ID.
        # So we have to search directory.
        
        # Optimization: Glob for *_{interview_id}.json
        pattern = os.path.join(self.base_dir, f"*_{interview_id}.json")
        matches = glob.glob(pattern)
        
        if not matches:
            return None
        
        # Should be unique
        filepath = matches[0]
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return InterviewReport(**data)
        except Exception as e:
            logger.exception(f"Failed to load report from {filepath}")
            return None

    def find_all(self) -> List[HistoryMetadata]:
        results = []
        if not os.path.exists(self.base_dir):
            return []
            
        files = os.listdir(self.base_dir)
        # Sort by filename descending (newest timestamp first)
        files.sort(reverse=True)
        
        for filename in files:
            parsed = self._parse_filename(filename)
            if not parsed:
                continue
                
            timestamp, interview_id = parsed
            filepath = os.path.join(self.base_dir, filename)
            
            try:
                # "Metadata 전략: ... 파일명(Timestamp)과 JSON 내부 필드를 실시간/캐시 파싱"
                # We need to open the file to get score/grade/category
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Robust extraction in case schema changed or data missing
                # data is expected to match InterviewReport dict structure
                header = data.get('header', {})
                total_score = header.get('total_score', 0.0)
                grade = header.get('grade', 'N/A')
                job_category = header.get('job_category', 'Unknown')
                job_id = header.get('job_id')
                
                # If report exists in file history, it is considered EVALUATED by default 
                # unless we have specific logic effectively saying otherwise.
                # Timestamp in filename is usually finished_at or saved_at.
                # We use it as started_at fallback if not available, OR leave started_at None.
                # Review: Plan says "started_at" filter required. 
                # If report doesn't have started_at, we might need to use timestamp as proxy 
                # or add started_at to ReportHeader. 
                # For now, let's use timestamp as proxy for started_at for existing reports 
                # (Assuming short interviews).
                
                meta = HistoryMetadata(
                    interview_id=interview_id,
                    timestamp=timestamp,
                    total_score=total_score,
                    grade=grade,
                    job_category=job_category,
                    job_id=job_id,
                    status="EVALUATED", # Persisted reports are evaluated
                    started_at=timestamp, # Proxy using save time
                    file_path=filename
                )
                results.append(meta)
            except Exception as e:
                logger.warning(f"Failed to parse metadata from {filename}: {e}")
                # Skip malformed files in list
                continue
                
        return results

    def update_interview_status(self, session_id: str, status: Any) -> None:
        """
        Implementation of SessionHistoryRepository.update_interview_status.
        For FileHistoryRepository, we strictly assume 'Evaluation Report' persistence.
        Intermediate status updates (APPLIED -> IN_PROGRESS) are not persisted to cold file storage.
        We log this transition for audit purposes.
        """
        logger.info(f"[HistoryRepo] Status Update for {session_id}: {status}")

    def save_interview_result(self, session_id: str, result_data: Any) -> None:
        """
        Implementation of SessionHistoryRepository.save_interview_result.
        Handles the final persistence of the interview result.
        """
        # If result_data is an InterviewReport, we save it.
        # If it's something else (e.g. SessionContext), we logs warning or try to convert.
        if isinstance(result_data, InterviewReport):
            self.save(result_data)
        else:
            logger.warning(f"[HistoryRepo] save_interview_result called with {type(result_data)}. FileRepo expects InterviewReport.")
            # In a real scenario, we might serialize result_data to a raw json file
            # For now, we log to satisfy the interface.
            pass
