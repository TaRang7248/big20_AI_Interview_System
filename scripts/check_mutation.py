
import sys
sys.path.append("c:/big20/big20_AI_Interview_simulation/IMH/IMH_interview")
sys.path.append("c:/big20/big20_AI_Interview_simulation/IMH/IMH_interview/packages")

from imh_job import Job, JobPolicy, JobStatus
from imh_session.policy import InterviewMode

def check_immutability():
    print("Checking Job Policy Immutability...")
    
    # Setup
    policy = JobPolicy(
        mode=InterviewMode.ACTUAL,
        total_question_limit=10,
        min_question_count=10,
        description="Test Job Description must be very long",
        requirements=["None"],
        preferences=["None"]
    )
    job = Job(job_id="test", title="Test", status=JobStatus.PUBLISHED, policy=policy)
    
    # Test 1: Direct Assignment
    try:
        new_policy = policy.copy()
        new_policy.total_question_limit = 999
        job.policy = new_policy
        print("[WARN] Direct assignment to job.policy is POSSIBLE.")
        is_immutable = False
    except Exception as e:
        print(f"[pass] Direct assignment failed: {e}")
        is_immutable = True

    # Test 2: Update Metadata Separation
    try:
        original_policy_limit = job.policy.total_question_limit
        job.update_metadata({"headcount": 5})
        if job.policy.total_question_limit == original_policy_limit:
            print("[PASS] update_metadata did not affect policy.")
        else:
            print("[FAIL] update_metadata affected policy!")
    except Exception as e:
        print(f"[FAIL] update_metadata failed: {e}")

if __name__ == "__main__":
    check_immutability()
