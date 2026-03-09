import threading
import time
from typing import Optional

try:
    import torch
except ImportError:
    torch = None

class VRAMMonitor:
    """
    STT 추론 구간 동안 백그라운드 스레드에서 GPU VRAM (Allocated) Peak 치를 모니터링한다.
    """
    def __init__(self, interval: float = 0.05, device_index: int = 0):
        self.interval = interval
        self.device_index = device_index
        self._running = False
        self._peak_vram_bytes = 0
        self._thread: Optional[threading.Thread] = None

    def _monitor_loop(self):
        if torch is None or not torch.cuda.is_available():
            return

        while self._running:
            # 현재 할당된 메모리
            current_allocated = torch.cuda.memory_allocated(self.device_index)
            if current_allocated > self._peak_vram_bytes:
                self._peak_vram_bytes = current_allocated
            time.sleep(self.interval)

    def start(self):
        if torch is None or not torch.cuda.is_available():
            self._peak_vram_bytes = 0
            return
            
        self._peak_vram_bytes = torch.cuda.memory_allocated(self.device_index)
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self) -> float:
        """
        모니터링을 종료하고 측정된 Peak VRAM을 MB 단위로 반환한다.
        """
        self._running = False
        if self._thread is not None:
            self._thread.join()
            
        return self._peak_vram_bytes / (1024 * 1024)
