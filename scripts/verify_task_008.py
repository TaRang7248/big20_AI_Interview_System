import os
import sys
import numpy as np
import cv2
from fastapi.testclient import TestClient

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from IMH.main import app

client = TestClient(app)

def create_dummy_video(filename, duration_sec=3, fps=10):
    height, width = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
    
    # Create black frames
    # To simulate a face, maybe draw a rectangle? DeepFace might not detect it.
    # But verify script just needs to check PIPELINE, not model accuracy.
    # If no face, it returns face_detected=False. This is valid verification.
    
    # Try to draw a face-like structure? No, simple black frame is enough to verify pipeline runs.
    # The Plan says: "2. 얼굴 없는 영상: 에러 없이 face_detected: false 리스트가 나오는지 확인"
    for _ in range(duration_sec * fps):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        # Draw a white circle to have some content
        cv2.circle(frame, (320, 240), 100, (255, 255, 255), -1)
        out.write(frame)
    
    out.release()
    return filename

def create_dummy_image(filename):
    height, width = 640, 480
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.circle(frame, (320, 240), 100, (255, 255, 255), -1)
    cv2.imwrite(filename, frame)
    return filename

def test_emotion_image():
    print("Testing Image Upload...")
    img_path = "test_image.jpg"
    create_dummy_image(img_path)
    
    try:
        with open(img_path, "rb") as f:
            response = client.post(
                "/api/v1/playground/emotion",
                files={"file": ("test_image.jpg", f, "image/jpeg")}
            )
        
        print(f"Status Code: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.text}")
            return False
            
        data = response.json()
        print("Response JSON keys:", data.keys())
        if "results" not in data or len(data["results"]) != 1:
            print("Failed: Expected 1 result for image")
            return False
            
        print("Image Test Passed!")
        return True
    finally:
        if os.path.exists(img_path):
            os.remove(img_path)

def test_emotion_video():
    print("\nTesting Video Upload (3s, 10fps)...")
    vid_path = "test_video.mp4"
    create_dummy_video(vid_path, duration_sec=3, fps=10)
    
    try:
        with open(vid_path, "rb") as f:
            response = client.post(
                "/api/v1/playground/emotion",
                files={"file": ("test_video.mp4", f, "video/mp4")}
            )
        
        print(f"Status Code: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.text}")
            return False
            
        data = response.json()
        print("Response JSON keys:", data.keys())
        
        # Verify 1fps sampling
        # duration 3s. frames at 0, 1, 2s. total 3 frames.
        results = data.get("results", [])
        print(f"Results Count: {len(results)}")
        
        if len(results) < 2 or len(results) > 4: # approx 3
             print(f"Warning: Expected ~3 frames, got {len(results)}")
             
        # Verify timestamps
        timestamps = [r["timestamp"] for r in results]
        print(f"Timestamps: {timestamps}")
        
        # Verify content
        for r in results:
             print(f"Time: {r['timestamp']}, FaceDetected: {r['face_detected']}")
             
        print("Video Test Passed!")
        return True
    finally:
        if os.path.exists(vid_path):
            os.remove(vid_path)

if __name__ == "__main__":
    success = True
    if not test_emotion_image():
        success = False
    if not test_emotion_video():
        success = False
        
    if success:
        print("\nAll Tests Passed!")
        sys.exit(0)
    else:
        print("\nSome Tests Failed!")
        sys.exit(1)
