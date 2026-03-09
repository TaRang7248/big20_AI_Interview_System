import cv2
import numpy as np
import mediapipe as mp
import logging
from typing import Dict, Any

from packages.imh_providers.visual.dto import VisualResultDTO

logger = logging.getLogger(__name__)

class MediaPipeVisualProvider:
    """
    Implementation of Visual Analysis using MediaPipe Solutions.
    Adheres to TASK-010 Reproduction Baseline.
    """
    def __init__(self):
        # Initialize MediaPipe solutions
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_pose = mp.solutions.pose
        
        # Consistent configuration (reproduction baseline)
        self.face_config = {
            'static_image_mode': True,
            'max_num_faces': 1,
            'refine_landmarks': True, # For iris/gaze refinement
            'min_detection_confidence': 0.5
        }
        self.pose_config = {
            'static_image_mode': True,
            'model_complexity': 1, # Balanced model
            'enable_segmentation': False,
            'min_detection_confidence': 0.5
        }

    def analyze(self, image_bytes: bytes) -> VisualResultDTO:
        try:
            # Decode image
            nparr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                 raise ValueError("Failed to decode image bytes")

            # MediaPipe needs RGB
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            h, w, _ = image.shape

            # 1. Face Analysis (Presence & Attention)
            has_face = False
            is_looking_center = False
            attention_score = 0.0
            presence_score = 0.0
            face_metadata = {}

            with self.mp_face_mesh.FaceMesh(**self.face_config) as face_mesh:
                results = face_mesh.process(image_rgb)
                
                if results.multi_face_landmarks:
                    has_face = True
                    presence_score = 1.0
                    face_landmarks = results.multi_face_landmarks[0]
                    
                    # Attention Logic: Simple Yaw Estimation
                    # Points: Nose tip (1), Left Eye (33), Right Eye (263)
                    src_pts = [
                        face_landmarks.landmark[1],   # Nose tip
                        face_landmarks.landmark[33],  # LP Eye
                        face_landmarks.landmark[263]  # RP Eye
                    ]
                    
                    # x coordinates
                    nose_x = src_pts[0].x
                    left_eye_x = src_pts[1].x
                    right_eye_x = src_pts[2].x 
                    
                    # Calculate horizontal offset relative to eye width
                    eye_width = abs(right_eye_x - left_eye_x)
                    if eye_width > 0:
                        mid_eye_x = (left_eye_x + right_eye_x) / 2
                        yaw_offset = abs(nose_x - mid_eye_x) / eye_width
                        
                        # Threshold for "looking center"
                        # 0.0 = perfect center. 0.3 allow deviation.
                        if yaw_offset < 0.3: 
                            is_looking_center = True
                            attention_score = max(0.0, 1.0 - (yaw_offset / 0.3))
                        else:
                            is_looking_center = False
                            # Score drops as offset increases
                            attention_score = max(0.0, 1.0 - (yaw_offset / 0.5))
                            
                        face_metadata["yaw_offset"] = float(yaw_offset)
                    
                    # Add face rectangle for verification
                    face_metadata["face_detected_score"] = float(1.0) # implicit

            # 2. Pose Analysis (Posture)
            # Only run if face is detected to save resource if "Absence" is already determined?
            # Plan says "Presence/Absence is priority". But if Face is there, we verify pose.
            is_posture_good = False
            pose_score = 0.0
            pose_metadata = {}
            
            if has_face:
                with self.mp_pose.Pose(**self.pose_config) as pose:
                    results_pose = pose.process(image_rgb)
                    
                    if results_pose.pose_landmarks:
                        landmarks = results_pose.pose_landmarks.landmark
                        left_shoulder = landmarks[11]
                        right_shoulder = landmarks[12]
                        
                        # Check visibility
                        if left_shoulder.visibility > 0.5 and right_shoulder.visibility > 0.5:
                            # Check tilt
                            dy = abs(left_shoulder.y - right_shoulder.y)
                            dx = abs(left_shoulder.x - right_shoulder.x)
                            
                            width = dx if dx > 0 else 0.001
                            tilt = dy / width
                            
                            # Threshold for "Good Posture" (Shoulders level)
                            if tilt < 0.2:
                                is_posture_good = True
                                pose_score = max(0.0, 1.0 - (tilt / 0.2))
                            else:
                                is_posture_good = False
                                pose_score = max(0.0, 1.0 - (tilt / 0.4))
                            
                            pose_metadata["shoulder_tilt"] = float(tilt)
                        else:
                            # Shoulders not visible
                            is_posture_good = False
                            pose_score = 0.0
                            pose_metadata["shoulder_visible"] = False

            return VisualResultDTO(
                has_face=has_face,
                presence_score=presence_score,
                attention_score=attention_score,
                pose_score=pose_score,
                is_looking_center=is_looking_center,
                is_posture_good=is_posture_good,
                metadata={**face_metadata, **pose_metadata}
            )

        except Exception as e:
            logger.error(f"Visual Analysis Failed: {str(e)}")
            # Fail-safe: Return "Absence" state rather than crash, 
            # OR re-raise if it's a system error? 
            # Plan: "데이터가 없으면(No Face) null이나 오류를 뱉는 것이 아니라... 부재 상태 반환"
            # But if decoding fails, that's an error.
            # If MediaPipe crash, that's an error. 
            # I will re-raise system errors, but logic errors (no face) are handled above.
            raise e
