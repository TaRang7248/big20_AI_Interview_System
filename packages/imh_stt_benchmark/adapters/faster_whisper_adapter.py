import os
import time
import gc
from typing import Dict, Any, Optional

try:
    import torch
    from faster_whisper import WhisperModel
except ImportError:
    torch = None
    WhisperModel = None

from ..domain import STTEngineProtocol, STTResultDTO
from ..normalization import normalize_text

class FasterWhisperAdapter(STTEngineProtocol):
    def __init__(self, model_size: str = "large-v3-turbo", device: str = "cuda", compute_type: str = "float16", initial_prompt: Optional[str] = None):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.initial_prompt = initial_prompt
        self.model: Optional[WhisperModel] = None

    def load_model(self) -> None:
        if WhisperModel is None:
            raise ImportError("faster-whisper is not installed. Please install it.")
        if self.device == "cuda" and (torch is None or not torch.cuda.is_available()):
            raise RuntimeError("CUDA is not available but device='cuda' was requested. CPU fallback is forbidden.")
            
        # load model
        self.model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
            download_root=os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
        )

    def warmup(self) -> None:
        # Create a dummy silent audio array (16kHz, 1 second)
        import numpy as np
        dummy_audio = np.zeros(16000, dtype=np.float32)
        segments, _ = self.model.transcribe(
            dummy_audio, 
            beam_size=1, 
            language="ko", 
            temperature=0.0
        )
        list(segments) # materialize to force inference

    def transcribe(self, audio_path: str) -> STTResultDTO:
        if self.model is None:
            raise RuntimeError("Model is not loaded. Call load_model() first.")

        # VRAM tracking will be handled by Evaluator's monitor, but we record inference time
        import librosa
        # Load duration
        duration = librosa.get_duration(path=audio_path)
        
        start_time = time.time()
        # Fast Whisper transcribe natively supports loading by path, and standardizes to 16kHz internally.
        # We force Greedy parameters.
        segments, info = self.model.transcribe(
            audio_path,
            beam_size=1,
            language="ko",
            temperature=0.0,
            vad_filter=True, # Use vad to avoid hallucination
            initial_prompt=self.initial_prompt
        )
        
        raw_texts = []
        for segment in segments:
            raw_texts.append(segment.text)
            
        inference_time = time.time() - start_time
        
        raw_text = " ".join(raw_texts).strip()
        normalized = normalize_text(raw_text)

        # Clear cache gently
        if torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()

        return STTResultDTO(
            raw_text=raw_text,
            normalized_text=normalized,
            inference_time_seconds=inference_time,
            audio_duration_seconds=duration,
            rtf=inference_time / duration if duration > 0 else 0,
            peak_vram_mb=0.0, # Handled by evaluator
            metadata={
                "model_name": f"faster-whisper-{self.model_size}",
                "device": self.device,
                "compute_type": self.compute_type,
                "language_probability": info.language_probability
            }
        )

    def unload(self):
        """명시적 메모리 반환"""
        if self.model is not None:
            del self.model
            self.model = None
            gc.collect()
            if torch is not None and torch.cuda.is_available():
                torch.cuda.empty_cache()
