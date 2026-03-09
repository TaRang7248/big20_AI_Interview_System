
import os
import sys
import wave
import struct
import math
import requests
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from packages.imh_core.config import IMHConfig


PORT = 8000 # Default FastAPI port
BASE_URL = f"http://127.0.0.1:{PORT}/api/v1/playground"
VOICE_URL = f"{BASE_URL}/voice"

def generate_sine_wave(filename, duration=1.0, frequency=440.0, sample_rate=44100):
    """Generate a WAV file with a sine wave."""
    n_samples = int(sample_rate * duration)
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        for i in range(n_samples):
            value = int(32767.0 * math.sin(2.0 * math.pi * frequency * i / sample_rate))
            data = struct.pack('<h', value)
            wav_file.writeframes(data)

def generate_silence(filename, duration=1.0, sample_rate=44100):
    """Generate a WAV file with silence."""
    n_samples = int(sample_rate * duration)
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        for i in range(n_samples):
            data = struct.pack('<h', 0)
            wav_file.writeframes(data)

def test_voice_analysis_sine_wave():
    filename = "test_sine_440.wav"
    try:
        generate_sine_wave(filename, duration=1.0, frequency=440.0)
        
        with open(filename, 'rb') as f:
            files = {'file': (filename, f, 'audio/wav')}
            print(f"[TEST] Sending Normal Sine Wave (440Hz): {filename}")
            response = requests.post(VOICE_URL, files=files)
        
        if response.status_code == 200:
            result = response.json()
            print(f"[PASS] Normal Analysis Result: {json.dumps(result, indent=2)}")
            
            # Validation
            pitch = result.get('pitch_mean')
            # Parselmouth might give slightly different values but should be close to 440
            if pitch and 430 < pitch < 450:
                print(f"[PASS] Pitch is approximately 440Hz ({pitch})")
            else:
                print(f"[FAIL] Pitch is weird: {pitch}")
                return False
                
            if result.get('jitter') is not None:
                print(f"[PASS] Jitter calculated: {result.get('jitter')}")
            
            return True
        else:
            print(f"[FAIL] Status Code: {response.status_code}")
            print(response.text)
            return False
            
    finally:
        if os.path.exists(filename):
            os.remove(filename)

def test_voice_analysis_silence():
    filename = "test_silence.wav"
    try:
        generate_silence(filename, duration=1.0)
        
        with open(filename, 'rb') as f:
            files = {'file': (filename, f, 'audio/wav')}
            print(f"\n[TEST] Sending Silence: {filename}")
            response = requests.post(VOICE_URL, files=files)
        
        if response.status_code == 200:
            result = response.json()
            print(f"[PASS] Silence Result: {json.dumps(result, indent=2)}")
            
            # Validation: Pitch should be None or 0
            if result.get('pitch_mean') is None or result.get('pitch_mean') == 0:
                print("[PASS] Pitch is None/0 as expected for silence")
            else:
                print(f"[FAIL] Unexpected pitch for silence: {result.get('pitch_mean')}")
                return False
                
            return True
        else:
            print(f"[FAIL] Status Code: {response.status_code}")
            print(response.text)
            return False
            
    finally:
        if os.path.exists(filename):
            os.remove(filename)

def test_invalid_file():
    filename = "test_fake.txt" # PRETENDING to be .wav extension but content is text
    # The API checks extension first
    filename_wav_ext = "test_fake.wav" 
    
    try:
        with open(filename_wav_ext, "w") as f:
            f.write("This is not a wav file")
            
        with open(filename_wav_ext, 'rb') as f:
            files = {'file': (filename_wav_ext, f, 'audio/wav')}
            print(f"\n[TEST] Sending Corrupted/Fake WAV: {filename_wav_ext}")
            response = requests.post(VOICE_URL, files=files)
            
        # Parselmouth will fail to load, expecting 500 (Internal Server Error) re-raised as HTTPException 
        # OR if we handle it gracefully, maybe 400?
        # My implementation re-raises Exception, which is caught by global exception handler usually or the specialized one in playground.
        # Use playground.py catch block: checks for general Exception -> 500.
        
        print(f"[INFO] Status Code: {response.status_code}")
        try:
             print(response.json())
        except:
             print(response.text)
        
        if response.status_code == 422:
             print("[PASS] Received 422 Unprocessable Entity as expected for corrupted file")
             return True
        elif response.status_code == 400:
             print("[PASS] Received 400 Bad Request (acceptable)")
             return True
        else:
             print(f"[FAIL] Expected 422 or 400, got {response.status_code}")
             return False

    finally:
        if os.path.exists(filename_wav_ext):
            os.remove(filename_wav_ext)

if __name__ == "__main__":
    print("=== TASK-009 Verification Script ===")
    print("Ensure the server is running on localhost!")
    
    try:
        health = requests.get(f"http://127.0.0.1:{PORT}/health")
        if health.status_code != 200:
            print("[ERROR] Server is not healthy or not running.")
            sys.exit(1)
    except Exception:
        print("[ERROR] Server is not running. Start it with 'python IMH/main.py'")
        sys.exit(1)

    all_passed = True
    if not test_voice_analysis_sine_wave(): all_passed = False
    if not test_voice_analysis_silence(): all_passed = False
    if not test_invalid_file(): all_passed = False
    
    if all_passed:
        print("\n=== [SUCCESS] All Test Cases Passed ===")
        sys.exit(0)
    else:
        print("\n=== [FAIL] Some Test Cases Failed ===")
        sys.exit(1)
