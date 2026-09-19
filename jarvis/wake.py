from __future__ import annotations

from pathlib import Path
import threading
import time
import urllib.request

import numpy as np
import yaml

_PROJECT_ROOT = Path(__file__).parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config.yaml"


def _load_config():
    return _runtime_load_config()


def _resolve_model_path(cfg: dict) -> Path:
    """Resolve/download the configured custom openWakeWord model."""
    configured = Path(str(cfg["model"]))
    path = configured if configured.is_absolute() else _PROJECT_ROOT / configured
    if path.exists():
        return path

    url = str(cfg.get("model_url", "")).strip()
    if not url:
        raise FileNotFoundError(f"Wake-word model not found: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".download")
    print(f"[Wake] Downloading COMPUTER wake-word model -> {path}")
    try:
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
    return path


# Mic pause/resume for STT recording. When STT needs to record, it pauses the
# wake-word stream so both components do not compete for the input device.
_mic_pause = threading.Event()


def pause_wake_mic() -> None:
    _mic_pause.set()


def resume_wake_mic() -> None:
    _mic_pause.clear()


def listen_for_wake_word(callback) -> None:
    """Listen continuously for the configured COMPUTER wake word."""
    import pyaudio
    from openwakeword.model import Model

    cfg = _load_config()["wake_word"]
    model_path = _resolve_model_path(cfg)
    phrase = str(cfg.get("phrase", "Computer"))
    threshold = float(cfg.get("threshold", 0.72))
    chunk_size = int(cfg.get("chunk_size", 1280))

    # Custom Computer v2 model from the Home Assistant wake-word collection.
    # ONNX inference stays on CPU and is intentionally independent of CUDA.
    oww = Model(wakeword_models=[str(model_path)], inference_framework="onnx")

    audio = pyaudio.PyAudio()
    mic = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=chunk_size,
    )

    _busy = threading.Lock()
    _ignore_until = [0.0]

    print(f"[COMPUTER] Listening for wake word: {phrase.upper()}...")
    try:
        while True:
            if _mic_pause.is_set():
                if mic.is_active():
                    mic.stop_stream()
                    print("[Wake] Mic paused for STT recording.")
                while _mic_pause.is_set():
                    time.sleep(0.05)
                mic.start_stream()
                oww.reset()
                print("[Wake] Mic resumed.")
                continue

            try:
                pcm = np.frombuffer(mic.read(chunk_size), dtype=np.int16)
            except Exception:
                time.sleep(0.05)
                continue

            predictions = oww.predict(pcm)
            # Only one wake model is loaded, but its result key is derived from
            # the ONNX graph/filename. max() avoids coupling to that internal key.
            score = max((float(v) for v in predictions.values()), default=0.0)
            if score < threshold:
                continue

            oww.reset()
            now = time.time()
            if now < _ignore_until[0]:
                continue

            if _busy.locked():
                _ignore_until[0] = now + 3.0
                from jarvis.main import abort_all
                abort_all()
                print("[COMPUTER] Stopped. (voice interrupt)")
            else:
                _ignore_until[0] = now + 2.0

                def _run():
                    with _busy:
                        callback()

                threading.Thread(target=_run, daemon=True).start()
    finally:
        mic.stop_stream()
        mic.close()
        audio.terminate()
