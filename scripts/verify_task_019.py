import sys
from datetime import datetime

# Adjust path to find packages
sys.path.append("c:/big20/big20_AI_Interview_simulation/IMH/IMH_interview")
sys.path.append("c:/big20/big20_AI_Interview_simulation/IMH/IMH_interview/packages")

from imh_job import Job, JobPolicy, JobStatus, JobStateError, PolicyValidationError
from imh_session.policy import InterviewMode

def run_verification():
    print("=== TASK-019 Verification: Job Policy Engine ===")
    
    # 1. Create Job in DRAFT
    print("\n1. creating Job (DRAFT)...")
    policy = JobPolicy(
        mode=InterviewMode.ACTUAL,
        total_question_limit=15,
        min_question_count=10,
        description="Software Engineer Interiew",
        requirements=["Python", "System Design"],
        preferences=["FastAPI"]
    )
    job = Job(job_id="job-001", title="Backend Engineer", status=JobStatus.DRAFT, policy=policy)
    print(f"   -> Job Created: {job.job_id} [{job.status}]")
    assert job.status == JobStatus.DRAFT

    # 2. Update Policy in DRAFT (Should Succeed)
    print("\n2. Updating Policy in DRAFT...")
    new_policy = policy.copy()
    new_policy.total_question_limit = 20
    job.update_policy(new_policy)
    print(f"   -> Policy Updated. Limit: {job.policy.total_question_limit}")
    assert job.policy.total_question_limit == 20

    # 3. Publish Job
    print("\n3. Publishing Job...")
    job.publish()
    print(f"   -> Job Published: {job.status} at {job.published_at}")
    assert job.status == JobStatus.PUBLISHED
    assert job.published_at is not None

    # 4. Try to Update Policy in PUBLISHED (Should Fail)
    print("\n4. Attempting to Update Policy in PUBLISHED (Expected Failure)...")
    try:
        invalid_policy = new_policy.copy()
        invalid_policy.total_question_limit = 99
        job.update_policy(invalid_policy)
        print("   -> FAIL: Policy update should have been blocked!")
        sys.exit(1)
    except PolicyValidationError as e:
        print(f"   -> SUCCESS: Blocked with error: {e}")

    # 5. Try to Revert State (Should Fail via Logic) -> Skipped as inferred.
    
    # 5-B. Try Direct Assignment (Bypass Check) in PUBLISHED
    print("\n5-B. Attempting Direct `job.policy = ...` Assignment in PUBLISHED...")
    try:
        job.policy = new_policy
        print("   -> FAIL: Direct assignment should have been blocked!")
        sys.exit(1)
    except PolicyValidationError as e:
        print(f"   -> SUCCESS: Blocked with error: {e}")
    
    # 6. Create Snapshot
    print("\n5. Creating Session Snapshot...")
    session_config = job.create_session_config()
    print(f"   -> Snapshot Created: {session_config}")
    assert session_config.total_question_limit == 20
    assert session_config.mode == InterviewMode.ACTUAL
    assert session_config.min_question_count == 10

    # 7. Close Job
    print("\n6. Closing Job...")
    job.close()
    print(f"   -> Job Closed: {job.status}")
    assert job.status == JobStatus.CLOSED

    # 8. Try to Update Metadata in CLOSED (Should Fail)
    print("\n7. Attempting to Update Metadata in CLOSED (Expected Failure)...")
    try:
        job.update_metadata({"headcount": 0})
        print("   -> FAIL: Metadata update should have been blocked in CLOSED state!")
        sys.exit(1)
    except JobStateError as e:
         print(f"   -> SUCCESS: Blocked with error: {e}")

    print("\n=== Verification Completed: All Checks Passed ===")

if __name__ == "__main__":
    run_verification()
