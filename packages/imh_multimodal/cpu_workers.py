"""
TASK-M Sprint 2: CPU Workers — Vision, Emotion, Audio analysis stubs.

Design rules (plan §4.3):
  Vision (MediaPipe):   2-3 FPS max. Interval-based frame skip.
  Emotion (DeepFace):   < 1 FPS max. Variable interval (on-motion).
  Audio  (Parselmouth): 2-3 second fixed window.

Each worker:
  1. Receives a Redis Streams message dict (from XREADGROUP).
  2. Performs analysis on the provided artifact (buffer_ref_id or artifact_id).
  3. Normalizes the result via normalizer.normalize().
  4. Builds a signal_id via signal_id.generate_signal_id().
  5. Returns a list of observation dicts for Persistence Worker.

Sprint 2 status: STUB — analysis calls are no-ops returning synthetic values.
                 Sprint 3 wires real library calls.

Isolation contract (plan §9.1):
  - Workers MUST NOT access redis session state or snapshots.
  - Workers MUST NOT write to interviews / evaluation_scores.
  - Workers use only stream payload data + their own analysis result.
"""
from __future__ import annotations
import logging
import time
from typing import Optional

from packages.imh_multimodal.normalizer import normalize, DEFAULT_PROFILE_ID
from packages.imh_multimodal.signal_id import generate_signal_id

logger = logging.getLogger("imh.multimodal.cpu_workers")

# ------------------------------------------------------------------ #
# Shared helper                                                        #
# ------------------------------------------------------------------ #

def _make_obs(
    session_id: str,
    turn_index: int,
    chunk_seq: int,
    modality: str,
    metric_key: str,
    timestamp_offset: float,
    raw_value: Optional[float],
    profile_id: str = DEFAULT_PROFILE_ID,
    session_profile_id: Optional[str] = None,
    extra: Optional[dict] = None,
) -> dict:
    """Build a single observation dict for the Persistence Worker."""
    norm = normalize(metric_key, raw_value, profile_id, session_profile_id)
    sig = generate_signal_id(session_id, turn_index, modality, chunk_seq, metric_key)
    return {
        "session_id": session_id,
        "turn_index": turn_index,
        "chunk_seq": chunk_seq,
        "signal_id": sig,
        "modality": modality,
        "metric_key": metric_key,
        "timestamp_offset": timestamp_offset,
        "normalized_value": norm,
        "extra_payload": extra,
    }


# ------------------------------------------------------------------ #
# Vision Worker — MediaPipe gaze (2-3 FPS max)                        #
# ------------------------------------------------------------------ #
_VISION_INTERVAL_SEC = 0.4   # ≈ 2.5 FPS ceiling
_last_vision_ts: dict[str, float] = {}


def process_vision_frame(
    message: dict,
    frame_seq: int,
) -> list[dict]:
    """
    Process one video frame from the Redis Streams payload.

    message keys: session_id, turn_index, ts (epoch float), profile_id,
                  session_profile_id, [buffer_ref_id | artifact_id]

    Returns list of observation dicts (may be empty if frame was skipped).

    Sprint 2: returns synthetic gaze values (stub).
    """
    session_id = message["session_id"]
    now = time.monotonic()
    last = _last_vision_ts.get(session_id, 0.0)

    # Interval-based frame skip (plan §4.3)
    if now - last < _VISION_INTERVAL_SEC:
        return []
    _last_vision_ts[session_id] = now

    turn_index = int(message["turn_index"])
    ts_offset = float(message.get("ts", 0.0))
    profile_id = message.get("profile_id", DEFAULT_PROFILE_ID)
    session_profile_id = message.get("session_profile_id")

    # Real MediaPipe gaze analysis
    raw_gaze_h: Optional[float] = None
    raw_gaze_v: Optional[float] = None
    artifact = message.get("buffer_ref_id") or message.get("artifact_id")
    if artifact:
        try:
            import cv2  # type: ignore
            import mediapipe as mp  # type: ignore
            import numpy as np  # type: ignore

            # artifact here is expected to be a base64 JPEG or a filepath
            if isinstance(artifact, str) and artifact.endswith((".jpg", ".jpeg", ".png")):
                frame_bgr = cv2.imread(artifact)
            else:
                # Try numpy decode from bytes if passed as buffer path token
                frame_bgr = None

            if frame_bgr is not None:
                with mp.solutions.face_mesh.FaceMesh(
                    static_image_mode=True, max_num_faces=1, refine_landmarks=True
                ) as face_mesh:
                    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                    result = face_mesh.process(rgb)
                    if result.multi_face_landmarks:
                        lms = result.multi_face_landmarks[0].landmark
                        # Left iris (468) vs right iris (473) centroid x-diff → gaze horizontal
                        left_x = lms[468].x
                        right_x = lms[473].x
                        raw_gaze_h = (left_x - right_x) * 60.0 - 30.0  # rough mapping → [-30, 30]
                        raw_gaze_v = (lms[468].y - 0.5) * 40.0         # rough mapping → [-20, 20]
        except Exception as exc:
            logger.debug("Vision MediaPipe analysis failed (fallback Neutral): %s", exc)

    obs = []
    for seq_offset, (metric_key, raw) in enumerate(
        [("gaze_horizontal", raw_gaze_h), ("gaze_vertical", raw_gaze_v)], start=0
    ):
        obs.append(_make_obs(
            session_id=session_id,
            turn_index=turn_index,
            chunk_seq=frame_seq * 10 + seq_offset + 1,  # unique within turn
            modality="VISION",
            metric_key=metric_key,
            timestamp_offset=ts_offset,
            raw_value=raw,
            profile_id=profile_id,
            session_profile_id=session_profile_id,
        ))

    logger.debug("Vision frame processed: session=%s turn=%d frame=%d", session_id, turn_index, frame_seq)
    return obs


# ------------------------------------------------------------------ #
# Emotion Worker — DeepFace (<1 FPS, on-motion)                        #
# ------------------------------------------------------------------ #
_EMOTION_INTERVAL_SEC = 1.5  # <1 FPS
_last_emotion_ts: dict[str, float] = {}


def process_emotion_frame(
    message: dict,
    interval_seq: int,
) -> list[dict]:
    """
    Process one emotion analysis window.

    Sprint 2: returns stub Neutral(0.5) for all emotion metrics.
    Sprint 3: wires DeepFace.analyze() call.
    """
    session_id = message["session_id"]
    now = time.monotonic()
    last = _last_emotion_ts.get(session_id, 0.0)

    if now - last < _EMOTION_INTERVAL_SEC:
        return []
    _last_emotion_ts[session_id] = now

    turn_index = int(message["turn_index"])
    ts_offset = float(message.get("ts", 0.0))
    profile_id = message.get("profile_id", DEFAULT_PROFILE_ID)
    session_profile_id = message.get("session_profile_id")

    # Real DeepFace emotion analysis
    raw_happy: Optional[float] = None
    raw_neutral: Optional[float] = None
    artifact = message.get("buffer_ref_id") or message.get("artifact_id")
    if artifact:
        try:
            from deepface import DeepFace  # type: ignore
            results = DeepFace.analyze(
                artifact,
                actions=["emotion"],
                enforce_detection=False,
                silent=True,
            )
            if results:
                emotions = results[0].get("emotion", {})
                total = sum(emotions.values()) or 1.0
                raw_happy = emotions.get("happy", 0.0) / total
                raw_neutral = emotions.get("neutral", 0.0) / total
        except Exception as exc:
            logger.debug("Emotion DeepFace analysis failed (fallback Neutral): %s", exc)

    obs = []
    for seq_offset, (metric_key, raw) in enumerate(
        [("emotion_happy", raw_happy), ("emotion_neutral", raw_neutral)], start=0
    ):
        obs.append(_make_obs(
            session_id=session_id,
            turn_index=turn_index,
            chunk_seq=interval_seq * 10 + seq_offset + 1,
            modality="EMOTION",
            metric_key=metric_key,
            timestamp_offset=ts_offset,
            raw_value=raw,
            profile_id=profile_id,
            session_profile_id=session_profile_id,
        ))

    logger.debug("Emotion frame processed: session=%s turn=%d interval=%d", session_id, turn_index, interval_seq)
    return obs


# ------------------------------------------------------------------ #
# Audio Worker — Parselmouth (2-3s window)                             #
# ------------------------------------------------------------------ #
_AUDIO_WINDOW_SEC = 2.5


def process_audio_window(
    message: dict,
    window_seq: int,
) -> list[dict]:
    """
    Process one audio analysis window (2-3 sec).

    message keys: same as Vision + buffer_ref_id or artifact_id pointing
                  to the window audio buffer.

    Sprint 2: returns stub Neutral values for pitch_hz and intensity_db.
    Sprint 3: wires Parselmouth analysis on the audio buffer.
    """
    session_id = message["session_id"]
    turn_index = int(message["turn_index"])
    ts_offset = float(message.get("ts", 0.0))
    profile_id = message.get("profile_id", DEFAULT_PROFILE_ID)
    session_profile_id = message.get("session_profile_id")

    # Real Parselmouth audio analysis
    raw_pitch: Optional[float] = None
    raw_intensity: Optional[float] = None
    artifact = message.get("buffer_ref_id") or message.get("artifact_id")
    if artifact:
        try:
            import parselmouth  # type: ignore
            import numpy as np  # type: ignore

            snd = parselmouth.Sound(artifact)
            pitch_obj = snd.to_pitch()
            pitch_values = pitch_obj.selected_array["frequency"]
            voiced = pitch_values[pitch_values > 0]
            raw_pitch = float(np.mean(voiced)) if len(voiced) > 0 else None

            intensity_obj = snd.to_intensity()
            raw_intensity = float(np.mean(intensity_obj.values)) if intensity_obj.n_frames > 0 else None
        except Exception as exc:
            logger.debug("Audio Parselmouth analysis failed (fallback Neutral): %s", exc)

    obs = []
    for seq_offset, (metric_key, raw) in enumerate(
        [("pitch_hz", raw_pitch), ("intensity_db", raw_intensity)], start=0
    ):
        obs.append(_make_obs(
            session_id=session_id,
            turn_index=turn_index,
            chunk_seq=window_seq * 10 + seq_offset + 1,
            modality="AUDIO",
            metric_key=metric_key,
            timestamp_offset=ts_offset,
            raw_value=raw,
            profile_id=profile_id,
            session_profile_id=session_profile_id,
        ))

    logger.debug("Audio window processed: session=%s turn=%d window=%d", session_id, turn_index, window_seq)
    return obs
