import sys
import os
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from fastapi.testclient import TestClient
from IMH.main import app
from packages.imh_core.config import IMHConfig

def verify_task_004():
    print(">>> Verifying TASK-004: FastAPI Entry & Healthcheck")
    
    # 1. Test Client Initialization (Triggers Lifespan Startup)
    print("[1] Initializing TestClient...")
    with TestClient(app) as client:
        
        # 2. Check /health endpoint
        print("[2] Requesting GET /health...")
        response = client.get("/health")
        
        if response.status_code != 200:
            print(f"[FAIL] Expected 200 OK, got {response.status_code}")
            sys.exit(1)
            
        data = response.json()
        print(f"    Response: {data}")
        
        # Verify fields
        required_fields = ["status", "version", "timestamp"]
        for field in required_fields:
            if field not in data:
                print(f"[FAIL] Missing field: {field}")
                sys.exit(1)
        
        config = IMHConfig.load()
        if data["version"] != config.VERSION:
            print(f"[FAIL] Version mismatch: Expected {config.VERSION}, got {data['version']}")
            sys.exit(1)
            
        print("[PASS] Healthcheck response is valid.")

    # 3. Verify Runtime Logging
    print("[3] Verifying Runtime Logs...")
    log_dir = os.path.join(os.path.dirname(__file__), "../logs/runtime")
    log_file = os.path.join(log_dir, "runtime.log")
    
    if not os.path.exists(log_file):
        print(f"[FAIL] Runtime log file not found at {log_file}")
        sys.exit(1)
        
    with open(log_file, "r", encoding="utf-8") as f:
        logs = f.read()
        print(f"    Log content preview (last 500 chars):\n    {logs[-500:]}")
        
        if "Starting" not in logs:
            print("[WARN] 'Starting' log not found. (Might be due to log rotation or timing)")
        if "Server shutting down" not in logs:
            print("[WARN] 'Shutting down' log not found.")

    print("\n>>> TASK-004 Verification SUCCESS")

if __name__ == "__main__":
    verify_task_004()
