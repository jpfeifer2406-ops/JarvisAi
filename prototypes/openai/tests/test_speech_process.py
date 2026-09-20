import asyncio
import sys
import pytest
from computer.adapters.speech_process import SpeechWorker


async def test_warm_worker_reuse_cancel_and_restart(monkeypatch, tmp_path):
    real_spawn = asyncio.create_subprocess_exec
    spawned = []
    script = """import json,sys,time
for line in sys.stdin:
 request=json.loads(line)
 if request["mode"]=="slow":time.sleep(60)
 print('{"ok":true}',flush=True)
"""

    async def spawn(*args, **kwargs):
        process = await real_spawn(sys.executable, "-u", "-c", script, **kwargs)
        spawned.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    worker = SpeechWorker()
    try:
        await worker.call("fast", {}, tmp_path / "out")
        await worker.call("fast", {}, tmp_path / "out")
        assert len(spawned) == 1
        task = asyncio.create_task(worker.call("slow", {}, tmp_path / "out"))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert spawned[0].returncode is not None and worker.process is None
        await worker.call("fast", {}, tmp_path / "out")
        assert len(spawned) == 2
    finally:
        await worker.close()
    assert all(p.returncode is not None for p in spawned)


async def test_worker_error_closes_process(monkeypatch, tmp_path):
    real_spawn = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        return await real_spawn(
            sys.executable,
            "-u",
            "-c",
            "import sys;sys.stdin.readline();print('{\"ok\":false}',flush=True)",
            **kwargs,
        )

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    worker = SpeechWorker()
    with pytest.raises(RuntimeError):
        await worker.call("stt", {}, tmp_path / "out")
    assert worker.process is None
