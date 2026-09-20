import asyncio
import pytest
from computer.contracts import Run, Provider
from computer.runtime import Runtime


async def test_real_sdk_read_prepare_no_approval(tmp_path):
    rt = Runtime(tmp_path)
    s = rt.new_session()
    r = await rt.start(s.id, text="/entwurf")
    await r.task
    assert r.status == "completed"
    assert len(rt.documents_for(s.id).list()) == 1
    assert not rt.broker.list_for(s.id)
    r = await rt.start(s.id, text="/dokumente")
    await r.task
    assert r.status == "completed" and "Logbuch" in r.output
    await rt.close()


async def test_provider_model_key_rotation_and_settings(tmp_path, monkeypatch):
    import computer.adapters.openai_agent as adapter

    made = []
    seen = []

    class Client:
        def __init__(self, **kw):
            self.kw = kw
            made.append(self)

        async def close(self):
            await self.kw["http_client"].aclose()
            self.closed = True

    class Model(adapter.DemoModel):
        def __init__(self, **kw):
            self.kw = kw

    async def runner(agent, **kwargs):
        seen.append(agent)

        class Result:
            final_output = "synthetic"

        return Result()

    monkeypatch.setattr(adapter, "AsyncOpenAI", Client)
    monkeypatch.setattr(adapter, "OpenAIResponsesModel", Model)
    monkeypatch.setattr(adapter, "OpenAIChatCompletionsModel", Model)
    monkeypatch.setattr(adapter.Runner, "run", runner)
    rt = Runtime(tmp_path)
    s = rt.new_session()
    for kind, key, name, temp in [
        ("openai", "synthetic-old", "model-one", 0.2),
        ("openai", "synthetic-new", "model-two", 0.5),
        ("local", "unused", "local-model", 0.8),
    ]:
        monkeypatch.setenv("OPENAI_API_KEY", key)
        r = Run("r", s.id, Provider(kind=kind, model=name, temperature=temp))
        await rt.agent.respond("test", [], r, rt.registry.dispatch)
    assert made[0].kw["api_key"] == "synthetic-old" and made[1].kw["api_key"] == "synthetic-new"
    assert all(c.closed for c in made)
    assert made[2].kw["base_url"] == "http://127.0.0.1:11434/v1"
    assert [a.model.kw["model"] for a in seen] == ["model-one", "model-two", "local-model"]
    assert [a.model_settings.temperature for a in seen] == [0.2, 0.5, 0.8]


async def test_dns_resolver_blocks_private_resolution(monkeypatch):
    from computer.network import PublicResolver, ThreadedResolver

    async def fake(*a, **kw):
        return [{"host": "127.0.0.1"}]

    monkeypatch.setattr(ThreadedResolver, "resolve", fake)
    resolver = PublicResolver()
    with pytest.raises(ValueError):
        await resolver.resolve("looks-public.example", 443)
    await resolver.close()


async def test_sessions_are_isolated(tmp_path):
    rt = Runtime(tmp_path)
    a = rt.new_session()
    b = rt.new_session()
    ra = await rt.start(a.id, text="/entwurf")
    rb = await rt.start(b.id, text="Hallo")
    await asyncio.gather(ra.task, rb.task)
    assert len(rt.documents_for(a.id).list()) == 1 and not rt.documents_for(b.id).list()
    assert rt.broker.list_for(b.id) == []
    await rt.close_session(a.id)
    with pytest.raises(PermissionError):
        rt.session(a.id)
    assert rt.session(b.id)
    await rt.close()
