import logging
import time
from typing import Optional, Dict, Any
from .domain import STTEngineProtocol, MetricsResult, TestCase, STTResultDTO
from .metrics import (
    calculate_cer,
    calculate_wer,
    calculate_digit_accuracy,
    calculate_foreign_term_accuracy,
    load_it_terms
)
from .normalization import normalize_text, extract_digits
from .vram_monitor import VRAMMonitor

logger = logging.getLogger(__name__)

class STTEvaluator:
    """
    STTEngineProtocol을 구현하는 STT 엔진을 받아 단일 테스트 케이스를 평가한다.
    GPU VRAM 모니터링 및 5.5GB 초과 시 OOM Skip 처리를 포함한다.
    """
    def __init__(self, engine: STTEngineProtocol, max_vram_mb: float = 5500.0):
        self.engine = engine
        self.max_vram_mb = max_vram_mb
        self.lexicon = load_it_terms()
        self._is_loaded = False

    def _ensure_loaded_and_warmed_up(self):
        try:
            import torch
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA is not available. GTX 1660 Super 환경 보호를 위해 CPU fallback을 금지합니다.")
        except ImportError:
            raise RuntimeError("torch 모듈이 설치되어 있지 않습니다.")

        if not self._is_loaded:
            logger.info("Loading STT model into VRAM...")
            self.engine.load_model()
            logger.info("Running warmup inference...")
            self.engine.warmup()
            self._is_loaded = True

    def evaluate(self, test_case: TestCase) -> Dict[str, Any]:
        """
        단일 오디오 파일에 대해 추론을 수행하고 메트릭을 추출한다.
        """
        self._ensure_loaded_and_warmed_up()
        
        monitor = VRAMMonitor(interval=0.05)
        monitor.start()
        
        error = None
        result_dto: Optional[STTResultDTO] = None
        
        try:
            result_dto = self.engine.transcribe(test_case.audio_path)
        except Exception as e:
            error = str(e)
            logger.error(f"Inference failed for {test_case.audio_path}: {error}")
        finally:
            peak_vram = monitor.stop()
            
        if peak_vram > self.max_vram_mb:
            error = f"OOM: Peak VRAM ({peak_vram:.2f} MB) exceeded cutoff ({self.max_vram_mb} MB)."
            logger.warning(error)

        if error or not result_dto:
            return {
                "audio_path": test_case.audio_path,
                "status": "FAILED",
                "error": error,
                "peak_vram_mb": peak_vram
            }

        # 메트릭 계산
        ref_norm = normalize_text(test_case.ground_truth)
        hyp_norm = result_dto.normalized_text
        
        wer = calculate_wer(ref_norm, hyp_norm)
        cer = calculate_cer(ref_norm, hyp_norm)
        
        ref_digits = extract_digits(test_case.ground_truth)
        hyp_digits = extract_digits(result_dto.raw_text) # 원본 텍스트에서 숫자 추출
        dig_acc = calculate_digit_accuracy(ref_digits, hyp_digits) if ref_digits else None
        
        for_acc = calculate_foreign_term_accuracy(test_case.ground_truth, result_dto.raw_text, self.lexicon)
        
        metrics = MetricsResult(
            wer=wer,
            cer=cer,
            digit_accuracy=dig_acc,
            foreign_term_accuracy=for_acc
        )
        
        return {
            "audio_path": test_case.audio_path,
            "status": "SUCCESS",
            "ground_truth": test_case.ground_truth,
            "raw_text": result_dto.raw_text,
            "normalized_text": result_dto.normalized_text,
            "metrics": metrics.model_dump(),
            "rtf": result_dto.rtf,
            "inference_time_seconds": result_dto.inference_time_seconds,
            "peak_vram_mb": peak_vram,
            "metadata": result_dto.metadata
        }
