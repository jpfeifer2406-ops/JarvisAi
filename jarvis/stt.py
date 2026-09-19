from pathlib import Path
import yaml
import numpy as np

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

def _load_config():
    return _runtime_load_config()

_model = None
_model_device = None  # track what device the model is on

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None  # type: ignore

def _get_model(force_cpu=False):
    global _model, _model_device
    if _model is not None and not force_cpu:
        return _model
    cfg = _load_config()
    stt = cfg["stt"]
    device = "cpu" if force_cpu else stt["device"]
    compute_type = "int8" if force_cpu else stt["compute_type"]
    try:
        _model = WhisperModel(stt["model"], device=device, compute_type=compute_type)
        _model_device = device
        print(f"[STT] Loaded {stt['model']} on {device}")
    except Exception as e:
        if device != "cpu":
            print(f"[STT] {device} failed to load ({e}), falling back to CPU")
            _model = WhisperModel(stt["model"], device="cpu", compute_type="int8")
            _model_device = "cpu"
            print(f"[STT] Loaded {stt['model']} on cpu")
        else:
            raise
    return _model

def transcribe_audio(audio: np.ndarray) -> str:
    """Transcribe a float32 numpy audio array (16kHz mono) to text."""
    try:
        model = _get_model()
        cfg = _load_config()
        language = cfg.get("stt", {}).get("language", "de")
        beam_size = int(cfg.get("stt", {}).get("beam_size", 1))
        segments, _ = model.transcribe(audio, beam_size=beam_size, language=language)
        return " ".join(seg.text.strip() for seg in segments).strip()
    except Exception as e:
        # If CUDA worked for loading but fails during inference, retry on CPU
        if _model_device != "cpu":
            print(f"[STT] {_model_device} transcription failed ({e}), reloading on CPU")
            try:
                model = _get_model(force_cpu=True)
                cfg = _load_config()
                language = cfg.get("stt", {}).get("language", "de")
                beam_size = int(cfg.get("stt", {}).get("beam_size", 1))
                segments, _ = model.transcribe(audio, beam_size=beam_size, language=language)
                return " ".join(seg.text.strip() for seg in segments).strip()
            except Exception as e2:
                print(f"[STT] CPU transcription also failed: {e2}")
                return ""
        print(f"[STT] Transcription failed: {e}")
        return ""

# Global abort event — set by main.py so recording can be interrupted
_abort_event = None

def set_abort_event(event) -> None:
    """Register the global abort event so recording checks it."""
    global _abort_event
    _abort_event = event

def record_until_silence(
    sample_rate: int = 16000,
    silence_threshold: float = 0.012,
    max_seconds: int = 30,
    speech_wait_seconds: int = 30,
) -> np.ndarray:
    """Record one utterance and stop after trailing silence.

    The microphone can stay open while waiting for the Captain without storing
    minutes of silence. Before speech starts, only a short pre-roll buffer is
    retained. If no speech starts within speech_wait_seconds, an empty array is
    returned so the active conversation can fall back to standby.
    """
    import time
    from collections import deque
    import sounddevice as sd

    chunk = int(sample_rate * 0.3)  # 300 ms
    pre_roll = deque(maxlen=3)      # ~900 ms before detected speech
    recording: list[np.ndarray] = []
    silent_chunks = 0
    silent_chunks_needed = 7        # ~2.1 s trailing silence
    heard_speech = False
    speech_threshold = 0.015
    wait_started = time.monotonic()
    speech_started = None

    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32") as stream:
        while True:
            if _abort_event and _abort_event.is_set():
                print("[STT] Recording aborted.")
                return np.array([], dtype=np.float32)

            data, _ = stream.read(chunk)
            flat = data.flatten().copy()
            rms = float(np.sqrt(np.mean(flat ** 2)))

            if not heard_speech:
                pre_roll.append(flat)
                if rms >= speech_threshold:
                    heard_speech = True
                    speech_started = time.monotonic()
                    recording.extend(pre_roll)
                    pre_roll.clear()
                    silent_chunks = 0
                    print(f"[STT] Speech detected (rms={rms:.4f})")
                elif time.monotonic() - wait_started >= speech_wait_seconds:
                    print(f"[STT] Inactivity timeout ({speech_wait_seconds}s).")
                    return np.array([], dtype=np.float32)
                continue

            recording.append(flat)

            if rms >= speech_threshold:
                silent_chunks = 0
            elif rms < silence_threshold:
                silent_chunks += 1

            if silent_chunks >= silent_chunks_needed:
                print("[STT] Silence detected, stopping recording.")
                break

            if speech_started and time.monotonic() - speech_started >= max_seconds:
                print(f"[STT] Max utterance length reached ({max_seconds}s).")
                break

    if not recording:
        return np.array([], dtype=np.float32)
    return np.concatenate(recording)

