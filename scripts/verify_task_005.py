import asyncio
import os
import sys
import tempfile
from fastapi.testclient import TestClient

# Add project root to sys.path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from IMH.main import app

client = TestClient(app)

def test_stt_upload():
    print(">>> [TASK-005] Verifying Playground STT API...")
    
    # 1. Prepare Dummy File
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(b"RIFF" + b"\x00" * 36) # Minimal WAV header mock
        temp_path = f.name
    
    try:
        # 2. Test Success Case
        print("[TEST] Uploading valid .wav file...")
        with open(temp_path, "rb") as f:
            response = client.post(
                "/api/v1/playground/stt",
                files={"file": ("test.wav", f, "audio/wav")}
            )
        
        if response.status_code == 200:
            data = response.json()
            # print(data)
            assert "text" in data
            assert "segments" in data
            print(f"[PASS] Success Case: {data['text']}")
        else:
            print(f"[FAIL] Expected 200, got {response.status_code}: {response.text}")
            sys.exit(1)

        # 3. Test Invalid Extension
        print("[TEST] Uploading invalid extension (.txt)...")
        with open(temp_path, "rb") as f:
             response = client.post(
                "/api/v1/playground/stt",
                files={"file": ("test.txt", f, "text/plain")}
            )
        
        if response.status_code == 400:
            print(f"[PASS] Invalid Extension Rejection: {response.json()}")
        else:
            print(f"[FAIL] Expected 400, got {response.status_code}: {response.text}")
            sys.exit(1)
            
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
    print(">>> [TASK-005] Verification Complete!")

if __name__ == "__main__":
    test_stt_upload()
