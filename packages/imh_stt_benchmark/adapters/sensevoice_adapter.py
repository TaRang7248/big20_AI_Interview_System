import os
import time
import gc
from typing import Optional

try:
    import torch
    from funasr import AutoModel
except ImportError:
    torch = None
    AutoModel = None

from ..domain import STTEngineProtocol, STTResultDTO
from ..normalization import normalize_text

class SenseVoiceAdapter(STTEngineProtocol):
    """
    SenseVoiceSmall 모델 어댑터 (FunASR 기반)
    """
    def __init__(self, model_dir: str = "iic/SenseVoiceSmall", device: str = "cuda:0"):
        self.model_dir = model_dir
        self.device = device
        self.model: Optional[AutoModel] = None

    def load_model(self) -> None:
        if AutoModel is None:
            raise ImportError("funasr is not installed.")
        if "cuda" in self.device and (torch is None or not torch.cuda.is_available()):
            raise RuntimeError("CUDA is not available but device was requested as cuda. CPU fallback forbidden.")

        self.model = AutoModel(
            model=self.model_dir,
            device=self.device,
            disable_update=True
        )

    def warmup(self) -> None:
        import numpy as np
        dummy_audio = np.zeros(16000, dtype=np.float32) # 1 sec
        self.model.generate(
            input=dummy_audio,
            cache={},
            language="ko", # force korean
            use_itn=False
        )

    def transcribe(self, audio_path: str) -> STTResultDTO:
        if self.model is None:
            raise RuntimeError("Model is not loaded.")

        import librosa
        duration = librosa.get_duration(path=audio_path)

        start_time = time.time()
        # SenseVoiceSmall generation
        # language='ko' forces Korean output
        # use_itn=False disables inverse text normalization (to keep raw output closer to words, or True to map '이십사'->24 natively)
        # We will use True if possible to let the model normalize digits natively
        res = self.model.generate(
            input=audio_path,
            cache={},
            language="ko",
            use_itn=True 
        )
        inference_time = time.time() - start_time

        if res and len(res) > 0:
            raw_text = res[0].get("text", "")
            # SenseVoice raw output usually comes with formatting <|ko|><|...|> tags, but funasr generate strips them mostly.
            # If there are any leading tags, we might need to strip them.
            import re
            raw_text = re.sub(r'<\|[^\|]+\|>', '', raw_text).strip()
        else:
            raw_text = ""

        normalized = normalize_text(raw_text)

        if torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()

        return STTResultDTO(
            raw_text=raw_text,
            normalized_text=normalized,
            inference_time_seconds=inference_time,
            audio_duration_seconds=duration,
            rtf=inference_time / duration if duration > 0 else 0,
            peak_vram_mb=0.0,
            metadata={
                "model_name": "SenseVoiceSmall",
                "device": self.device
            }
        )

    def unload(self):
        if self.model is not None:
            del self.model
            self.model = None
            gc.collect()
            if torch is not None and torch.cuda.is_available():
                torch.cuda.empty_cache()
