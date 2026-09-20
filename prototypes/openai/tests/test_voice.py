import asyncio
import pytest
from computer.voice import VoiceSession, AudioOwner, AudioState


@pytest.mark.parametrize("phase", ["stt", "agent", "tts", "playback"])
async def test_cancel_at_every_audio_phase_no_late_playback(phase):
    started = asyncio.Event()
    ended = asyncio.Event()
    calls = []

    async def stage(name, result):
        calls.append(name)
        if name == phase:
            started.set()
            try:
                await asyncio.sleep(60)
            finally:
                ended.set()
        return result

    async def flush():
        calls.append("flush")

    owner = AudioOwner()
    voice = VoiceSession(
        "s",
        owner,
        lambda x: stage("stt", "Hallo"),
        lambda x: stage("agent", "Antwort"),
        lambda x: stage("tts", b"audio"),
        lambda x: stage("playback", None),
        flush,
    )
    voice.wake()
    await voice.submit(b"pcm")
    await started.wait()
    await asyncio.wait_for(voice.stop(), 1)
    assert ended.is_set() and voice.state == AudioState.SLEEP
    if phase != "playback":
        assert "playback" not in calls
    await voice.close()
    assert owner.session_id is None


async def test_audio_owner_recovery_sleep_followup():
    owner = AudioOwner()
    count = 0

    async def stt(pcm):
        return pcm.decode()

    async def agent(text):
        return text

    async def tts(text):
        nonlocal count
        count += 1
        if count == 1:
            raise RuntimeError("device error")
        return b"audio"

    async def sink(audio):
        pass

    async def flush():
        pass

    voice = VoiceSession("s", owner, stt, agent, tts, sink, flush, idle_seconds=0)
    with pytest.raises(ValueError):
        VoiceSession("other", owner, stt, agent, tts, sink, flush)
    voice.wake()
    await voice.submit(b"Hallo")
    await voice.task
    assert voice.state == AudioState.ERROR
    voice.wake()
    await voice.submit(b"Hallo")
    await voice.task
    assert voice.state == AudioState.LISTENING
    voice.tick()
    assert voice.state == AudioState.SLEEP
    voice.wake()
    await voice.submit(b"Ruhemodus")
    await voice.task
    assert voice.state == AudioState.SLEEP
    await voice.close()


def test_livekit_token_scope(monkeypatch):
    from computer.adapters.livekit_voice import room_token
    import jwt

    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "a" * 40)
    token = room_token("session-a", "client")
    data = jwt.decode(token, "a" * 40, algorithms=["HS256"])
    assert data["video"]["room"] == "computer-session-a"
    assert data["video"]["canPublishData"] is False
    assert data["video"]["canPublishSources"] == ["microphone"]
    assert data["exp"] - data["nbf"] <= 300


async def test_pipecat_real_frame_pipeline(tmp_path):
    from pipecat.frames.frames import InputAudioRawFrame
    from computer.adapters.livekit_voice import ComputerAudioProcessor
    from computer.runtime import Runtime

    class Wake:
        def detect(self, pcm):
            return True

    class Speech:
        async def transcribe(self, pcm):
            return "Hallo"

        async def synthesize(self, text):
            return b"\x00\x00" * 100, 24000

    rt = Runtime(tmp_path)
    session = rt.new_session()
    processor = ComputerAudioProcessor(rt, session.id, AudioOwner(), Speech(), Wake())
    # Process real input frames through the actual Pipecat processor.
    assert processor.voice.state == AudioState.SLEEP
    from pipecat.processors.frame_processor import FrameDirection

    await processor.process_frame(InputAudioRawFrame(b"\0\0" * 160, 16000, 1), FrameDirection.DOWNSTREAM)
    assert processor.voice.state == AudioState.LISTENING
    await rt.close()


async def test_pipecat_wake_record_stt_sdk_tts_frames(tmp_path):
    import struct
    from pipecat.frames.frames import InputAudioRawFrame, TTSAudioRawFrame, InterruptionFrame
    from pipecat.processors.frame_processor import FrameDirection
    from computer.adapters.livekit_voice import ComputerAudioProcessor
    from computer.runtime import Runtime

    class Wake:
        def detect(self, pcm):
            return True

    class Speech:
        async def transcribe(self, pcm):
            return "Hallo"

        async def synthesize(self, text):
            return b"\x01\x00" * 480, 24000

    rt = Runtime(tmp_path)
    session = rt.new_session()
    processor = ComputerAudioProcessor(rt, session.id, AudioOwner(), Speech(), Wake())
    emitted = []

    async def capture(frame, *args):
        emitted.append(frame)

    processor.push_frame = capture

    async def frame(pcm):
        await processor.process_frame(InputAudioRawFrame(pcm, 16000, 1), FrameDirection.DOWNSTREAM)

    await frame(b"\0\0" * 160)
    await frame(struct.pack("<h", 3000) * 1600)
    await frame(b"\0\0" * 16000)
    assert processor.voice.task is not None
    await processor.voice.task
    assert processor.voice.state == AudioState.LISTENING
    assert any(isinstance(f, TTSAudioRawFrame) for f in emitted)
    assert any(r.status == "completed" for r in session.runs.values())
    await processor.voice.close()
    assert isinstance(emitted[-1], InterruptionFrame)
    await rt.close()
