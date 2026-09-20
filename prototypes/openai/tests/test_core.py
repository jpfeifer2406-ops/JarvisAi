import asyncio
from concurrent.futures import ThreadPoolExecutor
import pytest
from pydantic import ValidationError
from computer.runtime import Runtime
from computer.contracts import Run, Provider, Risk
from computer.broker import Broker
from computer.documents import Documents
from computer.tools import Tool, Empty
from computer.network import public_url
from computer.memory import Memory


async def pending(rt, sid):
    for _ in range(100):
        items = rt.broker.list_for(sid)
        if items:
            return items[0]
        await asyncio.sleep(0.01)
    raise AssertionError("No approval appeared")


@pytest.mark.parametrize(
    "tool,phrase", [("execute_probe", "Aktion freigeben"), ("critical_probe", "Kritische Aktion bestätigen")]
)
async def test_real_sdk_approval_resume(tmp_path, tool, phrase):
    rt = Runtime(tmp_path)
    s = rt.new_session()
    r = await rt.start(s.id, text="/execute" if tool == "execute_probe" else "/critical")
    p = await pending(rt, s.id)
    assert not r.results
    await rt.broker.decide(s.id, p["id"], p["digest"], phrase, True)
    await r.task
    assert r.status == "completed"
    assert r.results == [{"tool": tool, "status": "simulated"}]
    assert "simulated" in r.output
    await rt.close()


@pytest.mark.parametrize(
    "phrase",
    [
        "ja",
        "Ich möchte die Aktion freigeben nicht",
        "Was bedeutet Kritische Aktion bestätigen?",
        "Aktion freigeben?",
        "nicht Aktion freigeben",
        '"Aktion freigeben"',
    ],
)
async def test_false_phrases_never_approve(tmp_path, phrase):
    rt = Runtime(tmp_path)
    s = rt.new_session()
    r = await rt.start(s.id, tool="execute_probe")
    p = await pending(rt, s.id)
    with pytest.raises(ValueError):
        await rt.broker.decide(s.id, p["id"], p["digest"], phrase, True)
    assert not r.results
    await rt.stop(s.id, r.id)
    assert not rt.broker.list_for(s.id)


async def test_parallel_approval_at_most_once(tmp_path):
    rt = Runtime(tmp_path)
    s = rt.new_session()
    r = await rt.start(s.id, tool="execute_probe")
    p = await pending(rt, s.id)
    decisions = await asyncio.gather(
        *[rt.broker.decide(s.id, p["id"], p["digest"], "Aktion freigeben", True) for _ in range(10)],
        return_exceptions=True,
    )
    await r.task
    assert sum(x is None for x in decisions) == 1
    assert len(r.results) == 1


async def test_denial_and_cross_session(tmp_path):
    rt = Runtime(tmp_path)
    s = rt.new_session()
    other = rt.new_session()
    r = await rt.start(s.id, text="/critical")
    p = await pending(rt, s.id)
    with pytest.raises(ValueError):
        await rt.broker.decide(other.id, p["id"], p["digest"], p["phrase"], True)
    with pytest.raises(ValueError):
        rt.get_run(other.id, r.id)
    await rt.broker.decide(s.id, p["id"], p["digest"], "", False)
    await r.task
    assert "denied" in r.output


async def test_cancel_waiting_then_new_run(tmp_path):
    rt = Runtime(tmp_path)
    s = rt.new_session()
    r = await rt.start(s.id, text="/execute")
    p = await pending(rt, s.id)
    await rt.stop(s.id, r.id)
    with pytest.raises(ValueError):
        await rt.broker.decide(s.id, p["id"], p["digest"], p["phrase"], True)
    r2 = await rt.start(s.id, text="Hallo")
    await r2.task
    assert r2.status == "completed" and r.status == "cancelled"


async def test_pause_before_tool_and_resume(tmp_path):
    rt = Runtime(tmp_path)
    s = rt.new_session()
    r = await rt.start(s.id, tool="execute_probe")
    p = await pending(rt, s.id)
    await rt.pause(s.id, r.id)
    await rt.broker.decide(s.id, p["id"], p["digest"], p["phrase"], True)
    await asyncio.sleep(0.01)
    assert not r.results
    await rt.resume(s.id, r.id)
    await r.task
    assert len(r.results) == 1


@pytest.mark.parametrize("phase", ["llm", "tool"])
async def test_cancel_inflight(tmp_path, phase):
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def slow(*args):
        started.set()
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.set()

    rt = Runtime(tmp_path)
    s = rt.new_session()
    if phase == "llm":
        rt.agent.respond = slow
        r = await rt.start(s.id, text="hello")
    else:
        rt.registry.register(Tool("slow", "test", Empty, Risk.READ, slow))
        r = await rt.start(s.id, tool="slow")
    await started.wait()
    await asyncio.wait_for(rt.stop(s.id, r.id), 1)
    assert cancelled.is_set() and r.status == "cancelled"


async def test_invalid_arguments_result_and_cloud_device(tmp_path):
    rt = Runtime(tmp_path, local_device=False)
    s = rt.new_session()
    r = Run("r", s.id, Provider())
    out = await rt.registry.dispatch(
        r, "create_document", {"title": "x", "text": "y", "format": "txt", "extra": True}
    )
    assert out.status == "error"

    async def broken(*args):
        return "Erledigt"

    rt.registry.register(Tool("broken", "test", Empty, Risk.READ, broken))
    assert (await rt.registry.dispatch(r, "broken", {})).status == "error"
    assert (await rt.registry.dispatch(r, "run_python", {})).status == "denied"
    assert (await rt.registry.dispatch(r, "device_action", {"action": "lock_screen"})).status == "denied"


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://example.com",
        "https://127.0.0.1/",
        "https://[::1]/",
        "https://169.254.169.254/",
        "https://localhost/",
        "https://example.com:444/",
        "https://user:pass@example.com/",
    ],
)
def test_url_rejections(url):
    with pytest.raises(ValueError):
        public_url(url)


@pytest.mark.parametrize("kind", ["txt", "docx", "pdf"])
def test_documents_integrity_revision_long(tmp_path, kind):
    d = Documents(tmp_path)
    original = "A\n" + "Text mit Umlauten äöü.\n" * 1800 + "ENDMARKER"
    doc = d.create("Logbuch", original, kind)
    new = d.revise(doc["id"], "A", "AA")
    assert d.read(doc["id"])[1] == original
    assert d.read(new["id"])[1] == original.replace("A", "AA")
    _, _, blob = d.read(new["id"])
    if kind == "docx":
        import io
        from docx import Document

        assert Document(io.BytesIO(blob)).paragraphs[0].text == "AA"
    if kind == "pdf":
        import io
        from pypdf import PdfReader

        assert "ENDMAARKER" in "".join(p.extract_text() for p in PdfReader(io.BytesIO(blob)).pages)


def test_document_concurrency_and_tamper(tmp_path):
    d = Documents(tmp_path)
    with ThreadPoolExecutor(8) as pool:
        docs = list(pool.map(lambda _: d.create("same", "content", "txt"), range(12)))
    assert len({x["id"] for x in docs}) == 12
    with pytest.raises(ValueError):
        d.read("../outside")
    (d.path(docs[0]["id"]) / "source.txt").write_text("changed")
    with pytest.raises(ValueError):
        d.read(docs[0]["id"])


def test_memory_rejects_secrets_and_free_text():
    m = Memory()
    with pytest.raises(ValidationError):
        m.set({"password": "synthetic"})
    with pytest.raises(ValidationError):
        m.set({"address": "my password is synthetic"})
    m.set({"address": "neutral", "response_length": "kurz"})
    m.clear()
    assert m.preferences.address == "Captain"


async def test_expiry_and_digest_binding():
    b = Broker(ttl=0.03)
    r = Run("r", "s", Provider())
    task = asyncio.create_task(b.authorize(r, "probe", {"x": 1}, Risk.CRITICAL))
    await asyncio.sleep(0.005)
    p = b.list_for("s")[0]
    with pytest.raises(ValueError):
        await b.decide("s", p["id"], "0" * 64, p["phrase"], True)
    assert await task is False
    assert not b.list_for("s")
