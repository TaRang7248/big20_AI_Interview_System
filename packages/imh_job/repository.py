from abc import ABC, abstractmethod
from typing import Optional, List
from .models import Job, JobStatus

class JobPostingRepository(ABC):
    @abstractmethod
    def save(self, job: Job) -> None:
        pass

    @abstractmethod
    def find_by_id(self, job_id: str) -> Optional[Job]:
        pass

    @abstractmethod
    def find_published(self) -> List[Job]:
        pass

class MemoryJobPostingRepository(JobPostingRepository):
    def __init__(self):
        self._jobs: dict[str, Job] = {}

    def save(self, job: Job) -> None:
        self._jobs[job.job_id] = job

    def find_by_id(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def find_published(self) -> List[Job]:
        return [j for j in self._jobs.values() if j.status == JobStatus.PUBLISHED]
