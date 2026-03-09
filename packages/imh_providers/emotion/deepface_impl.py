import cv2
import numpy as np
from deepface import DeepFace
import logging
import os

from packages.imh_providers.emotion.base import IEmotionProvider
from packages.imh_core.dto import EmotionResultDTO
from packages.imh_providers.emotion.dto import (
    VideoEmotionAnalysisResultDTO, 
    FrameEmotionDTO, 
    VideoEmotionAnalysisMetadataDTO, 
    EmotionScoreDTO
)
from packages.imh_core.config import IMHConfig

logger = logging.getLogger(__name__)

class DeepFaceEmotionProvider(IEmotionProvider):
    def __init__(self, config: IMHConfig = None):
        self.config = config
        # Initial load or check could happen here, but DeepFace lazy loads models usually.

    async def analyze_face(self, image_path: str) -> EmotionResultDTO:
        try:
            # enforce_detection=True raises ValueError if no face found
            # actions=['emotion']
            objs = DeepFace.analyze(
                img_path=image_path, 
                actions=['emotion'], 
                enforce_detection=True,
                detector_backend='opencv'
            )
            
            # DeepFace returns a list of results. We take the first one (most dominant face usually if alignment logic works)
            # Or we could pick the one with largest region. Default DeepFace behavior returns all detected faces.
            # We assume single face for now as per common use case, or pick the first.
            if not objs:
                raise ValueError("No face detected")
            
            result = objs[0]
            
            return EmotionResultDTO(
                dominant_emotion=result['dominant_emotion'],
                scores=result['emotion'],
                region=result['region']
            )
        except ValueError as e:
            # Face not detected
            # For header interface compliance, we might need to handle this or let it bubble.
            # But EmotionResultDTO expects dominant_emotion. 
            # If no face, we can't return valid emotion.
            # Plan says for VIDEO "face_detected: false". For single image, it's likely an error or N/A.
            # But analyze_face return type is EmotionResultDTO which mandates fields.
            # We will raise for single image if no face, let caller handle.
            raise e
        except Exception as e:
            logger.error(f"DeepFace analyze_face error: {e}")
            raise e

    async def analyze_video(self, video_path: str) -> VideoEmotionAnalysisResultDTO:
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        
        # 1 frame per second
        # If fps is 30, we want frame 0, 30, 60...
        sample_interval = int(round(fps)) if fps >= 1 else 1
        
        results: list[FrameEmotionDTO] = []
        analyzed_count = 0
        
        try:
            current_frame_idx = 0
            while current_frame_idx < total_frames:
                cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_idx)
                ret, frame = cap.read()
                
                if not ret:
                    break
                
                timestamp = current_frame_idx / fps if fps > 0 else 0
                
                # Analyze frame
                # DeepFace expects path or numpy array (BGR is fine for opencv backend?)
                # DeepFace uses RGB usually, OpenCV uses BGR. 
                # DeepFace.analyze internal logic handles BGR->RGB conversion if numpy array is passed?
                # Actually DeepFace docs say: "OpenCV expects BGR but DeepFace expects RGB".
                # We should convert.
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                frame_result_dto = FrameEmotionDTO(
                    timestamp=timestamp,
                    face_detected=False
                )
                
                try:
                    # detector_backend='opencv' is fast (cpu friendly)
                    # enforce_detection=True to get exception if no face
                    objs = DeepFace.analyze(
                        img_path=rgb_frame,
                        actions=['emotion'],
                        enforce_detection=True,
                        detector_backend='opencv',
                        silent=True # Suppress logs
                    )
                    
                    if objs:
                        # Take the first face (or largest)
                        # DeepFace sorts by size? Not guaranteed. 
                        # Ideally we pick largest face.
                        # obj['region'] = {'x':, 'y':, 'w':, 'h':}
                        
                        # Let's find max area face
                        main_face = max(objs, key=lambda x: x['region']['w'] * x['region']['h'])
                        
                        frame_result_dto.face_detected = True
                        frame_result_dto.dominant_emotion = main_face['dominant_emotion']
                        frame_result_dto.emotion_scores = EmotionScoreDTO(**main_face['emotion'])
                        frame_result_dto.box = [
                            main_face['region']['x'],
                            main_face['region']['y'],
                            main_face['region']['w'],
                            main_face['region']['h']
                        ]
                        
                except ValueError:
                    # No face detected
                    frame_result_dto.face_detected = False
                except Exception as e:
                    logger.warning(f"Error analyzing frame at {timestamp}s: {e}")
                    # We treat error as no face detected or just skip? 
                    # Plan says "얼굴 미검출... 에러 아님". 
                    # If other error, maybe log and continue.
                    pass
                
                results.append(frame_result_dto)
                analyzed_count += 1
                
                # Move to next second
                current_frame_idx += sample_interval
                
        finally:
            cap.release()
            
        return VideoEmotionAnalysisResultDTO(
            metadata=VideoEmotionAnalysisMetadataDTO(
                total_duration=duration,
                total_frames_analyzed=analyzed_count,
                model="DeepFace (opencv)"
            ),
            results=results
        )
