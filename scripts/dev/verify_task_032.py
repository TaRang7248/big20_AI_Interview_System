import asyncio
import os
import random
import sys
from pprint import pprint
import uuid

# Setup Python Path for IMH package resolution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from packages.imh_core.config import IMHConfig
from app.api.dependencies import get_session_service

def verify_e2e_flow():
    print("--- TASK-032 Local Verification Start ---")
    
    # 1. Config Check
    config = IMHConfig.load()
    print(f"[Config] LLM Provider: {config.ACTIVE_LLM_PROVIDER}")
    print(f"[Config] Write Path: {config.WRITE_PATH_PRIMARY}")
    
    # Needs valid connection string to test PG
    if not config.POSTGRES_CONNECTION_STRING:
         print("[Error] POSTGRES_CONNECTION_STRING is missing. Required for End-to-End.")
         sys.exit(1)
         
    # 2. Get Service Instance (wires everything)
    service = get_session_service()
    
    # 3. Create Session
    mock_job_id = "job-mock-local"
    mock_user_id = f"test-user-{uuid.uuid4().hex[:6]}"
    
    # [Pre-flight] Ensure Mock Job Exists in DB
    try:
        import asyncio
        import asyncpg
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def ensure_job():
            dsn = config.POSTGRES_CONNECTION_STRING.replace("postgresql+asyncpg://", "postgresql://")
            conn = await asyncpg.connect(dsn)
            try:
                exists = await conn.fetchval("SELECT 1 FROM jobs WHERE job_id = $1", mock_job_id)
                if not exists:
                    await conn.execute("INSERT INTO jobs (job_id, title, status) VALUES ($1, 'Mock Job', 'PUBLISHED')", mock_job_id)
            finally:
                await conn.close()
                
        loop.run_until_complete(ensure_job())
        loop.run_until_complete(ensure_job())
    except Exception as e:
        print(f"[Warning] Failed to ensure mock job in DB: {e}")
        
    # Also inject into the application's memory job repository
    from packages.imh_job.models import Job, JobPolicy
    from packages.imh_job.enums import JobStatus
    from packages.imh_session.policy import InterviewMode
    
    policy = JobPolicy(
        description="Mock Policy",
        total_question_limit=10,
        min_question_count=10,
        question_timeout_sec=60,
        silence_timeout_sec=15,
        mode=InterviewMode.PRACTICE
    )
    mock_job = Job(job_id=mock_job_id, title="Mock Job", status=JobStatus.PUBLISHED, policy=policy)
    service.job_repo.save(mock_job)
    
    try:
         # Need an actual job in DB for this to truly succeed, but we're testing the logic
         # Let's bypass DB job check by instantiating a raw session object directly for testing
         # OR assuming a job exists. Let's assume job "test_job" exists, otherwise we'll spoof it.
        import time
        print(f"[Flow] 1. Creating Session for user {mock_user_id}...")
        start_time = time.time()
        
        job_policy_snapshot = {
            "mode": "PRACTICE",
            "time_limit_seconds": 60,
            "max_retries": 1,
            "total_question_limit": 3,
            "job_id": mock_job_id,
        }
        
        started_dto = service.create_session(job_policy_snapshot, mock_user_id)
        end_time = time.time()
        creation_latency = end_time - start_time
         
        session_id = started_dto.session_id
        print(f"Session Started: {started_dto.status} (Latency: {creation_latency:.2f}s)")
        print(f"Question 1: {started_dto.current_question.content if started_dto.current_question else 'None'}")
        
        # 4. Answers
        from packages.imh_dto.session import AnswerSubmissionDTO
        
        step_latencies = []
        for i in range(1, 4): # Assume 3 phases/questions
            print(f"\n[Flow] 2.{i} Submitting Answer {i}...")
            ans_dto = AnswerSubmissionDTO(type="TEXT", content=f"My generic test answer for question {i}.", duration_seconds=15.0)
            
            s_t = time.time()
            updated_session = service.submit_answer(session_id, ans_dto)
            e_t = time.time()
            lat = e_t - s_t
            step_latencies.append(lat)
            
            print(f"Status: {updated_session.status} (Latency: {lat:.2f}s)")
            if updated_session.current_question:
                print(f"Next Question {i+1}: {updated_session.current_question.content}")
                
            if updated_session.status == "COMPLETED":
                print("Session reached COMPLETED status.")
                break
        
        if step_latencies:
            avg_lat = sum(step_latencies) / len(step_latencies)
            print(f"\n[Stats] Average Submit Latency: {avg_lat:.2f}s (Min: {min(step_latencies):.2f}s, Max: {max(step_latencies):.2f}s)")

                 
    except Exception as e:
        print(f"Error during flow: {e}")
        return

    # 5. Idempotency Check (Simulate concurrent API hits trying to save)
    print("\n[Flow] 3. Testing Evaluator Idempotency (Forcing Evaluation)")
    try:
        from packages.imh_eval.engine import RubricEvaluator, EvaluationContext
        from packages.imh_report.engine import ReportGenerator
        
        context = EvaluationContext(
            job_category="DEV", 
            job_id=mock_job_id,
            answer_text="Overall answer consolidation test.",
            rag_keywords_found=["Mock", "Keyword"],
            hint_count=0
        )
        eval_result = RubricEvaluator().evaluate(context)
        report = ReportGenerator.generate(eval_result)
        report.raw_debug_info = {"_session_id": session_id, "_interview_id": session_id}
        
        import concurrent.futures
        
        def concurrent_save(thread_index):
            print(f"[Thread-{thread_index}] Saving Report...")
            # Each thread needs to deepcopy the report to ensure independent object instances if necessary,
            # though here we are testing the DB layer idempotency. Let's just pass the same report.
            return service.history_repo.save_interview_result(session_id, report)
            
        print("Firing 3 concurrent save requests to test DB-Level Idempotency...")
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(concurrent_save, i) for i in range(3)]
            for future in concurrent.futures.as_completed(futures):
                try:
                    res = future.result()
                    results.append(res)
                    print(f"Result ID returned: {res}")
                except Exception as ex:
                    print(f"Concurrent Save Failed: {ex}")
                    
        if len(set(results)) == 1 and len(results) == 3:
            print(f"[SUCCESS] True Idempotency holds! All 3 threads returned the EXACT SAME ID: {results[0]}")
        else:
            print(f"[FAIL] Idempotency failed! IDs do not match or a thread failed: {results}")
    except Exception as e:
        print(f"Error during Evaluation Test: {e}")

    # 6. Database Verification (UI Mapping logic)
    print("\n[Flow] 4. Fetching mapped UI data via repository")
    saved_report = service.history_repo.find_by_id(session_id)
    if saved_report:
        tech_score = 0.0
        prob_score = 0.0
        for detail in saved_report.details:
            if detail.tag_code == "capability.knowledge": tech_score = detail.score * 20.0
            elif detail.tag_code == "capability.problem_solving": prob_score = detail.score * 20.0
        
        print(f"Extracted Tech Score (UI format): {tech_score}")
        print(f"Extracted Problem Solving Score (UI format): {prob_score}")
        print(f"Decision: {'PASS' if saved_report.header.total_score >= 70 else 'FAIL'}")
    else:
        print("Failed to find saved report.")

    print("\n--- TASK-032 Local Verification Complete ---")


if __name__ == "__main__":
    verify_e2e_flow()
