import json
import os
from typing import List, Optional, Dict
from datetime import datetime
from packages.imh_core.logging import get_logger
from .domain import Question, QuestionStatus, SourceMetadata, SourceType
from .repository_interface import QuestionRepository

logger = get_logger("imh_qbank.repository")

class JsonFileQuestionRepository(QuestionRepository):
    """
    File-based implementation of QuestionRepository using a single JSON file.
    Note: For production/large scale, this should be replaced by DB.
    For current phase, it suffices as per Plan Decision Point A.
    """
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.file_path):
            directory = os.path.dirname(self.file_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump([], f)

    def _load_all(self) -> List[Question]:
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                questions = []
                for item in data:
                    # Parse Question object from dict
                    q = Question(
                        id=item['id'],
                        content=item['content'],
                        tags=item['tags'],
                        difficulty=item['difficulty'],
                        job_role=item.get('job_role'),
                        source=SourceMetadata(
                            source_type=SourceType(item['source']['source_type']),
                            bank_id=item['source'].get('bank_id'),
                            generation_context=item['source'].get('generation_context'),
                            created_at=datetime.fromisoformat(item['source']['created_at'])
                        ),
                        status=QuestionStatus(item['status']),
                        updated_at=datetime.fromisoformat(item['updated_at'])
                    )
                    questions.append(q)
                return questions
        except Exception as e:
            logger.error(f"Failed to load questions from {self.file_path}: {e}")
            return []

    def _save_all(self, questions: List[Question]):
        data = []
        for q in questions:
            data.append({
                'id': q.id,
                'content': q.content,
                'tags': q.tags,
                'difficulty': q.difficulty,
                'job_role': q.job_role,
                'source': {
                    'source_type': q.source.source_type.value,
                    'bank_id': q.source.bank_id,
                    'generation_context': q.source.generation_context,
                    'created_at': q.source.created_at.isoformat()
                },
                'status': q.status.value,
                'updated_at': q.updated_at.isoformat()
            })
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save questions to {self.file_path}: {e}")
            raise

    def save(self, question: Question) -> None:
        questions = self._load_all()
        # Check if update or insert
        for i, q in enumerate(questions):
            if q.id == question.id:
                questions[i] = question
                self._save_all(questions)
                logger.info(f"Updated question {question.id} in bank.")
                return
        
        questions.append(question)
        self._save_all(questions)
        logger.info(f"Saved new question {question.id} to bank.")

    def find_by_id(self, question_id: str) -> Optional[Question]:
        questions = self._load_all()
        for q in questions:
            if q.id == question_id:
                return q
        return None

    def find_all_active(self) -> List[Question]:
        questions = self._load_all()
        return [q for q in questions if q.status == QuestionStatus.ACTIVE and q.is_active()]

    def delete(self, question_id: str) -> bool:
        questions = self._load_all()
        for q in questions:
            if q.id == question_id:
                q.mark_deleted() # Soft Delete
                self._save_all(questions)
                logger.info(f"Soft deleted question {question_id}.")
                return True
        logger.warning(f"Attempted to delete non-existent question {question_id}.")
        return False
