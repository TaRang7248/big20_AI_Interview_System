import os
import asyncio
import logging
import parselmouth
from parselmouth.praat import call
from packages.imh_providers.voice.base import IVoiceProvider
from packages.imh_core.dto import VoiceResultDTO

# Set up logging
logger = logging.getLogger("imh.providers.voice.parselmouth")

class ParselmouthVoiceProvider(IVoiceProvider):
    async def analyze_audio(self, audio_path: str) -> VoiceResultDTO:
        """
        Analyze audio file using Parselmouth (Praat).
        Extracts Pitch, Intensity, Jitter, Shimmer, and HNR.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        try:
            # Run CPU-bound analysis in a thread pool to avoid blocking the event loop
            return await asyncio.to_thread(self._analyze_sync, audio_path)
            
        except Exception as e:
            logger.exception(f"Failed to analyze audio file: {audio_path}")
            # Return empty result or re-raise depending on policy.
            # Plan says: "Exception handling: ... return HTTP 422 if damaged"
            # But the provider interface returns DTO. 
            # We will let the exception propagate to be handled by the API layer 
            # or return a partial DTO if it's a soft failure.
            # For now, if parselmouth fails completely (e.g. bad format), we re-raise.
            raise e
        finally:
            # Plan says: "Audio file is deleted immediately after analysis"
            # However, the `analyze_audio` might be called by an API handler that manages the temp file.
            # The Provider acts on a path. It is safer if the Caller manages the file lifecycle
            # OR we explicitly document that this provider deletes the file.
            # Given the previous pattern (STT), the API handler often creates a temp file.
            # But the Plan 7.3 says "Audio file is deleted immediately after analysis".
            # Let's clean it up here to be safe and strictly follow "files are ephemeral".
            try:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                    logger.info(f"Deleted temporary audio file: {audio_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to delete temp file {audio_path}: {cleanup_error}")

    def _analyze_sync(self, audio_path: str) -> VoiceResultDTO:
        try:
            sound = parselmouth.Sound(audio_path)
        except Exception as e:
            # Parselmouth raises generic exception for bad files usually.
            # We map this to ValueError for the consumer to handle as 400/422.
            raise ValueError(f"Failed to load audio file. File might be corrupted or unsupported format. Error: {e}") from e
        
        # 1. Pitch Analysis
        # limits: 75Hz - 500Hz (standard human range)
        pitch = sound.to_pitch(time_step=None, pitch_floor=75.0, pitch_ceiling=500.0)
        pitch_mean = call(pitch, "Get mean", 0, 0, "Hertz")  # 0,0 means whole duration
        pitch_min = call(pitch, "Get minimum", 0, 0, "Hertz", "Parabolic")
        pitch_max = call(pitch, "Get maximum", 0, 0, "Hertz", "Parabolic")
        
        # Check if pitch is detected (NaN check)
        # parsley returns nan if no pitch found
        import math
        if math.isnan(pitch_mean):
            pitch_mean = None
            pitch_min = None
            pitch_max = None
        else:
            # Round for cleaner output
            pitch_mean = round(pitch_mean, 2)
            pitch_min = round(pitch_min, 2)
            pitch_max = round(pitch_max, 2)

        # 2. Intensity Analysis
        intensity = sound.to_intensity(minimum_pitch=100.0)
        intensity_mean = call(intensity, "Get mean", 0, 0, "energy")
        intensity_min = call(intensity, "Get minimum", 0, 0, "Parabolic")
        intensity_max = call(intensity, "Get maximum", 0, 0, "Parabolic")
        
        if math.isnan(intensity_mean):
            intensity_mean = None
            intensity_min = None
            intensity_max = None
        else:
            intensity_mean = round(intensity_mean, 2)
            intensity_min = round(intensity_min, 2)
            intensity_max = round(intensity_max, 2)

        # 3. Jitter & Shimmer (Voice Quality)
        # Needs PointProcess
        jitter = None
        shimmer = None
        hnr_val = None

        if pitch_mean is not None:
            # Create PointProcess for Jitter/Shimmer
            try:
                point_process = call(sound, "To PointProcess (periodic, cc)", 75.0, 500.0)
                
                # Jitter (local)
                jitter = call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
                
                # Shimmer (local)
                # Shimmer needs Sound object too
                shimmer = call([sound, point_process], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)

                if math.isnan(jitter): jitter = None
                else: jitter = round(jitter, 5) # Jitter is usually very small (e.g. 0.01)

                if math.isnan(shimmer): shimmer = None
                else: shimmer = round(shimmer, 5)

            except Exception as e:
                logger.warning(f"Failed to calculate Jitter/Shimmer: {e}")
        
        # 4. HNR (Harmonics-to-Noise Ratio)
        try:
            harmonicity = call(sound, "To Harmonicity (cc)", 0.01, 75.0, 0.1, 1.0)
            hnr_val = call(harmonicity, "Get mean", 0, 0)
            if math.isnan(hnr_val):
                hnr_val = None
            else:
                hnr_val = round(hnr_val, 2)
        except Exception as e:
            logger.warning(f"Failed to calculate HNR: {e}")

        logger.info(f"Analyzed audio {os.path.basename(audio_path)}: Pitch={pitch_mean}, Inten={intensity_mean}")

        return VoiceResultDTO(
            pitch_mean=pitch_mean,
            pitch_min=pitch_min,
            pitch_max=pitch_max,
            intensity_mean=intensity_mean,
            intensity_min=intensity_min,
            intensity_max=intensity_max,
            jitter=jitter,
            shimmer=shimmer,
            hnr=hnr_val
        )
