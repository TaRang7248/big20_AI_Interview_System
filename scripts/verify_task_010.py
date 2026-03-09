import sys
import os
import cv2
import numpy as np
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from packages.imh_providers.visual.mediapipe_impl import MediaPipeVisualProvider
from packages.imh_providers.visual.dto import VisualResultDTO

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VERIFY_TASK_010")

def create_dummy_image(has_face=False):
    # Create black image
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    if has_face:
        # Draw a simple face? MediaPipe is robust, simple drawing won't trick it easily
        # without landmarks.
        pass
    
    # Encode
    _, buf = cv2.imencode('.jpg', img)
    return buf.tobytes()

def verify():
    logger.info("Initializing MediaPipeVisualProvider...")
    try:
        provider = MediaPipeVisualProvider()
        logger.info("Provider initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize provider: {e}")
        sys.exit(1)

    # Test 1: No Face
    logger.info("Test 1: Analyzing image with NO face...")
    img_bytes = create_dummy_image(has_face=False)
    
    try:
        result = provider.analyze(img_bytes)
        logger.info(f"Result: {result}")
        
        if result.has_face is False and result.presence_score == 0.0:
            logger.info("Test 1 PASSED: Correctly identified no face.")
        else:
            logger.error(f"Test 1 FAILED: Expected has_face=False, got {result.has_face}")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Test 1 Error: {e}")
        sys.exit(1)

    # Test 2: Check DTO Import in API
    logger.info("Test 2: Verifying API module imports...")
    try:
        from IMH.api.playground import router
        logger.info("Test 2 PASSED: IMH.api.playground imported successfully.")
    except Exception as e:
        logger.error(f"Test 2 FAILED: Could not import API router. {e}")
        sys.exit(1)

    logger.info("TASK-010 Verification Completed Successfully.")

if __name__ == "__main__":
    verify()
