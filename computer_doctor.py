from __future__ import annotations

import importlib
import json
import platform
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config.yaml"
REPORT = ROOT / "computer_diagnostics.txt"


def line(name: str, value) -> str:
    return f"{name}: {value}"


def check_import(module: str) -> str:
    try:
        importlib.import_module(module)
        return "OK"
    except Exception as exc:
        return f"ERROR - {type(exc).__name__}: {exc}"


def ollama_status(base_url: str) -> str:
    try:
        url = base_url.rstrip("/") + "/api/tags"
        with urllib.request.urlopen(url, timeout=2) as response:
            data = json.loads(response.read().decode("utf-8"))
        models = [m.get("name", "?") for m in data.get("models", [])]
        return "OK - " + (", ".join(models) if models else "no models listed")
    except Exception as exc:
        return f"OFFLINE/ERROR - {type(exc).__name__}: {exc}"


def main() -> int:
    lines: list[str] = []
    lines.append("COMPUTER v0.5.1 TEST // DIAGNOSTICS")
    lines.append("=" * 48)
    lines.append(line("Python", sys.version.replace("\n", " ")))
    lines.append(line("Platform", platform.platform()))
    lines.append(line("Executable", sys.executable))
    lines.append("")

    modules = [
        "faster_whisper",
        "openwakeword",
        "kokoro",
        "ollama",
        "openai",
        "chromadb",
        "pyaudio",
        "sounddevice",
        "fastapi",
        "uvicorn",
        "yaml",
    ]
    lines.append("DEPENDENCIES")
    for module in modules:
        lines.append(line(module, check_import(module)))
    lines.append("")

    try:
        cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
        lines.append("CONFIG")
        lines.append(line("wake_word.model", cfg.get("wake_word", {}).get("model")))
        lines.append(line("wake_word.threshold", cfg.get("wake_word", {}).get("threshold")))
        lines.append(line("stt.model", cfg.get("stt", {}).get("model")))
        lines.append(line("stt.device", cfg.get("stt", {}).get("device")))
        lines.append(line("stt.language", cfg.get("stt", {}).get("language")))
        lines.append(line("tts.voice", cfg.get("tts", {}).get("voice")))
        lines.append(line("tts.speed", cfg.get("tts", {}).get("speed")))
        lines.append(line("voice.session_timeout_seconds", cfg.get("voice", {}).get("session_timeout_seconds")))
        lines.append(line("llm.active_provider", cfg.get("llm", {}).get("active_provider")))
        providers = cfg.get("llm", {}).get("providers", {})
        for key, provider in providers.items():
            # Intentionally never print api_key.
            lines.append(line(f"provider.{key}", {
                "type": provider.get("type"),
                "model": provider.get("model"),
                "base_url": provider.get("base_url"),
                "has_api_key": bool(provider.get("api_key")),
            }))
        ollama_cfg = providers.get("ollama", {})
        lines.append(line("ollama", ollama_status(ollama_cfg.get("base_url", "http://localhost:11434"))))
    except Exception as exc:
        lines.append(line("CONFIG ERROR", f"{type(exc).__name__}: {exc}"))

    lines.append("")
    lines.append("AUDIO DEVICES")
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        default_in, default_out = sd.default.device
        lines.append(line("default_input_index", default_in))
        lines.append(line("default_output_index", default_out))
        for idx, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) or dev.get("max_output_channels", 0):
                lines.append(
                    f"[{idx}] {dev.get('name')} | in={dev.get('max_input_channels')} "
                    f"| out={dev.get('max_output_channels')} | rate={dev.get('default_samplerate')}"
                )
    except Exception as exc:
        lines.append(line("AUDIO ERROR", f"{type(exc).__name__}: {exc}"))

    text = "\n".join(lines) + "\n"
    REPORT.write_text(text, encoding="utf-8")
    print(text)
    print(f"Report saved to: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
