import time
import gc
from typing import Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from ..domain import STTEngineProtocol, STTResultDTO
from ..normalization import normalize_text
import os

class WhisperAPIAdapter(STTEngineProtocol):
    """
    OpenAI Whisper API 어댑터 (Baseline용)
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.client: Optional[OpenAI] = None

    def load_model(self) -> None:
        if OpenAI is None:
            raise ImportError("openai package is not installed.")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set.")
            
        self.client = OpenAI(api_key=self.api_key)

    def warmup(self) -> None:
        # API is serverless, no local warmup needed but we can do a ping if we want.
        # Skip to save cost.
        pass

    def transcribe(self, audio_path: str) -> STTResultDTO:
        if self.client is None:
            raise RuntimeError("Client is not initialized.")

        import librosa
        duration = librosa.get_duration(path=audio_path)

        start_time = time.time()
        
        with open(audio_path, "rb") as audio_file:
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ko", # force ko
                temperature=0.0, # greedy
                response_format="text"
            )
            
        inference_time = time.time() - start_time

        raw_text = str(transcript).strip()
        normalized = normalize_text(raw_text)

        return STTResultDTO(
            raw_text=raw_text,
            normalized_text=normalized,
            inference_time_seconds=inference_time,
            audio_duration_seconds=duration,
            rtf=inference_time / duration if duration > 0 else 0,
            peak_vram_mb=0.0, # Cloud API uses no local VRAM
            metadata={
                "model_name": "Whisper-1-API",
                "device": "Cloud"
            }
        )

    def unload(self):
        pass
