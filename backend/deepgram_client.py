"""Deepgram STT + TTS. Degrades gracefully: if no key, STT returns the raw
text passthrough and TTS returns None so you can build the brain before audio."""
import os

_KEY = os.getenv("DEEPGRAM_API_KEY", "").strip()
_TTS_MODEL = os.getenv("DEEPGRAM_TTS_MODEL", "aura-asteria-en")
_STT_MODEL = os.getenv("DEEPGRAM_STT_MODEL", "nova-2")

_dg = None
if _KEY:
    try:
        from deepgram import DeepgramClient
        _dg = DeepgramClient(_KEY)
    except Exception:  # noqa: BLE001
        _dg = None


def transcribe(audio_bytes: bytes) -> str:
    """Speech -> text. Returns '' if audio can't be transcribed."""
    if not _dg:
        return ""  # caller should fall back to typed input
    try:
        from deepgram import PrerecordedOptions
        opts = PrerecordedOptions(model=_STT_MODEL, smart_format=True)
        res = _dg.listen.rest.v("1").transcribe_file({"buffer": audio_bytes}, opts)
        return res.results.channels[0].alternatives[0].transcript
    except Exception:  # noqa: BLE001
        return ""


def synthesize(text: str) -> bytes | None:
    """Text -> speech (mp3 bytes). Returns None if TTS unavailable."""
    if not _dg or not text:
        return None
    try:
        from deepgram import SpeakOptions
        opts = SpeakOptions(model=_TTS_MODEL)
        # SDK writes to a path; capture into memory via a temp buffer.
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=True) as f:
            _dg.speak.rest.v("1").save(f.name, {"text": text}, opts)
            f.seek(0)
            return f.read()
    except Exception:  # noqa: BLE001
        return None
