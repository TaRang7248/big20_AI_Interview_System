import asyncio
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from packages.imh_core.config import IMHConfig
from packages.imh_core.dto import LLMMessageDTO
from packages.imh_providers.stt import MockSTTProvider
from packages.imh_providers.llm import MockLLMProvider
from packages.imh_providers.emotion import MockEmotionProvider
from packages.imh_providers.visual import MockVisualProvider
from packages.imh_providers.voice import MockVoiceProvider

async def main():
    print(">>> Verifying TASK-003: Provider Interfaces & Mocks")
    
    # Fake config (using default)
    config = IMHConfig() 
    # Or force mock latency if config supports it, but default is 0 which is fine strictly for structure test.
    # To test latency logic, we can try patching:
    # config.MOCK_LATENCY_MS = 100 # This won't work if pydantic validates or if fields are locked, 
    # but let's assume default config.
    
    # 1. STT
    stt = MockSTTProvider(config)
    transcript = await stt.transcribe("dummy.wav")
    print(f"[STT] Transcribe result: {transcript.text} (segments: {len(transcript.segments)})")
    assert transcript.text == "This is a mock transcription result."
    
    # 2. LLM
    llm = MockLLMProvider(config)
    msgs = [LLMMessageDTO(role="user", content="Hello")]
    resp = await llm.chat(msgs)
    print(f"[LLM] Chat result: {resp.content}")
    assert "mock LLM response" in resp.content
    
    # 3. Emotion
    emotion = MockEmotionProvider(config)
    emo_res = await emotion.analyze_face("dummy.jpg")
    print(f"[Emotion] Result: {emo_res.dominant_emotion}")
    assert emo_res.dominant_emotion == "neutral"
    
    # 4. Visual
    visual = MockVisualProvider(config)
    vis_res = await visual.analyze_frame("dummy.jpg")
    print(f"[Visual] Gaze: {vis_res.gaze_vector}")
    assert len(vis_res.gaze_vector) == 3
    
    # 5. Voice
    voice = MockVoiceProvider(config)
    voice_res = await voice.analyze_audio("dummy.wav")
    print(f"[Voice] Pitch: {voice_res.pitch_mean}")
    assert voice_res.pitch_mean > 0
    
    print("\n>>> ALL MOCK PROVIDERS VERIFIED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(main())
