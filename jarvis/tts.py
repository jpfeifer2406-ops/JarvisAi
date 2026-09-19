from pathlib import Path
import re
import yaml
import numpy as np
import sounddevice as sd
import threading

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

def _load_config():
    return _runtime_load_config()

_pipeline = None
_voice_tensor = None
_tts_model = None
_speaking = threading.Event()  # set while audio is playing
_interrupt = threading.Event()  # set to stop streaming
_tts_available = True
_tts_error: str | None = None

_LOCAL_PTH = Path.home() / "Downloads" / "kokoro-v1_0.pth"
_VICTORIA_CONFIG = Path(__file__).parent / "tts_assets" / "kikiri_config.json"


def _disable_tts(exc: Exception) -> None:
    """Disable TTS for this runtime instead of crashing COMPUTER at startup."""
    global _tts_available, _tts_error
    _tts_error = f"{type(exc).__name__}: {exc}"
    if _tts_available:
        print(f"[TTS] Kokoro unavailable; continuing without voice. {_tts_error}")
    _tts_available = False
    _speaking.clear()
    try:
        sd.stop()
    except Exception:
        pass


def tts_available() -> bool:
    """Return whether TTS is still available in this runtime."""
    return _tts_available

def _get_pipeline():
    """Load the configured TTS engine lazily.

    v0.5.2 defaults to the German Victoria checkpoint. The currently installed
    Kokoro release may not register German yet, so COMPUTER adds the minimal
    in-memory language mapping before creating the pipeline.
    """
    global _pipeline, _voice_tensor, _tts_model
    if _pipeline is not None:
        return _pipeline

    cfg = _load_config()
    tts_cfg = cfg.get("tts", {})
    engine = str(tts_cfg.get("engine", "legacy")).lower()

    from kokoro import KPipeline, KModel

    if engine == "victoria":
        import torch
        from huggingface_hub import hf_hub_download
        from misaki.de import DEG2P

        repo_id = tts_cfg.get("repo_id", "kikiri-tts/kikiri-german-victoria")
        model_file = tts_cfg.get("model_file", "kikiri_german_victoria_ep10.pth")
        voice_file = tts_cfg.get("voice_file", "voices/victoria.pt")

        print("[TTS] Loading German Victoria voice on CPU...")
        model_path = hf_hub_download(repo_id=repo_id, filename=model_file)
        voice_path = hf_hub_download(repo_id=repo_id, filename=voice_file)

        # Kikiri's German checkpoints were trained against this exact Kokoro
        # vocabulary/config and the dedicated German DEG2P frontend.
        _tts_model = KModel(
            repo_id="hexgrad/Kokoro-82M",
            config=str(_VICTORIA_CONFIG),
            model=model_path,
        ).to("cpu").eval()
        _pipeline = KPipeline(
            lang_code="d",
            repo_id="hexgrad/Kokoro-82M",
            model=_tts_model,
            device="cpu",
        )
        # Defensive assignment: the pinned fork already selects DEG2P for "d",
        # but keeping this explicit prevents a silent fallback to generic eSpeak.
        _pipeline.g2p = DEG2P()
        _voice_tensor = torch.load(voice_path, map_location="cpu", weights_only=True)
        print("[TTS] German Victoria voice ready (DEG2P / CPU / 24 kHz).")
        return _pipeline

    # Legacy Kokoro path retained as a fallback/testing option.
    repo_id = "hexgrad/Kokoro-82M"
    if _LOCAL_PTH.exists():
        _tts_model = KModel(repo_id=repo_id, model=str(_LOCAL_PTH)).to("cpu").eval()
        _pipeline = KPipeline(lang_code="a", repo_id=repo_id, model=_tts_model)
    else:
        _pipeline = KPipeline(lang_code="a", repo_id=repo_id)
    return _pipeline


def _get_voice():
    """Load the configured voice tensor once and cache it."""
    global _voice_tensor
    if _voice_tensor is not None:
        return _voice_tensor

    # _get_pipeline also loads Victoria's dedicated voicepack.
    _get_pipeline()
    if _voice_tensor is not None:
        return _voice_tensor

    import torch
    cfg = _load_config()
    voice_name = cfg["tts"].get("voice", "af_heart")
    local_voice = _LOCAL_PTH.parent / f"{voice_name}.pt"
    if local_voice.exists():
        _voice_tensor = torch.load(str(local_voice), weights_only=True)
    else:
        from huggingface_hub import hf_hub_download
        path = hf_hub_download(
            repo_id="hexgrad/Kokoro-82M",
            filename=f"voices/{voice_name}.pt",
            local_files_only=False,
        )
        _voice_tensor = torch.load(path, weights_only=True)
    return _voice_tensor


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences for streaming TTS."""
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p.strip() for p in parts if p.strip()]


def speak_to_bytes(text: str) -> bytes:
    """Convert text to PCM audio bytes using Kokoro TTS."""
    if not text or not text.strip():
        raise ValueError("Text cannot be empty")
    pipeline = _get_pipeline()
    voice = _get_voice()
    cfg = _load_config()
    speed = cfg["tts"]["speed"]
    audio_chunks = []
    for _, _, audio in pipeline(text, voice=voice, speed=speed):
        if audio is not None:
            audio_chunks.append(audio)
    if not audio_chunks:
        return b""
    combined = np.concatenate(audio_chunks)
    pcm = (combined * 32767).astype(np.int16)
    return pcm.tobytes()


def is_speaking() -> bool:
    """Check if Jarvis is currently speaking."""
    return _speaking.is_set()


def stop_speaking() -> None:
    """Interrupt current speech playback — instant."""
    _interrupt.set()
    sd.stop()
    _speaking.clear()


def _wait_or_interrupt() -> bool:
    """Poll until audio finishes or interrupt is set. Returns True if interrupted."""
    while sd.get_stream() and sd.get_stream().active:
        if _interrupt.is_set():
            sd.stop()
            return True
        _interrupt.wait(0.05)  # 50ms poll
    return _interrupt.is_set()


def speak(text: str) -> None:
    """Speak text aloud. Can be interrupted via stop_speaking().

    If Kokoro or one of its native dependencies is blocked/unavailable,
    disable TTS for this runtime and keep the rest of COMPUTER online.
    """
    if not _tts_available:
        return
    _interrupt.clear()
    try:
        audio_bytes = speak_to_bytes(text)
        if not audio_bytes:
            return
        audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32767
        _speaking.set()
        sd.play(audio, samplerate=24000)
        _wait_or_interrupt()
    except Exception as exc:
        _disable_tts(exc)
    finally:
        _speaking.clear()


def speak_streamed(text: str) -> None:
    """Speak text sentence by sentence — starts playing before full generation is done.
    Can be interrupted mid-stream via stop_speaking()."""
    if not _tts_available:
        return
    _interrupt.clear()
    sentences = _split_sentences(text)
    if not sentences:
        return

    # Short text — just speak normally
    if len(sentences) == 1:
        speak(text)
        return

    try:
        pipeline = _get_pipeline()
        voice = _get_voice()
        cfg = _load_config()
        speed = cfg["tts"]["speed"]

        _speaking.set()
        for sentence in sentences:
            if _interrupt.is_set():
                break
            chunks = []
            for _, _, audio in pipeline(sentence, voice=voice, speed=speed):
                if _interrupt.is_set():
                    break
                if audio is not None:
                    chunks.append(audio)
            if not chunks or _interrupt.is_set():
                break
            combined = np.concatenate(chunks)
            sd.play(combined, samplerate=24000)
            if _wait_or_interrupt():
                break
    except Exception as exc:
        _disable_tts(exc)
    finally:
        try:
            sd.stop()  # ensure audio stops even if we break mid-play
        except Exception:
            pass
        _speaking.clear()
        _interrupt.clear()
