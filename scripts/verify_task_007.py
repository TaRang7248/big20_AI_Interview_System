import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from IMH.main import app

client = TestClient(app)

def test_embedding():
    print("Testing /api/v1/playground/embedding ...")
    
    # 1. Normal case
    payload = {"text": "Python GIL 개념"}
    response = client.post("/api/v1/playground/embedding", json=payload)
    
    if response.status_code != 200:
        print(f"FAILED: Expected 200, got {response.status_code}")
        print(response.json())
        sys.exit(1)
        
    data = response.json()
    if "vector" not in data or "dimension" not in data:
        print("FAILED: Missing keys in response")
        print(data)
        sys.exit(1)
        
    vector = data["vector"]
    dimension = data["dimension"]
    
    if not isinstance(vector, list) or len(vector) != dimension:
        print(f"FAILED: Vector dimension mismatch. Expected {dimension}, got {len(vector)}")
        sys.exit(1)
        
    print(f"SUCCESS: Got vector of dimension {dimension}")

    # 2. Empty text case
    print("Testing empty text...")
    payload = {"text": "   "}
    response = client.post("/api/v1/playground/embedding", json=payload)
    
    if response.status_code != 400:
        print(f"FAILED: Expected 400 for empty text, got {response.status_code}")
        sys.exit(1)
        
    print("SUCCESS: Empty text rejected as expected")

if __name__ == "__main__":
    test_embedding()
    print("ALL TESTS PASSED")
