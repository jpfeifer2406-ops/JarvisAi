"""Pipecat carries frames; COMPUTER owns turns and all permissions.

Experimental live adapter. Not validated against real audio devices or a server.
One session owns one room and one pipeline. Client tokens cannot publish data.
"""

from __future__ import annotations
import asyncio
import math
import os
import struct
from datetime import timedelta
from livekit import api
from pipecat.frames.frames import InputAudioRawFrame, TTSAudioRawFrame, InterruptionFrame
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineWorker, PipelineParams
from pipecat.pipeline.runner import PipelineRunner
from pipecat.transports.livekit.transport import LiveKitTransport, LiveKitParams
from ..voice import AudioOwner, AudioState, VoiceSession
from .speech_process import LocalSpeech
from .wake import ComputerWake


def room_token(sid, identity):
    return (
        api.AccessToken(os.environ["LIVEKIT_API_KEY"], os.environ["LIVEKIT_API_SECRET"])
        .with_identity(identity)
        .with_ttl(timedelta(minutes=5))
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room="computer-" + sid,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=False,
                can_update_own_metadata=False,
                can_publish_sources=["microphone"],
            )
        )
        .to_jwt()
    )


class ComputerAudioProcessor(FrameProcessor):
    def __init__(self, runtime, sid, owner, speech=None, wake=None):
        super().__init__()
        self.rt, self.sid = runtime, sid
        self.speech = speech or LocalSpeech()
        self.wake_detector = wake or ComputerWake()
        self.voice = VoiceSession(
            sid, owner, self.speech.transcribe, self.agent, self.speech.synthesize, self.play, self.flush
        )
        self.recorded = bytearray()
        self.silent = 0.0
        self.voiced = 0.0

    async def agent(self, text):
        run = await self.rt.start(self.sid, text=text)
        try:
            await asyncio.shield(run.task)
        except asyncio.CancelledError:
            # No call to Runtime.stop here: avoid voice-stop -> voice-task recursion.
            run.cancelled.set()
            run.resume_gate.set()
            await self.rt.broker.cancel(run.id)
            run.task.cancel()
            await asyncio.gather(run.task, return_exceptions=True)
            raise
        if run.status != "completed":
            raise RuntimeError("Agent turn failed")
        return run.output

    async def flush(self):
        self.recorded.clear()
        self.silent = 0.0
        self.voiced = 0.0
        await self.push_frame(InterruptionFrame())

    async def play(self, audio):
        pcm, sample_rate = audio
        # Bound transport queue and keep cancellation observable between 20ms frames.
        chunk = max(2, int(sample_rate * 0.02) * 2)
        for start in range(0, len(pcm), chunk):
            await self.push_frame(TTSAudioRawFrame(pcm[start : start + chunk], sample_rate, 1))
            await asyncio.sleep(0.02)

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if not isinstance(frame, InputAudioRawFrame):
            await self.push_frame(frame, direction)
            return
        if frame.sample_rate != 16000 or frame.num_channels != 1 or len(frame.audio) % 2:
            self.voice.state = AudioState.ERROR
            return
        self.voice.tick()
        # Single input stream, no second microphone opened by wake or STT.
        try:
            detected = await asyncio.to_thread(self.wake_detector.detect, frame.audio)
            values = struct.unpack("<" + "h" * (len(frame.audio) // 2), frame.audio)
            rms = math.sqrt(sum(x * x for x in values) / max(1, len(values))) / 32768
            seconds = len(frame.audio) / 32000
            if self.voice.state in (AudioState.STT, AudioState.AGENT, AudioState.TTS, AudioState.PLAYBACK):
                self.voiced = self.voiced + seconds if rms > 0.025 else 0
                if detected or self.voiced >= 0.25:
                    await self.voice.stop(sleep=False)  # experimental energy-based barge-in
                return
            if self.voice.state in (AudioState.SLEEP, AudioState.ERROR):
                if detected:
                    self.voice.wake()
                return
            if self.voice.state == AudioState.LISTENING:
                if rms > 0.015:
                    self.voice.state = AudioState.RECORDING
                else:
                    return
            self.recorded.extend(frame.audio)
            self.silent = self.silent + seconds if rms < 0.015 else 0  # consecutive silence only
            if self.silent >= 0.8 or len(self.recorded) >= 20 * 32000:
                recording = bytes(self.recorded)
                self.recorded.clear()
                self.silent = 0
                await self.voice.submit(recording)
        except asyncio.CancelledError:
            raise
        except Exception:
            await self.voice.stop()
            self.voice.state = AudioState.ERROR
            self.voice.error = "Audio-Geräte-/Verarbeitungsfehler; erneut verbinden."


class LiveKitVoice:
    def __init__(self, runtime):
        self.rt = runtime
        self.owner = AudioOwner()
        self.processor = None
        self.task = None
        self.runner_task = None

    async def connect(self, sid):
        self.rt.session(sid)
        if self.owner.session_id:
            raise ValueError("Audio bereits belegt. Zuerst trennen.")
        url = os.environ.get("LIVEKIT_URL", "")
        if not (url.startswith("wss://") or url in ("ws://127.0.0.1:7880", "ws://localhost:7880")):
            raise ValueError("LiveKit lokal oder über TLS konfigurieren.")
        processor = ComputerAudioProcessor(self.rt, sid, self.owner)
        try:
            transport = LiveKitTransport(
                url,
                room_token(sid, "computer-worker"),
                "computer-" + sid,
                LiveKitParams(
                    audio_in_enabled=True,
                    audio_out_enabled=True,
                    audio_in_sample_rate=16000,
                    audio_out_sample_rate=24000,
                    audio_out_queue_size_ms=100,
                ),
            )
            pipeline = Pipeline([transport.input(), processor, transport.output()])
            self.task = PipelineWorker(
                pipeline, params=PipelineParams(audio_in_sample_rate=16000, audio_out_sample_rate=24000)
            )
            self.processor = processor

            @transport.event_handler("on_participant_disconnected")
            async def participant_left(transport, participant_id):
                await processor.voice.stop()

            self.runner_task = asyncio.create_task(self._run())
            return {
                "url": url,
                "token": room_token(sid, "computer-client"),
                "room": "computer-" + sid,
                "status": "connecting",
                "validated": False,
            }
        except BaseException:
            self.owner.release(sid)
            raise

    async def _run(self):
        try:
            await PipelineRunner(handle_sigint=False).run(self.task)
        except Exception:
            if self.processor:
                self.processor.voice.state = AudioState.ERROR
                self.processor.voice.error = "LiveKit-Verbindung fehlgeschlagen."
        finally:
            if self.processor:
                await self.processor.voice.close()
                if hasattr(self.processor.speech, "close"):
                    await self.processor.speech.close()

    async def stop(self, sid):
        if self.processor and self.owner.session_id == sid:
            await self.processor.voice.stop()

    async def disconnect(self, sid):
        if self.owner.session_id != sid:
            return
        await self.stop(sid)
        if self.task:
            await self.task.cancel()
        if self.runner_task:
            try:
                await asyncio.wait_for(asyncio.shield(self.runner_task), 5)
            except TimeoutError:
                self.runner_task.cancel()
                await asyncio.gather(self.runner_task, return_exceptions=True)
        self.owner.release(sid)
        self.processor = None

    def view(self, sid):
        if not self.processor or self.owner.session_id != sid:
            return {"status": "not_connected", "validated": False}
        return {
            "status": self.processor.voice.state.value,
            "error": self.processor.voice.error,
            "validated": False,
        }
