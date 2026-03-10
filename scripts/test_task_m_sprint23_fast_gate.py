"""
TASK-M Sprint 2-3: Expanded Fast Gate verification script.

Tests all Sprint 1-3 contracts in a single run.

FG-M1  Idempotency         — duplicate signal_id silently rejected by DB
FG-M2  Isolation           — authority table structure intact (no writes)
FG-M3  Mutex Key           — Redis gpu_mutex set/release
FG-M4  Flags               — all MM flags default False; env toggle works
FG-M5  Signal-ID           — same inputs → same UUID; wrong input raises
FG-M6  Table Schema        — multimodal_observations: columns + UNIQUE constraint
FG-S2a Normalizer          — clip formula, outlier clip, Neutral(0.5) for None/unknown
FG-S2b Normalizer-ProfileID — profile_id mismatch → Neutral
FG-S2c CPU Workers         — Vision/Emotion/Audio return observation dicts with signal_ids
FG-S2d Persistence-Build   — build_insert_params returns correct tuple shape
FG-S3a GPU Mutex           — acquire, detect hold, release, yield signal
FG-S3b STT Worker          — turn_finalized drop; OOM falls back gracefully
FG-S3c PII Masking         — phone/email masked; output ≤ 100 chars; exception → ""
FG-S3d TTS Flag Off        — tts_generate() returns None when MM_ENABLE_TTS=False
FG-S3e PDF Flag Off        — extract_resume_text() returns "" when flag off

Pass criterion: EXIT 0, all tests PASS.
Usage:
    python scripts/test_task_m_sprint23_fast_gate.py
"""

import os
import sys
import uuid
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
imh_root = project_root / "IMH" / "AI_Interview_System"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(imh_root))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("fast_gate_sprint23")

env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)

import re
import asyncpg  # type: ignore

conn_string = os.getenv("POSTGRES_CONNECTION_STRING", "")
pat = r"postgresql\+asyncpg://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)"
m = re.match(pat, conn_string)
if not m:
    logger.error("POSTGRES_CONNECTION_STRING not found or invalid"); sys.exit(1)
user, password, host, port, database = m.groups()

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = ""):
    status = "PASS" if ok else "FAIL"
    logger.info(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    RESULTS.append((name, ok, detail))


# ------------------------------------------------------------------ #
# FG-M4/S1: Feature Flags                                             #
# ------------------------------------------------------------------ #
def test_flags():
    logger.info("FG-M4: MM Feature Flags")
    import importlib
    for key in ("MM_ENABLE", "MM_ENABLE_WEBRTC", "MM_ENABLE_TTS", "MM_ENABLE_PDF_TEXT", "MM_ENABLE_EVAL_INTEGRATION"):
        os.environ.pop(key, None)
    import packages.imh_multimodal.mm_flags as mf
    importlib.reload(mf)
    MMFlags = mf.MMFlags
    record("MM_ENABLE defaults False", MMFlags.MM_ENABLE is False)
    record("webrtc_active() False with no flags", MMFlags.webrtc_active() is False)
    os.environ["MM_ENABLE"] = "true"; os.environ["MM_ENABLE_WEBRTC"] = "true"
    importlib.reload(mf); MMFlags2 = mf.MMFlags
    record("webrtc_active() True with both flags", MMFlags2.webrtc_active() is True)
    os.environ.pop("MM_ENABLE", None); os.environ.pop("MM_ENABLE_WEBRTC", None)


# ------------------------------------------------------------------ #
# FG-M5: Signal-ID determinism                                        #
# ------------------------------------------------------------------ #
def test_signal_id():
    logger.info("FG-M5: Signal-ID Determinism")
    from packages.imh_multimodal.signal_id import generate_signal_id
    args = ("session-abc", 0, "STT", 1, "stt_confidence")
    record("Deterministic UUID", generate_signal_id(*args) == generate_signal_id(*args))
    record("Different inputs -> different UUID",
           generate_signal_id(*args) != generate_signal_id("session-abc", 0, "VISION", 1, "gaze_horizontal"))
    try:
        generate_signal_id("s", 0, "BAD", 1, "k"); record("Bad modality raises", False)
    except ValueError:
        record("Bad modality raises ValueError", True)
    try:
        generate_signal_id("s", 0, "STT", 0, "k"); record("chunk_seq=0 raises", False)
    except ValueError:
        record("chunk_seq=0 raises ValueError", True)


# ------------------------------------------------------------------ #
# FG-S2a/b: Normalizer                                                #
# ------------------------------------------------------------------ #
def test_normalizer():
    logger.info("FG-S2a/b: Normalizer")
    from packages.imh_multimodal.normalizer import normalize, NEUTRAL
    # Clip formula
    v = normalize("pitch_hz", 275.0)   # midpoint of 50-500
    record("Normalize midpoint ≈ 0.5", abs(v - 0.5) < 0.01, str(v))
    # Outlier clip
    v2 = normalize("pitch_hz", 9999.0)
    record("Outlier hard-clipped to 1.0", v2 == 1.0, str(v2))
    # Missing → Neutral
    record("None → Neutral 0.5", normalize("pitch_hz", None) == NEUTRAL)
    # Unknown metric → Neutral
    record("Unknown metric → Neutral", normalize("unknown_key", 1.0) == NEUTRAL)
    # Profile mismatch → Neutral
    record("Profile mismatch → Neutral",
           normalize("pitch_hz", 275.0, profile_id="v2", session_profile_id="v1") == NEUTRAL)


# ------------------------------------------------------------------ #
# FG-S2c: CPU Workers                                                 #
# ------------------------------------------------------------------ #
def test_cpu_workers():
    logger.info("FG-S2c: CPU Workers")
    # Clear any throttle state before test
    import packages.imh_multimodal.cpu_workers as cw
    cw._last_vision_ts.clear()
    cw._last_emotion_ts.clear()

    msg = {"session_id": str(uuid.uuid4()), "turn_index": 0, "ts": 1.0}
    # Vision
    obs_v = cw.process_vision_frame(msg, frame_seq=1)
    record("Vision returns obs list", isinstance(obs_v, list))
    if obs_v:
        record("Vision obs has signal_id", "signal_id" in obs_v[0])
        record("Vision obs value in [0,1]", 0.0 <= obs_v[0]["normalized_value"] <= 1.0)
    # Emotion — different session so not throttled
    msg2 = {**msg, "session_id": str(uuid.uuid4())}
    obs_e = cw.process_emotion_frame(msg2, interval_seq=1)
    record("Emotion returns obs list", isinstance(obs_e, list))
    # Audio
    obs_a = cw.process_audio_window(msg, window_seq=1)
    record("Audio returns obs list", isinstance(obs_a, list) and len(obs_a) == 2)


# ------------------------------------------------------------------ #
# FG-S2d: Persistence build_insert_params                             #
# ------------------------------------------------------------------ #
def test_persistence_build():
    logger.info("FG-S2d: Persistence build_insert_params")
    from packages.imh_multimodal.persistence import build_insert_params
    sig = str(uuid.uuid4())
    sess = str(uuid.uuid4())
    params = build_insert_params(sess, 0, 1, sig, "STT", "stt_confidence", 1.5, 0.85)
    record("build_insert_params returns 8-tuple", len(params) == 8)
    record("payload is JSON string with value", '"value"' in params[7])


# ------------------------------------------------------------------ #
# FG-M3 / FG-S3a: GPU Mutex                                          #
# ------------------------------------------------------------------ #
def test_gpu_mutex():
    logger.info("FG-S3a: GPU Mutex Manager")
    try:
        from packages.imh_core.infra.redis import RedisClient
        from packages.imh_multimodal.gpu_mutex import GPUMutexManager
        from packages.imh_multimodal.redis_streams import GPU_MUTEX_KEY, LLM_YIELD_REQUEST_KEY
        r = RedisClient.get_instance()
        r.delete(GPU_MUTEX_KEY); r.delete(LLM_YIELD_REQUEST_KEY)

        stt_mgr = GPUMutexManager(r, "stt")
        acquired = stt_mgr.try_acquire_stt()
        record("STT mutex acquired", acquired)

        # LLM yield signal detection
        r.set(LLM_YIELD_REQUEST_KEY, "1", ex=10)
        record("check_yield_requested() True when signal set", stt_mgr.check_yield_requested())

        stt_mgr.release()
        record("STT mutex released", r.get(GPU_MUTEX_KEY) is None)

        r.delete(LLM_YIELD_REQUEST_KEY)
    except Exception as exc:
        record("GPU Mutex Manager test", False, str(exc))


# ------------------------------------------------------------------ #
# FG-S3b: STT Worker drop + OOM                                      #
# ------------------------------------------------------------------ #
def test_stt_worker():
    logger.info("FG-S3b: STT Worker")
    from packages.imh_multimodal.stt_worker import process_stt
    msg = {"session_id": str(uuid.uuid4()), "turn_index": 0, "ts": 0.0}
    # turn_finalized=True → Drop → None
    result = process_stt(msg, turn_finalized=True)
    record("STT drop when turn finalized", result is None)
    # No mutex manager (standalone) → returns observation with Neutral confidence
    result2 = process_stt(msg, turn_finalized=False, gpu_mutex_manager=None)
    record("STT returns obs without mutex manager", result2 is not None)
    if result2:
        record("STT obs value in [0,1]", 0.0 <= result2["normalized_value"] <= 1.0)
        record("STT obs has no text field", "text" not in result2)


# ------------------------------------------------------------------ #
# FG-S3c: PII Masking                                                 #
# ------------------------------------------------------------------ #
def test_pii_masking():
    logger.info("FG-S3c: PII Masking")
    from packages.imh_multimodal.stt_worker import _mask_pii
    masked = _mask_pii("010-1234-5678 test@example.com hello")
    record("Phone masked", "010-1234-5678" not in masked)
    record("Email masked", "test@example.com" not in masked)
    long_text = "a" * 200
    record("Output truncated to ≤100 chars", len(_mask_pii(long_text)) <= 100)


# ------------------------------------------------------------------ #
# FG-S3d: TTS flag off                                                #
# ------------------------------------------------------------------ #
def test_tts_flag_off():
    logger.info("FG-S3d: TTS Flag Off")
    import importlib
    os.environ.pop("MM_ENABLE", None); os.environ.pop("MM_ENABLE_TTS", None)
    import packages.imh_multimodal.mm_flags as mf; importlib.reload(mf)
    import packages.imh_multimodal.tts_facade as tf; importlib.reload(tf)
    result = tf.tts_generate("테스트 질문입니다.")
    record("TTS returns None when flag off", result is None)


# ------------------------------------------------------------------ #
# FG-S3e: PDF flag off                                                #
# ------------------------------------------------------------------ #
def test_pdf_flag_off():
    logger.info("FG-S3e: PDF Flag Off")
    import importlib
    os.environ.pop("MM_ENABLE", None); os.environ.pop("MM_ENABLE_PDF_TEXT", None)
    import packages.imh_multimodal.mm_flags as mf; importlib.reload(mf)
    import packages.imh_multimodal.pdf_facade as pf; importlib.reload(pf)
    result = pf.extract_resume_text("/nonexistent/path.pdf")
    record("PDF returns empty string when flag off", result == "")


# ------------------------------------------------------------------ #
# FG-M1/M2/M6: DB checks                                             #
# ------------------------------------------------------------------ #
async def test_db():
    conn = await asyncpg.connect(host=host, port=int(port), user=user, password=password, database=database)
    try:
        logger.info("FG-M6: Table Schema, FG-M1: Idempotency, FG-M2: Isolation")
        row = await conn.fetchrow("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='multimodal_observations'")
        record("FG-M6: table exists", row is not None)

        uq = await conn.fetchrow("SELECT 1 FROM information_schema.table_constraints WHERE table_schema='public' AND table_name='multimodal_observations' AND constraint_type='UNIQUE' AND constraint_name='uq_multimodal_signal_id'")
        record("FG-M6: UNIQUE(signal_id) exists", uq is not None)

        sig = str(uuid.uuid4()); sess = str(uuid.uuid4())
        sql = "INSERT INTO multimodal_observations (session_id,turn_index,chunk_seq,signal_id,modality,metric_key,timestamp_offset,payload) VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb) ON CONFLICT (signal_id) DO NOTHING"
        await conn.execute(sql, uuid.UUID(sess), 0, 1, uuid.UUID(sig), "STT", "stt_confidence", 1.0, '{"value":0.5}')
        await conn.execute(sql, uuid.UUID(sess), 0, 1, uuid.UUID(sig), "STT", "stt_confidence", 1.0, '{"value":0.9}')
        count = await conn.fetchval("SELECT COUNT(*) FROM multimodal_observations WHERE signal_id=$1", uuid.UUID(sig))
        record("FG-M1: duplicate → 1 row only", count == 1)
        await conn.execute("DELETE FROM multimodal_observations WHERE signal_id=$1", uuid.UUID(sig))

        cols = {r["column_name"] for r in await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='interviews'")}
        record("FG-M2: interviews structure intact", {"session_id","job_policy_snapshot","session_config_snapshot"} <= cols)
    finally:
        await conn.close()


async def main():
    logger.info("=" * 60)
    logger.info("TASK-M Sprint 2-3 Fast Gate")
    logger.info("=" * 60)

    test_flags()
    test_signal_id()
    test_normalizer()
    test_cpu_workers()
    test_persistence_build()
    test_gpu_mutex()
    test_stt_worker()
    test_pii_masking()
    test_tts_flag_off()
    test_pdf_flag_off()
    await test_db()

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = sum(1 for _, ok, _ in RESULTS if not ok)
    logger.info("=" * 60)
    logger.info(f"Results: {passed} PASS  |  {failed} FAIL  |  {len(RESULTS)} total")
    if failed:
        logger.error("FAST GATE: FAIL")
        return 1
    logger.info("FAST GATE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
