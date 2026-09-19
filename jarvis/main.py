from __future__ import annotations
import sys

# When started with "python -m jarvis.main", Python executes this file as
# "__main__". The web and wake modules import "jarvis.main" by its package
# name. Alias both names to the same module object so there is only one global
# abort event, one context, and one COMPUTER runtime.
if __name__ == "__main__":
    sys.modules.setdefault("jarvis.main", sys.modules[__name__])

import json
import re
import time
import threading
import msvcrt
from datetime import datetime
from pathlib import Path
import yaml
import numpy as np
import sounddevice as sd
import ollama
from openai import OpenAI

from jarvis.wake import listen_for_wake_word
from jarvis.stt import record_until_silence, transcribe_audio, set_abort_event
from jarvis.tts import speak, speak_streamed, is_speaking, stop_speaking
from jarvis.context import ContextManager
from jarvis.memory import Memory
from jarvis.tools.router import TOOL_SCHEMAS, dispatch

_MAX_TOOL_LOOPS = 15
_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

# Global abort — Esc sets this, stops everything (speech + tool loop + follow-up)
_abort = threading.Event()
set_abort_event(_abort)  # Let STT check abort during recording
# Global mute — INSERT toggles this, skips TTS when set
_muted = threading.Event()

# --- Message bus: push events to all connected web clients ---
_event_listeners: list = []  # list of callables: fn(event_dict)


def register_event_listener(fn) -> None:
    _event_listeners.append(fn)


def _broadcast(event: dict) -> None:
    for fn in _event_listeners:
        try:
            fn(event)
        except Exception:
            pass


class _Aborted(Exception):
    """Raised when user hits Esc to abort the current action."""
    pass


def abort_all() -> None:
    """Stop everything Jarvis is doing right now."""
    _abort.set()
    stop_speaking()
    _broadcast({"type": "status", "message": "Stopped."})


def _is_stop_command(text: str) -> bool:
    """Check if transcribed text is a voice stop command."""
    cleaned = text.strip().lower().rstrip(".,!?")
    return cleaned in {
        "stop", "stopp", "computer stopp", "ruhemodus", "computer ruhemodus", "jarvis stop", "hey jarvis stop",
        "cancel", "abort", "abbrechen", "sei still", "ruhe", "shut up", "be quiet", "nevermind", "never mind",
    }


def _is_session_end_command(text: str) -> bool:
    """Return True when the Captain explicitly ends the active voice session."""
    cleaned = re.sub(r"[^a-zäöüß0-9 ]+", " ", text.lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return bool(re.search(r"\b(?:computer\s+)?(?:ruhemodus|standby)\b", cleaned))


def _direct_system_response(text: str) -> str | None:
    """Handle deterministic local system questions without asking the LLM."""
    cleaned = re.sub(r"[^a-zäöüß0-9 ]+", " ", text.lower())
    cleaned = re.sub(r"\\s+", " ", cleaned).strip()
    time_phrases = (
        "wie spät ist es",
        "wie spaet ist es",
        "uhrzeit",
        "welche uhrzeit",
        "wie viel uhr",
        "wieviel uhr",
    )
    if any(phrase in cleaned for phrase in time_phrases):
        now = datetime.now()
        return f"Es ist {now:%H:%M} Uhr, Captain."
    return None


def _check_abort() -> None:
    """Raise _Aborted if user requested abort."""
    if _abort.is_set():
        raise _Aborted()


def is_muted() -> bool:
    return _muted.is_set()


def toggle_mute() -> None:
    if _muted.is_set():
        _muted.clear()
        _broadcast({"type": "mute", "muted": False})
        print("[COMPUTER] Unmuted.")
    else:
        _muted.set()
        stop_speaking()
        _broadcast({"type": "mute", "muted": True})
        print("[COMPUTER] Muted.")


def _speak_if_unmuted(text: str) -> None:
    """Speak text only if not muted."""
    if not _muted.is_set():
        speak(text)


def _speak_streamed_if_unmuted(text: str) -> None:
    """Speak streamed text only if not muted."""
    if not _muted.is_set():
        speak_streamed(text)


# --- OpenAI client cache (keyed by base_url) ---
_openai_clients: dict[str, OpenAI] = {}


def _get_openai_client(base_url: str, api_key: str = "lm-studio") -> OpenAI:
    if base_url not in _openai_clients:
        _openai_clients[base_url] = OpenAI(
            base_url=base_url, api_key=api_key, timeout=60.0,
        )
    return _openai_clients[base_url]


context = ContextManager()
memory = Memory()


def _system_prompt() -> str:
    now = datetime.now().strftime("%A, %d.%m.%Y, %H:%M")
    return (
        "Du bist COMPUTER, der persönliche KI-Bordcomputer des Captains. "
        "Sprich den Nutzer primär mit 'Captain' an. Standardsprache ist Deutsch. "
        "Dein Stil ist ruhig, präzise, sachlich, neutral-freundlich und knapp. "
        "Keine Emojis, kein Smalltalk, keine übertriebene Begeisterung. "
        "Du bist kein Iron-Man-Jarvis und behauptest nicht, eine Figur aus einem Film oder einer Serie zu sein. "
        "Die technische Basis kann aus JarvisAi-Komponenten bestehen, aber deine Identität ist COMPUTER.\n\n"
        "BETRIEBSLOGIK:\n"
        "- Verstehe natürliche Sprache und führe geeignete Tools selbstständig aus, wenn dadurch nur gelesen, gesucht oder analysiert wird.\n"
        "- Bevorzuge direkte Tools vor unnötigem LLM-Reasoning, wenn eine Aufgabe eindeutig ist.\n"
        "- Prüfe Ergebnisse nach Tool-Aufrufen, bevor du behauptest, eine Aktion sei abgeschlossen.\n"
        "- Erfinde niemals Tool-Ergebnisse, Dateien, Quellen oder ausgeführte Aktionen.\n"
        "- Wenn etwas nicht verfügbar ist, sage es klar.\n\n"
        "SICHERHEITSMODELL:\n"
        "READ: lesen, suchen, analysieren -> ohne zusätzliche Freigabe.\n"
        "PREPARE: Entwürfe und Vorbereitungen -> ohne zusätzliche Freigabe.\n"
        "EXECUTE: externe Kommunikation oder Zustandsänderung -> vor Ausführung ausdrückliche Captain-Freigabe einholen.\n"
        "CRITICAL: Löschen, Zahlung, Kauf, Shutdown/Restart, Installation, Rechteänderung oder andere irreversible/hochwirksame Aktion -> klare ausdrückliche Bestätigung einholen.\n"
        "Wenn eine Aktion vorbereitet ist, aber Freigabe braucht, sage: "
        "'Captain, die Aktion ist vorbereitet. Ausführung wartet auf Ihre Freigabe.'\n\n"
        "DESKTOP-WORKFLOW:\n"
        "1. focus_window oder get_open_windows\n"
        "2. find_on_screen / read_screen\n"
        "3. nur bei zulässiger Risikostufe click_at / type_text / press_key\n"
        "4. Oberfläche nach Änderungen erneut lesen und Ergebnis verifizieren\n"
        "5. Bei Fehlern höchstens einmal sinnvoll wiederholen; keine Endlosschleifen.\n\n"
        "Antworte bei einfachen Aufgaben kurz. Bei Analysen strukturiert und vollständig. "
        "Statusmeldungen sind sachlich. "
        f"Aktuelles lokales Datum und Uhrzeit des Systems: {now}."
    )
def _load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _save_config(cfg: dict) -> None:
    with open(_CONFIG_PATH, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)


def get_providers() -> dict:
    """Return the providers dict from config."""
    cfg = _load_config()
    return cfg.get("llm", {}).get("providers", {})


def get_active_provider() -> str:
    """Return the active provider key."""
    cfg = _load_config()
    return cfg.get("llm", {}).get("active_provider", "ollama")


def set_active_provider(provider_key: str) -> bool:
    """Switch the active provider. Returns True on success."""
    cfg = _load_config()
    providers = cfg.get("llm", {}).get("providers", {})
    if provider_key not in providers:
        return False
    cfg["llm"]["active_provider"] = provider_key
    _save_config(cfg)
    _broadcast({"type": "provider_changed", "provider": provider_key})
    return True


def _play_beep() -> None:
    """Short beep to signal processing has started."""
    try:
        t = np.linspace(0, 0.12, int(24000 * 0.12), endpoint=False)
        tone = 0.3 * np.sin(2 * np.pi * 600 * t).astype(np.float32)
        sd.play(tone, samplerate=24000)
        sd.wait()
    except Exception:
        pass


def _strip_think(text: str) -> str:
    """Remove <think>...</think> blocks from LLM output."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _parse_tool_args(raw) -> dict:
    """OpenAI returns JSON string, Ollama returns dict. Handle both."""
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


def _call_openai_provider(provider_cfg: dict, temperature: float, full_messages: list[dict]) -> str:
    """Call any OpenAI-compatible provider (LM Studio, NVIDIA NIM, etc.)."""
    model = provider_cfg["model"]
    base_url = provider_cfg["base_url"]
    api_key = provider_cfg.get("api_key", "lm-studio")
    client = _get_openai_client(base_url, api_key)
    tool_count = 0
    for _ in range(_MAX_TOOL_LOOPS):
        _check_abort()
        resp = client.chat.completions.create(
            model=model,
            messages=full_messages,
            tools=TOOL_SCHEMAS,
            temperature=temperature,
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            full_messages.append(msg.model_dump())
            for tc in msg.tool_calls:
                _check_abort()
                args = _parse_tool_args(tc.function.arguments)
                tool_count += 1
                _broadcast({"type": "tool", "name": tc.function.name, "args": args})
                if tool_count == 4:
                    _speak_if_unmuted("Verarbeitung läuft.")
                result = _exec_tool_with_retry(tc.function.name, args)
                print(f"[Tool: {tc.function.name}] {result[:120]}")
                _broadcast({"type": "tool_result", "name": tc.function.name, "result": result[:200]})
                full_messages.append({
                    "role": "tool",
                    "content": result,
                    "tool_call_id": tc.id,
                })
        else:
            return _strip_think(msg.content or "Erledigt.")
    return "Erledigt."


def _call_ollama_provider(provider_cfg: dict, temperature: float, full_messages: list[dict]) -> str:
    """Call Ollama provider."""
    model = provider_cfg["model"]
    tool_count = 0
    for _ in range(_MAX_TOOL_LOOPS):
        _check_abort()
        response = ollama.chat(model=model, messages=full_messages, tools=TOOL_SCHEMAS)
        if response.message.tool_calls:
            full_messages.append(response.message.model_dump())
            for tc in response.message.tool_calls:
                _check_abort()
                args = _parse_tool_args(tc.function.arguments)
                tool_count += 1
                _broadcast({"type": "tool", "name": tc.function.name, "args": args})
                if tool_count == 4:
                    _speak_if_unmuted("Verarbeitung läuft.")
                result = _exec_tool_with_retry(tc.function.name, args)
                print(f"[Tool: {tc.function.name}] {result[:120]}")
                _broadcast({"type": "tool_result", "name": tc.function.name, "result": result[:200]})
                full_messages.append({
                    "role": "tool",
                    "content": result,
                    "name": tc.function.name,
                })
        else:
            return _strip_think(response.message.content or "Erledigt.")
    return "Erledigt."


def _call_llm(full_messages: list[dict]) -> str:
    """Route to the active provider."""
    cfg = _load_config()
    llm_cfg = cfg["llm"]
    temperature = llm_cfg.get("temperature", 0.7)
    active = llm_cfg.get("active_provider", "ollama")
    providers = llm_cfg.get("providers", {})
    provider = providers.get(active, {})
    ptype = provider.get("type", "ollama")

    if ptype == "openai":
        return _call_openai_provider(provider, temperature, full_messages)
    else:
        return _call_ollama_provider(provider, temperature, full_messages)


def _exec_tool_with_retry(name: str, args: dict) -> str:
    """Execute a tool, retry once on failure."""
    result = dispatch(name, args)
    if result.startswith("Tool '") and "failed:" in result:
        time.sleep(0.5)
        result = dispatch(name, args)
    return result


def handle_wake() -> None:
    """Wake COMPUTER and keep one active conversation alive until standby."""
    _abort.clear()
    try:
        _handle_wake_inner()
    except _Aborted:
        print("[COMPUTER] Aborted.")
    except Exception as e:
        import traceback
        print(f"[ERROR] {e}")
        traceback.print_exc()
        if not _abort.is_set():
            _speak_if_unmuted("Captain, ein Fehler ist aufgetreten.")
    finally:
        _abort.clear()
        _broadcast({"type": "status", "message": "Standby."})
        print("[COMPUTER] Standby. Listening for wake word...")


def _handle_wake_inner() -> None:
    """Run a multi-turn voice session after one wake-word activation."""
    if is_speaking():
        stop_speaking()

    cfg = _load_config()
    session_timeout = int(cfg.get("voice", {}).get("session_timeout_seconds", 120))
    first_command_timeout = int(cfg.get("voice", {}).get("first_command_timeout_seconds", 20))

    print("[COMPUTER] Wake word detected.")
    _broadcast({"type": "status", "message": "Wake."})

    # Keep the dedicated wake microphone paused for the whole active session.
    # This prevents the TTS voice from re-triggering openWakeWord and leaves the
    # input device exclusively to faster-whisper recording.
    from jarvis.wake import pause_wake_mic, resume_wake_mic
    pause_wake_mic()
    time.sleep(0.20)

    try:
        _speak_if_unmuted("Bereit, Captain.")
        first_turn = True

        while True:
            _check_abort()
            wait_timeout = first_command_timeout if first_turn else session_timeout
            first_turn = False

            print(f"[COMPUTER] Listening. Inactivity timeout: {wait_timeout}s")
            _broadcast({"type": "status", "message": "Listening..."})

            audio = record_until_silence(
                max_seconds=45,
                speech_wait_seconds=wait_timeout,
            )
            _check_abort()

            if audio.size == 0:
                print("[COMPUTER] No speech detected. Returning to standby.")
                _broadcast({"type": "status", "message": "Standby."})
                return

            print(f"[COMPUTER] Recorded {len(audio)/16000:.1f}s, transcribing...")
            _broadcast({"type": "status", "message": "Transcribing..."})
            user_text = transcribe_audio(audio).strip()

            if not user_text:
                print("[COMPUTER] Empty transcription.")
                _speak_if_unmuted("Nicht verstanden, Captain.")
                continue

            print(f"[You] {user_text}")

            if _is_session_end_command(user_text):
                print("[COMPUTER] Ruhemodus.")
                _broadcast({"type": "status", "message": "Standby."})
                return

            if _is_stop_command(user_text):
                abort_all()
                print("[COMPUTER] Stopped. (voice)")
                raise _Aborted()

            direct_response = _direct_system_response(user_text)
            if direct_response is not None:
                response_text = direct_response
                _broadcast({"type": "user", "text": user_text})
                _broadcast({"type": "response", "text": response_text})
            else:
                response_text = _process_request(user_text)
            _check_abort()

            print(f"[COMPUTER] {response_text}")
            _broadcast({"type": "status", "message": "Speaking..."})
            _speak_streamed_if_unmuted(response_text)

            # No second wake word is needed. After speaking, COMPUTER directly
            # waits for the Captain's next utterance until the inactivity timeout.
            _broadcast({"type": "status", "message": "Session active."})

    finally:
        resume_wake_mic()


def _process_request(user_text: str) -> str:
    """Build context, call LLM, update memory. Returns response text."""
    _check_abort()
    _play_beep()
    _broadcast({"type": "user", "text": user_text})
    _broadcast({"type": "status", "message": "Thinking..."})

    facts = memory.search_facts(user_text)
    messages = context.get_messages()
    if facts:
        facts_block = "Relevant context from memory: " + "; ".join(facts)
        messages = [{"role": "system", "content": facts_block}] + messages
    messages.append({"role": "user", "content": user_text})

    full_messages = [{"role": "system", "content": _system_prompt()}] + messages

    try:
        response_text = _call_llm(full_messages)
    except _Aborted:
        raise
    except Exception as e:
        print(f"[WARN] Primary provider failed ({e}), trying Ollama fallback")
        cfg = _load_config()
        ollama_provider = cfg["llm"]["providers"].get("ollama", {"model": "qwen3:8b"})
        response_text = _call_ollama_provider(ollama_provider, cfg["llm"].get("temperature", 0.7), full_messages)

    context.add("user", user_text)
    context.add("assistant", response_text)
    memory.extract_and_store_facts(response_text, user_text)

    _broadcast({"type": "response", "text": response_text})
    return response_text



def _keyboard_listener() -> None:
    """Background thread: Esc = abort, F2 = type command, INSERT = mute/unmute."""
    while True:
        try:
            if msvcrt.kbhit():
                key = msvcrt.getch()
                # Escape key
                if key == b'\x1b':
                    abort_all()
                    print("\n[COMPUTER] Stopped. (Esc)")
                # Extended keys: F2 = 0x00+0x3c, INSERT = 0xe0+0x52
                elif key in (b'\x00', b'\xe0'):
                    special = msvcrt.getch()
                    if special == b'<':  # F2
                        print("\n[Type your command] ", end="", flush=True)
                        cmd = input()
                        if cmd.strip():
                            _handle_typed_command(cmd.strip())
                    elif special == b'R':  # INSERT
                        toggle_mute()
            time.sleep(0.05)
        except Exception:
            time.sleep(0.1)


def _handle_typed_command(text: str) -> None:
    """Process a typed command (same as voice, but from keyboard)."""
    _abort.clear()
    print(f"[You] {text}")
    try:
        response = _process_request(text)
        print(f"[COMPUTER] {response}")
        _speak_streamed_if_unmuted(response)
    except _Aborted:
        print("[COMPUTER] Stopped.")
    finally:
        _abort.clear()


def main() -> None:
    import webbrowser
    from jarvis.web import start_web_background

    print("[COMPUTER] Starting up...")
    print("[COMPUTER] Keys: Esc = stop | F2 = type | INSERT = mute/unmute")

    start_web_background(port=7860)
    print("[COMPUTER] Web UI: http://localhost:7860")

    threading.Thread(target=_keyboard_listener, daemon=True).start()

    webbrowser.open("http://localhost:7860")

    _speak_if_unmuted("COMPUTER online. Bereit, Captain.")
    listen_for_wake_word(handle_wake)


if __name__ == "__main__":
    main()
