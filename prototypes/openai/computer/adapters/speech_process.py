"""Killable local inference helpers. Process separation is NOT a Python sandbox.

Models must already exist locally. No automatic downloads and no credentials in
command-line arguments. CPU default; GPU can be selected by the local operator.
"""

import asyncio
import json
import os
import sys
import tempfile
import wave
from pathlib import Path


class SpeechWorker:
    """One warm worker per audio owner. Stop destroys it; next turn recovers fresh."""

    def __init__(self):
        self.process = None
        self.lock = asyncio.Lock()

    async def close(self):
        process, self.process = self.process, None
        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 3)
            except TimeoutError:
                process.kill()
                await process.wait()

    async def call(self, mode, payload, output):
        async with self.lock:
            try:
                if not self.process or self.process.returncode is not None:
                    executable = os.environ.get("COMPUTER_VOICE_PYTHON", sys.executable)
                    environment = os.environ.copy()
                    threads = environment.get("COMPUTER_CPU_THREADS", "2")
                    environment.update(
                        {
                            "OMP_NUM_THREADS": threads,
                            "MKL_NUM_THREADS": threads,
                            "TOKENIZERS_PARALLELISM": "false",
                        }
                    )
                    self.process = await asyncio.create_subprocess_exec(
                        executable,
                        "-m",
                        "computer.adapters.speech_worker",
                        "serve",
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                        env=environment,
                    )
                request = {"mode": mode, "payload": payload, "output": str(output)}
                self.process.stdin.write((json.dumps(request) + "\n").encode())
                await self.process.stdin.drain()
                async with asyncio.timeout(180):
                    reply = await self.process.stdout.readline()
                if not reply or not json.loads(reply).get("ok"):
                    raise RuntimeError("Local speech worker failed")
            except BaseException:
                await self.close()
                raise


class LocalSpeech:
    def __init__(self):
        self.worker = SpeechWorker()
        self.profile = json.loads((Path(__file__).parents[1] / "profiles/voice.json").read_text())

    async def transcribe(self, pcm):
        model = os.environ.get("COMPUTER_STT_MODEL")
        if not model or not Path(model).is_dir():
            raise ValueError("COMPUTER_STT_MODEL muss ein lokales faster-whisper-Modellverzeichnis sein.")
        with tempfile.TemporaryDirectory(prefix="computer-stt-") as folder:
            source, target = Path(folder) / "input.wav", Path(folder) / "text.json"
            with wave.open(str(source), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(pcm)
            await self.worker.call("stt", {"model": model, "input": str(source)}, target)
            return json.loads(target.read_text())["text"]

    async def synthesize(self, text):
        model = os.environ.get("COMPUTER_QWEN_MODEL")
        if not model or not Path(model).is_dir():
            raise ValueError("COMPUTER_QWEN_MODEL muss ein lokales Qwen-Modellverzeichnis sein.")
        with tempfile.TemporaryDirectory(prefix="computer-tts-") as folder:
            target = Path(folder) / "voice.wav"
            await self.worker.call(
                "tts",
                {
                    "model": model,
                    "text": text[:600],
                    "profile": self.profile,
                    "reference": os.environ.get("COMPUTER_VOICE_REFERENCE"),
                    "device": os.environ.get("COMPUTER_VOICE_DEVICE", "cpu"),
                },
                target,
            )
            with wave.open(str(target), "rb") as wav:
                if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                    raise ValueError("Ungültiges PCM-Format")
                return wav.readframes(wav.getnframes()), wav.getframerate()

    async def close(self):
        await self.worker.close()
