"""COMPUTER audio state/ownership independent of transport and TTS provider."""

from __future__ import annotations
import asyncio
import time
from enum import StrEnum


class AudioState(StrEnum):
    SLEEP = "sleep"
    LISTENING = "listening"
    RECORDING = "recording"
    STT = "stt"
    AGENT = "agent"
    TTS = "tts"
    PLAYBACK = "playback"
    ERROR = "error"


class AudioOwner:
    def __init__(self):
        self.session_id = None

    def acquire(self, sid):
        if self.session_id is not None and self.session_id != sid:
            raise ValueError("Audio wird bereits von einer anderen Sitzung verwendet.")
        self.session_id = sid

    def release(self, sid):
        if self.session_id == sid:
            self.session_id = None


class VoiceSession:
    """One turn task, no detached inference/playback after stop.

    Adapters MUST propagate cancellation and finish their cleanup before returning.
    Text from STT is never a trusted permission-broker approval channel.
    """

    def __init__(self, sid, owner, stt, agent, tts, playback, flush, idle_seconds=120):
        owner.acquire(sid)
        self.sid, self.owner = sid, owner
        self.stt, self.agent, self.tts, self.playback, self.flush = stt, agent, tts, playback, flush
        self.idle_seconds = idle_seconds
        self.state = AudioState.SLEEP
        self.last_activity = time.monotonic()
        self.task = None
        self.epoch = 0
        self.error = None

    def wake(self):
        if self.state in (AudioState.SLEEP, AudioState.ERROR):
            self.state = AudioState.LISTENING
            self.error = None
        self.last_activity = time.monotonic()

    def tick(self):
        if self.state == AudioState.LISTENING and time.monotonic() - self.last_activity > self.idle_seconds:
            self.state = AudioState.SLEEP

    async def submit(self, pcm):
        if self.state not in (AudioState.LISTENING, AudioState.RECORDING):
            raise ValueError("Voice ist nicht aufnahmebereit.")
        await self.stop(sleep=False)
        epoch = self.epoch
        self.task = asyncio.create_task(self._turn(pcm, epoch))

    async def _turn(self, pcm, epoch):
        try:
            self.state = AudioState.STT
            text = await self.stt(pcm)
            if epoch != self.epoch:
                return
            if text.strip().casefold().rstrip(".!?") in ("ruhemodus", "computer ruhemodus"):
                self.state = AudioState.SLEEP
                return
            if not text.strip():
                return
            self.state = AudioState.AGENT
            response = await self.agent(text)
            if epoch != self.epoch:
                return
            self.state = AudioState.TTS
            audio = await self.tts(response)
            if epoch != self.epoch:
                return
            self.state = AudioState.PLAYBACK
            await self.playback(audio)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.state = AudioState.ERROR
            self.error = "Audio-/Modellfehler. Geräte und lokale Modelle prüfen; erneut aktivieren."
            await self.flush()
        finally:
            if epoch == self.epoch and self.state not in (AudioState.SLEEP, AudioState.ERROR):
                self.state = AudioState.LISTENING
            self.last_activity = time.monotonic()

    async def stop(self, sleep=True):
        self.epoch += 1
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        await self.flush()
        self.state = AudioState.SLEEP if sleep else AudioState.LISTENING
        self.last_activity = time.monotonic()

    async def close(self):
        await self.stop()
        self.owner.release(self.sid)
