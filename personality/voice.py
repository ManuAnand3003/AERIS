"""
AERIS's voice interface.
She listens. She speaks. She sounds like herself.
"""
import asyncio
import numpy as np
from pathlib import Path
from loguru import logger
import sys


class VoiceIO:
    """Speech input/output interface for AERIS"""
    
    def __init__(self):
        self.whisper_model = None
        self.tts_model = None
        self.listening = False

    def initialize_stt(self):
        """Load Whisper model for speech-to-text"""
        try:
            import whisper
            self.whisper_model = whisper.load_model("base")  # "small" for better accuracy
            logger.info("Whisper STT loaded")
        except ImportError:
            logger.error("Whisper not installed. Install with: pip install openai-whisper")
        except Exception as e:
            logger.error(f"Failed to load Whisper: {e}")

    def initialize_tts(self):
        """Load Coqui TTS model for text-to-speech"""
        try:
            from TTS.api import TTS
            self.tts_model = TTS("tts_models/en/ljspeech/tacotron2-DDC", gpu=True)
            logger.info("Coqui TTS loaded")
        except ImportError:
            logger.error("TTS not installed. Install with: pip install TTS")
        except Exception as e:
            logger.error(f"Failed to load TTS: {e}")

    async def listen(self) -> str | None:
        """Record from microphone until silence, transcribe with Whisper"""
        try:
            import sounddevice as sd
        except ImportError:
            logger.error("sounddevice not installed. Install with: pip install sounddevice")
            return None
        
        SAMPLE_RATE = 16000
        SILENCE_THRESHOLD = 0.01
        SILENCE_DURATION = 1.5  # seconds of silence before stopping

        logger.info("[Voice] Listening...")
        recorded = []
        silent_chunks = 0
        
        def callback(indata, frames, time_info, status):
            nonlocal silent_chunks
            recorded.append(indata.copy())
            rms = np.sqrt(np.mean(indata**2))
            silent_chunks = silent_chunks + 1 if rms < SILENCE_THRESHOLD else 0

        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=callback, dtype="float32"):
                while silent_chunks < int(SAMPLE_RATE / 1024 * SILENCE_DURATION):
                    await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"Microphone error: {e}")
            return None

        if not recorded:
            return None
            
        audio = np.concatenate(recorded).flatten()
        
        if self.whisper_model is None:
            self.initialize_stt()
        
        if self.whisper_model is None:
            return None
        
        try:
            result = self.whisper_model.transcribe(audio, fp16=False)
            text = result["text"].strip()
            logger.info(f"[Voice] Heard: {text}")
            return text if text else None
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None

    async def speak(self, text: str):
        """Convert text to speech and play it"""
        if self.tts_model is None:
            self.initialize_tts()
        
        if self.tts_model is None:
            logger.warning("[Voice] TTS not available, printing instead: " + text)
            return
        
        output_path = "/tmp/aeris_speech.wav"
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.tts_model.tts_to_file(text=text, file_path=output_path)
            )
            
            # Play via aplay (ALSA, works on Arch)
            import subprocess
            subprocess.run(["aplay", output_path], capture_output=True, timeout=30)
        except FileNotFoundError:
            logger.warning("[Voice] aplay not found, trying paplay or other audio player")
            try:
                import subprocess
                subprocess.run(["paplay", output_path], capture_output=True, timeout=30)
            except:
                logger.warning("[Voice] No audio player available")
        except Exception as e:
            logger.error(f"TTS/playback error: {e}")

    def is_available(self) -> bool:
        """Check if both STT and TTS are available"""
        return self.whisper_model is not None and self.tts_model is not None


# Global singleton instance
voice = VoiceIO()
