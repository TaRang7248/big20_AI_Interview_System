"""
IMH UI API 검증 스크립트 (TASK-UI)
백엔드 API E2E 흐름을 검증합니다.

Usage:
    python scripts/verify_ui_apis.py
"""
import sys
import json
import uuid
import requests

BASE = "http://localhost:8000/api/v1"
session = requests.Session()

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"

results = []

def check(name: str, ok: bool, detail: str = ""):
    icon = PASS if ok else FAIL
    print(f"  {icon} {name}" + (f" | {detail}" if detail else ""))
    results.append((name, ok))
    return ok


def section(title: str):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")


def main():
    u = f"apitest_{uuid.uuid4().hex[:6]}"
    pw = "testpass123"
    token = None
    admin_token = None

    # -------- AUTH --------
    section("AUTH: Signup & Login")

    # Signup candidate
    r = session.post(f"{BASE}/auth/signup", json={
        "username": u, "password": pw, "name": "API 테스트 유저",
        "email": "api@test.com", "user_type": "CANDIDATE"
    })
    check("Signup (CANDIDATE)", r.status_code == 201, f"status={r.status_code}")

    # Duplicate check
    r = session.get(f"{BASE}/auth/check-username", params={"username": u})
    check("Username check (taken)", r.ok and r.json().get("available") == False, str(r.json()))

    # Login
    r = session.post(f"{BASE}/auth/login", json={"username": u, "password": pw})
    ok = r.ok and "token" in r.json()
    check("Login", ok, f"status={r.status_code}")
    if ok:
        token = r.json()["token"]

    # Signup admin
    admin_u = f"admin_{uuid.uuid4().hex[:6]}"
    r = session.post(f"{BASE}/auth/signup", json={
        "username": admin_u, "password": pw, "name": "관리자 테스트",
        "user_type": "ADMIN"
    })
    check("Signup (ADMIN)", r.status_code == 201, f"status={r.status_code}")

    r = session.post(f"{BASE}/auth/login", json={"username": admin_u, "password": pw})
    ok = r.ok and "token" in r.json()
    check("Admin login", ok, str(r.status_code))
    if ok:
        admin_token = r.json()["token"]

    # Get me
    headers = {"Authorization": f"Bearer {token}"}
    r = session.get(f"{BASE}/auth/me", headers=headers)
    check("GET /auth/me", r.ok, f"name={r.json().get('name')}")

    # -------- JOBS --------
    section("JOBS: CRUD")

    admin_h = {"Authorization": f"Bearer {admin_token}"}

    # Create job
    r = session.post(f"{BASE}/jobs", json={
        "title": "API 테스트 포지션",
        "company": "테스트 주식회사",
        "description": "테스트 공고입니다.",
        "location": "서울",
        "headcount": 3,
        "deadline": "2026-12-31",
        "tags": ["Python", "FastAPI"],
        "total_question_limit": 6,
        "question_timeout_sec": 120,
        "mode": "ACTUAL",
    }, headers=admin_h)
    ok = r.status_code == 201 and "job_id" in r.json()
    check("POST /jobs (create)", ok, f"status={r.status_code}")
    job_id = r.json().get("job_id") if ok else None

    # List jobs
    r = session.get(f"{BASE}/jobs")
    check("GET /jobs (list)", r.ok, f"count={len(r.json())}")

    # Get job detail
    if job_id:
        r = session.get(f"{BASE}/jobs/{job_id}")
        check("GET /jobs/{id} (detail)", r.ok, f"title={r.json().get('title')}")

        # Publish
        r = session.patch(f"{BASE}/jobs/{job_id}", json={"action": "PUBLISH"}, headers=admin_h)
        check("PATCH /jobs/{id} (PUBLISH)", r.ok, str(r.status_code))

        # Update
        r = session.patch(f"{BASE}/jobs/{job_id}", json={"title": "API 테스트 포지션 (수정됨)"}, headers=admin_h)
        check("PATCH /jobs/{id} (update)", r.ok, str(r.status_code))

    # -------- INTERVIEWS --------
    section("INTERVIEWS: Session & Chat")

    session_id = None
    if job_id:
        # Create interview
        r = session.post(f"{BASE}/interviews", json={"job_id": job_id}, headers=headers)
        ok = r.status_code == 201 and "session_id" in r.json()
        check("POST /interviews (create)", ok, f"status={r.status_code}")
        session_id = r.json().get("session_id") if ok else None

    if session_id:
        # Get session state
        r = session.get(f"{BASE}/interviews/{session_id}", headers=headers)
        check("GET /interviews/{id}", r.ok, f"phase={r.json().get('current_phase')}")

        # Get chat history (should have initial AI message)
        r = session.get(f"{BASE}/interviews/{session_id}/chat", headers=headers)
        chat = r.json()
        check("GET /interviews/{id}/chat", r.ok and len(chat) >= 1, f"messages={len(chat)}")

        # Submit 6 answer turns (to complete the interview)
        is_done = False
        for i in range(6):
            r = session.post(f"{BASE}/interviews/{session_id}/chat",
                             json={"content": f"테스트 답변 {i+1}입니다. 충분히 긴 내용으로 답변드립니다."},
                             headers=headers)
            if r.ok:
                data = r.json()
                if data.get("is_done"):
                    is_done = True
                    break
            else:
                check(f"POST chat turn {i+1}", False, str(r.status_code))
                break

        check("Interview completed (6 turns)", is_done)

        # Get result
        r = session.get(f"{BASE}/interviews/{session_id}/result", headers=headers)
        ok = r.ok and r.json().get("evaluation") is not None
        check("GET /interviews/{id}/result", ok, f"decision={r.json().get('evaluation', {}).get('decision')}" if r.ok else str(r.status_code))

    # -------- ADMIN CANDIDATES --------
    section("ADMIN: Candidate List")

    if job_id:
        r = session.get(f"{BASE}/jobs/{job_id}/candidates", headers=admin_h)
        check("GET /jobs/{id}/candidates", r.ok, f"count={len(r.json())}")

    # -------- SUMMARY --------
    total = len(results)
    passed = sum(1 for _, ok in results if ok)
    section(f"SUMMARY: {passed}/{total} passed")
    for name, ok in results:
        icon = PASS if ok else FAIL
        print(f"  {icon} {name}")

    if passed < total:
        print(f"\n{FAIL} {total-passed} test(s) FAILED")
        sys.exit(1)
    else:
        print(f"\n{PASS} All {total} tests passed!")


if __name__ == "__main__":
    main()
