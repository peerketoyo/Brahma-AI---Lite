import ctypes
import logging
import os
import re
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice_engine")

DUTCH_FEMALE_VOICE = "nl-NL-FennaNeural"
ENGLISH_FEMALE_VOICE = "en-US-AriaNeural"

_current_audio_path: Optional[str] = None
_current_player_alias: Optional[str] = None
_speech_lock = threading.Lock()

# Heuristic lists for language identification (Dutch as primary base)
DUTCH_MARKERS = {
    "de", "het", "een", "en", "is", "van", "te", "dat", "die", "voor", "niet",
    "met", "op", "zijn", "was", "we", "je", "ze", "er", "maar", "als", "om",
    "naar", "over", "door", "kan", "kunnen", "zal", "zou", "heeft", "hebben",
    "hallo", "goedemorgen", "goedemiddag", "goedenavond", "alsjeblieft",
    "alstublieft", "bedankt", "welkom", "tot", "ziens", "ik", "ben", "jennifer",
    "wat", "kan", "helpen", "vandaag", "begrepen", "natuurlijk", "zeker", "klaar",
    "geen", "probleem", "graag", "gedaan"
}

ENGLISH_MARKERS = {
    "the", "a", "an", "and", "is", "of", "to", "that", "this", "for", "not",
    "with", "on", "are", "was", "we", "you", "they", "there", "but", "if",
    "about", "into", "can", "could", "will", "would", "has", "have", "hello",
    "hi", "good", "morning", "afternoon", "welcome", "please", "thanks",
    "thank", "understand", "sure", "ready", "what", "how", "today"
}

def detect_language(text: str) -> str:
    """Return 'nl' if Dutch (default base), 'en' if English."""
    cleaned = re.sub(r"[^a-zA-Z\s]", " ", (text or "").lower())
    words = set(cleaned.split())
    if not words:
        return "nl"

    nl_count = sum(1 for w in words if w in DUTCH_MARKERS)
    en_count = sum(1 for w in words if w in ENGLISH_MARKERS)

    # Defaults to Dutch ('nl') unless clear predominance of English words
    if en_count > nl_count and en_count >= 2:
        return "en"
    return "nl"

def get_voice_for_text(text: str, override_voice: Optional[str] = None) -> str:
    if override_voice:
        return override_voice
    lang = detect_language(text)
    if lang == "en":
        return ENGLISH_FEMALE_VOICE
    return DUTCH_FEMALE_VOICE

def _cleanup_audio():
    global _current_player_alias, _current_audio_path
    if _current_player_alias:
        try:
            ctypes.windll.winmm.mciSendStringW(f"stop {_current_player_alias}", None, 0, None)
            ctypes.windll.winmm.mciSendStringW(f"close {_current_player_alias}", None, 0, None)
        except Exception:
            pass
        _current_player_alias = None

    if _current_audio_path:
        try:
            if os.path.exists(_current_audio_path):
                os.remove(_current_audio_path)
        except Exception:
            pass
        _current_audio_path = None

def stop_speech() -> None:
    """Immediately stop speech playback and clean up audio files."""
    with _speech_lock:
        _cleanup_audio()

def speak_windows_sapi(text: str) -> bool:
    """Fallback Windows speech synthesis using System.Speech."""
    try:
        clean_text = text.replace("'", " ").replace('"', ' ').replace("\n", " ")
        ps_cmd = f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{clean_text}')"
        subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps_cmd], capture_output=True, timeout=20)
        return True
    except Exception as exc:
        logger.error(f"[VoiceEngine] Windows SAPI speech failed: {exc}")
        return False

def speak_text(text: str, voice: Optional[str] = None, wait: bool = True) -> bool:
    """
    Synthesize and play speech.
    Uses Edge TTS (FennaNeural for Dutch / AriaNeural for English) if available,
    falling back to Windows System.Speech.
    """
    global _current_audio_path, _current_player_alias
    text = (text or "").strip()
    if not text:
        return False

    has_edge_tts = False
    try:
        import edge_tts  # type: ignore[import-not-found]
        has_edge_tts = True
    except ImportError:
        has_edge_tts = False

    if not has_edge_tts:
        logger.info("[VoiceEngine] edge_tts not available, using Windows SAPI voice.")
        return speak_windows_sapi(text)

    with _speech_lock:
        _cleanup_audio()
        selected_voice = get_voice_for_text(text, voice)
        audio_path = os.path.join(tempfile.gettempdir(), f"jennifer_tts_{uuid.uuid4().hex}.mp3")

        try:
            communicator = edge_tts.Communicate(text, voice=selected_voice)
            communicator.save_sync(audio_path)
        except Exception as exc:
            logger.warning(f"[VoiceEngine] Edge TTS generation failed: {exc}. Falling back to SAPI.")
            _cleanup_audio()
            return speak_windows_sapi(text)

        player_alias = f"jennifer_tts_{uuid.uuid4().hex}"
        try:
            res = ctypes.windll.winmm.mciSendStringW(
                f'open "{audio_path}" type mpegvideo alias {player_alias}',
                None,
                0,
                None,
            )
            if res != 0:
                raise RuntimeError(f"MCI open failed: {res}")

            _current_player_alias = player_alias
            _current_audio_path = audio_path

            wait_flag = "wait" if wait else "notify"
            ctypes.windll.winmm.mciSendStringW(
                f"play {player_alias} {wait_flag}",
                None,
                0,
                None,
            )
            return True
        except Exception as exc:
            logger.warning(f"[VoiceEngine] MCI playback failed: {exc}. Falling back to SAPI.")
            _cleanup_audio()
            return speak_windows_sapi(text)
