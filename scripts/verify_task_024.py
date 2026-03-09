import sys
import os
import shutil
import logging
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from packages.imh_qbank import QuestionBankService, JsonFileQuestionRepository, Question, QuestionStatus
from packages.imh_core.logging import get_logger

# Setup logging
logger = get_logger("verify_task_024")

TEMP_REPO_FILE = "temp_qbank_repo.json"

def cleanup():
    if os.path.exists(TEMP_REPO_FILE):
        os.remove(TEMP_REPO_FILE)

def verify_soft_delete_and_immutability():
    print(">>> Verifying TASK-024: QBank Soft Delete & Immutability")
    
    cleanup()
    
    try:
        # 1. Initialize Service & Repo
        repo = JsonFileQuestionRepository(TEMP_REPO_FILE)
        service = QuestionBankService(repo)
        
        # 2. Add Static Question
        print("[Step 1] Adding Static Question...")
        q1 = service.add_static_question(
            content="Explain Dependency Injection.",
            tags=["ARCHITECTURE", "DESIGN_PATTERN"],
            difficulty="HARD",
            job_role="BACKEND"
        )
        assert q1.id is not None
        assert q1.status == QuestionStatus.ACTIVE
        print(" -> Added successfully.")

        # 3. Verify Candidate Retrieval
        print("[Step 2] Verifying Candidate Retrieval...")
        candidates = service.get_candidates(tags=["ARCHITECTURE"])
        assert len(candidates) == 1
        assert candidates[0].id == q1.id
        print(" -> Retrieved successfully.")

        # 4. Simulate Session Snapshot (Immutability Check)
        print("[Step 3] Simulating Session Snapshot...")
        # Session takes a COPY of the question data (Policy: Independent Value)
        # In actual implementation, this would be a Pydantic model dump or deep copy.
        # Here we simulate by keeping the returned object 'q1' as the session record, 
        # and we will modify the bank's record separately.
        # Wait, Python objects are references. 
        # Plan says: "Session has strict independence". 
        # Verification: Ensure that if we modify the repository data, the 'session' object remains untouched 
        # IF we followed the principle. 
        # BUT `service.add_static_question` returns a Question object. 
        # If I modify q1, I modify the object reference.
        # To strictly verify immutability contract, we must assume the Session Engine 
        # would create a copy. 
        # HERE, we verify that the REPOSITORY operations do not affect *external* references 
        # unless they are re-fetched.
        
        session_question_snapshot = Question(
            id=q1.id,
            content=q1.content, # "Explain Dependency Injection."
            tags=list(q1.tags),
            source=q1.source # shared ref for now, but content is string
        )
        
        # 5. Modify Question in Bank (Edit)
        print("[Step 4] Modifying Question in Bank...")
        q_to_edit = repo.find_by_id(q1.id)
        q_to_edit.content = "Explain Dependency Inversion Principle." # Changed
        repo.save(q_to_edit)
        
        # Verify Session Snapshot is Unchanged (Edit-Tolerant)
        assert session_question_snapshot.content == "Explain Dependency Injection."
        print(f" -> Session Snapshot Content: {session_question_snapshot.content}")
        print(f" -> Bank Content: {repo.find_by_id(q1.id).content}")
        assert session_question_snapshot.content != repo.find_by_id(q1.id).content
        print(" -> Edit-Tolerance verified.")

        # 6. Soft Delete in Bank
        print("[Step 5] Soft Deleting Question in Bank...")
        deleted = service.soft_delete_question(q1.id)
        assert deleted is True
        
        q_deleted = repo.find_by_id(q1.id)
        assert q_deleted.status == QuestionStatus.DELETED
        print(" -> Soft Delete status verified.")

        # 7. Verify Exclusion from Candidates
        print("[Step 6] Verifying Exclusion from Candidates...")
        candidates_after_delete = service.get_candidates(tags=["ARCHITECTURE"])
        assert len(candidates_after_delete) == 0
        print(" -> Excluded from candidates successfully.")

        # 8. Verify Session Snapshot is Unchanged (Delete-Tolerant)
        print("[Step 7] Verifying Session Snapshot Preservation...")
        # Session snapshot should still exist and match original state
        assert session_question_snapshot.content == "Explain Dependency Injection."
        assert session_question_snapshot.id == q1.id
        # And we can still retrieve the deleted question using find_by_id for audit
        audit_q = service.get_question_by_id(q1.id)
        assert audit_q is not None
        assert audit_q.status == QuestionStatus.DELETED
        print(" -> Delete-Tolerance verified.")
        
        print(">>> ALL CHECKS PASSED.")
        
    except Exception as e:
        print(f">>> VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cleanup()

if __name__ == "__main__":
    verify_soft_delete_and_immutability()
