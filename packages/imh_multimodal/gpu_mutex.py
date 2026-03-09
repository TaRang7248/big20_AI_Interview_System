"""
TASK-M Sprint 3: GPU Mutex Manager (plan §4.1)

Implements:
  - LLM > STT cooperative yield via Redis key lock.
  - Heartbeat-based TTL renewal (every 3s, TTL=10s).
  - Orphan recovery: setnx after 5s wait + TTL expiry check.
  - Soft Degrade Mode: after 3 consecutive yield-failures, STT halves rate.
  - Mutex queue depth limit: MM_MUTEX_QUEUE_MAX (default 10).

Contract:
  - Phase 1 only: Heartbeat + cooperative yield.
  - Incarnation Token: strictly forbidden (Phase 2 scope).
  - LLM priority: LLM ALWAYS wins if it raises LLM_YIELD_REQUEST_KEY.

Usage pattern:
    from packages.imh_multimodal.gpu_mutex import GPUMutexManager
    mgr = GPUMutexManager(redis_client, owner="stt")
    acquired = mgr.try_acquire()
    if acquired:
        # ... run STT ...
        mgr.release()
"""
from __future__ import annotations
import logging
import time
import threading
from typing import Optional

from packages.imh_multimodal.redis_streams import (
    GPU_MUTEX_KEY,
    GPU_MUTEX_TTL_SEC,
    GPU_MUTEX_HEARTBEAT_SEC,
    LLM_YIELD_REQUEST_KEY,
)
from packages.imh_multimodal.mm_flags import MMFlags

logger = logging.getLogger("imh.multimodal.gpu_mutex")

# Retry parameters (plan §4.1)
_LLM_RETRY_INTERVAL_SEC = 0.2   # 200 ms
_LLM_MAX_WAIT_SEC = 5.0
_SOFT_DEGRADE_THRESHOLD = 3     # consecutive fails before Soft Degrade Mode


class GPUMutexManager:
    """
    Manages the shared GPU mutex (gpu_mutex Redis key).

    Args:
        redis_client:  Active Redis client instance.
        owner:         Identifier string: "llm" or "stt".
    """

    def __init__(self, redis_client, owner: str):
        self._r = redis_client
        self._owner = owner
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_stop = threading.Event()
        self._consec_fails: int = 0  # consecutive yield failures for STT
        self._soft_degrade: bool = False

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def try_acquire_stt(self) -> bool:
        """
        STT Worker: attempt to acquire the GPU mutex (non-blocking).

        In Soft Degrade Mode, only attempts every other call (50% rate).
        Returns True if acquired, False if already held.
        """
        if self._soft_degrade:
            # Simple toggle: skip every second call
            self._consec_fails += 1
            if self._consec_fails % 2 == 0:
                logger.debug("STT Soft Degrade: skipping this slot")
                return False

        acquired = self._r.set(GPU_MUTEX_KEY, self._owner, nx=True, ex=GPU_MUTEX_TTL_SEC)
        if acquired:
            self._consec_fails = 0
            self._soft_degrade = False
            self._start_heartbeat()
            logger.debug("GPU mutex acquired by %s", self._owner)
            return True

        # Failed to acquire
        self._consec_fails += 1
        if self._consec_fails >= _SOFT_DEGRADE_THRESHOLD:
            if not self._soft_degrade:
                logger.warning(
                    "STT: %d consecutive mutex failures — entering Soft Degrade Mode",
                    self._consec_fails,
                )
                self._soft_degrade = True
        return False

    def acquire_llm_blocking(self) -> bool:
        """
        LLM Dispatcher: signal yield request then wait up to 5s for the lock.

        1. Write LLM_YIELD_REQUEST_KEY (STT's heartbeat reads this).
        2. Retry every 200 ms for up to 5s.
        3. If still locked after 5s, attempt orphan recovery (setnx after TTL expiry).

        Returns True if lock acquired, False if orphan recovery also failed.

        Plan §4.1 Mutex Queue depth: checked externally by session gate.
        """
        # Signal STT to yield
        self._r.set(LLM_YIELD_REQUEST_KEY, "1", ex=GPU_MUTEX_TTL_SEC)
        deadline = time.monotonic() + _LLM_MAX_WAIT_SEC
        attempt = 0

        while time.monotonic() < deadline:
            acquired = self._r.set(GPU_MUTEX_KEY, self._owner, nx=True, ex=GPU_MUTEX_TTL_SEC)
            if acquired:
                self._r.delete(LLM_YIELD_REQUEST_KEY)
                self._start_heartbeat()
                logger.info("LLM GPU mutex acquired after %d retries", attempt)
                return True
            attempt += 1
            time.sleep(_LLM_RETRY_INTERVAL_SEC)

        # Orphan recovery (plan §4.1): check remaining TTL
        ttl = self._r.ttl(GPU_MUTEX_KEY)
        if ttl <= 0:
            # TTL has expired — orphan lock; force acquire
            acquired = self._r.set(GPU_MUTEX_KEY, self._owner, nx=True, ex=GPU_MUTEX_TTL_SEC)
            if acquired:
                self._r.delete(LLM_YIELD_REQUEST_KEY)
                self._start_heartbeat()
                logger.warning("LLM: orphan GPU mutex recovered via setnx")
                return True

        logger.error("LLM: failed to acquire GPU mutex after %.1fs", _LLM_MAX_WAIT_SEC)
        self._r.delete(LLM_YIELD_REQUEST_KEY)
        return False

    def check_yield_requested(self) -> bool:
        """
        STT heartbeat callback: returns True if LLM has raised yield request.
        STT Worker should call this every heartbeat cycle and release if True.
        """
        return self._r.exists(LLM_YIELD_REQUEST_KEY) == 1

    def release(self) -> None:
        """Release the GPU mutex and stop the heartbeat thread."""
        self._stop_heartbeat()
        try:
            current = self._r.get(GPU_MUTEX_KEY)
            if current == self._owner:
                self._r.delete(GPU_MUTEX_KEY)
                logger.debug("GPU mutex released by %s", self._owner)
        except Exception:
            logger.warning("GPU mutex release failed (non-fatal)", exc_info=True)

    @property
    def soft_degrade_active(self) -> bool:
        return self._soft_degrade

    # ------------------------------------------------------------------ #
    # Heartbeat (internal)                                                  #
    # ------------------------------------------------------------------ #

    def _start_heartbeat(self) -> None:
        """Start background thread that renews lock TTL every 3s."""
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True, name=f"gpu-hb-{self._owner}"
        )
        self._heartbeat_thread.start()

    def _stop_heartbeat(self) -> None:
        self._heartbeat_stop.set()
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=GPU_MUTEX_HEARTBEAT_SEC + 1)

    def _heartbeat_loop(self) -> None:
        """
        Renew lock TTL every GPU_MUTEX_HEARTBEAT_SEC seconds.
        If renewal fails (lock lost), stop immediately.
        If LLM yield signal detected, abort and release.
        """
        while not self._heartbeat_stop.wait(GPU_MUTEX_HEARTBEAT_SEC):
            # Check cooperative yield signal first
            if self.check_yield_requested() and self._owner == "stt":
                logger.info("STT: LLM yield request detected — releasing GPU mutex")
                self._stop_heartbeat()
                self.release()
                return

            # Renew TTL
            try:
                current = self._r.get(GPU_MUTEX_KEY)
                if current != self._owner:
                    logger.warning(
                        "GPU mutex heartbeat: lock lost (owner=%r, expected=%r) — aborting",
                        current, self._owner,
                    )
                    self._heartbeat_stop.set()
                    return
                self._r.expire(GPU_MUTEX_KEY, GPU_MUTEX_TTL_SEC)
            except Exception:
                logger.error("GPU mutex heartbeat renewal failed — aborting", exc_info=True)
                self._heartbeat_stop.set()
                return
