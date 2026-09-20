from __future__ import annotations
import asyncio
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from .contracts import Run, Provider
from .broker import Broker
from .documents import Documents
from .integrations import Integrations
from .memory import Memory
from .tools import Registry
from .adapters.openai_agent import OpenAIAgent
from .adapters.drive import DriveReader


@dataclass
class Session:
    id: str
    expires: float
    provider: Provider = field(default_factory=Provider)
    history: list[dict] = field(default_factory=list)
    memory: Memory = field(default_factory=Memory)
    runs: dict[str, Run] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class Runtime:
    def __init__(self, root: Path, agent_factory=OpenAIAgent, local_device=True):
        self.root = root
        self.sessions: dict[str, Session] = {}
        self.broker = Broker()
        self.integrations = Integrations(DriveReader())
        self.registry = Registry(
            self.broker, self.documents_for, self.integrations, local_device=local_device
        )
        self.agent = agent_factory(self.registry)
        self.voice = None

    def new_session(self):
        if len(self.sessions) >= 16:
            raise ValueError("Sitzungslimit erreicht. Abgelaufene Sitzungen werden bereinigt.")
        s = Session(secrets.token_hex(24), time.monotonic() + 8 * 3600)
        self.sessions[s.id] = s
        return s

    def session(self, sid):
        s = self.sessions.get(sid)
        if not s or s.expires <= time.monotonic():
            raise PermissionError("Sitzung abgelaufen.")
        return s

    def documents_for(self, sid):
        self.session(sid)
        return Documents(self.root / sid / "documents")

    def active(self, session):
        return next((r for r in session.runs.values() if r.task and not r.task.done()), None)

    async def start(self, sid, text="", tool=None, arguments=None):
        session = self.session(sid)
        async with session.lock:
            if self.active(session):
                raise ValueError("Sitzung hat bereits einen aktiven Auftrag.")
            run = Run(secrets.token_hex(16), sid, session.provider.model_copy(deep=True))
            session.runs[run.id] = run
            # Retain bounded terminal metadata only.
            while len(session.runs) > 30:
                session.runs.pop(next(iter(session.runs)))
            run.task = asyncio.create_task(self._work(session, run, text, tool, arguments))
            return run

    async def _work(self, session, run, text, tool, arguments):
        try:
            if tool:
                result = await self.registry.dispatch(run, tool, arguments or {})
                run.output = result.model_dump_json()
            else:
                preferences = session.memory.preferences
                context = [
                    {
                        "role": "user",
                        "content": f"Sitzungsvorlieben: Anrede {preferences.address}; Antwortlänge {preferences.response_length}.",
                    }
                ] + list(session.history)
                run.output = await self.agent.respond(text, context, run, self.registry.dispatch)
                session.history.extend(
                    [{"role": "user", "content": text}, {"role": "assistant", "content": run.output}]
                )
                # Explicit bounded conversation, no silent recursive summary loss.
                session.history[:] = session.history[-16:]
            await run.checkpoint()
            run.status = "completed"
        except asyncio.CancelledError:
            run.status = "cancelled"
            run.output = (
                "Auftrag abgebrochen. Bereits abgeschlossene Schritte werden nicht rückgängig gemacht."
            )
        except Exception:
            run.status = "error"
            run.error = "Auftrag fehlgeschlagen. Provider, Modell und lokale Konfiguration prüfen."
        finally:
            await self.broker.cancel(run.id)

    def get_run(self, sid, rid):
        s = self.session(sid)
        if rid not in s.runs:
            raise ValueError("Auftrag gehört nicht zu dieser Sitzung.")
        return s.runs[rid]

    async def stop(self, sid, rid):
        run = self.get_run(sid, rid)
        run.cancelled.set()
        run.resume_gate.set()
        await self.broker.cancel(run.id)
        if run.task and not run.task.done():
            run.task.cancel()
            await asyncio.gather(run.task, return_exceptions=True)
            run.status = "cancelled"
        if self.voice:
            await self.voice.stop(sid)

    async def pause(self, sid, rid):
        run = self.get_run(sid, rid)
        if not run.task or run.task.done():
            raise ValueError("Auftrag nicht aktiv.")
        run.resume_gate.clear()
        run.status = "pause_requested"  # In-flight I/O is not falsely claimed frozen.

    async def resume(self, sid, rid):
        run = self.get_run(sid, rid)
        if run.cancelled.is_set() or not run.task or run.task.done():
            raise ValueError("Abgebrochene/beendete Aufträge können nicht fortgesetzt werden.")
        run.resume_gate.set()
        run.status = "running"

    async def close_session(self, sid):
        s = self.sessions.get(sid)
        if not s:
            return
        for run in list(s.runs.values()):
            # stop() requires unexpired session; cancellation here also handles expiration.
            run.cancelled.set()
            run.resume_gate.set()
            await self.broker.cancel(run.id)
            if run.task and not run.task.done():
                run.task.cancel()
                await asyncio.gather(run.task, return_exceptions=True)
        if self.voice:
            await self.voice.disconnect(sid)
        s.history.clear()
        s.memory.clear()
        self.integrations.tabs.pop(sid, None)
        self.sessions.pop(sid, None)

    async def close(self):
        for sid in list(self.sessions):
            await self.close_session(sid)

    def view(self, sid):
        s = self.session(sid)
        return {
            "session": sid,
            "provider": s.provider.model_dump(),
            "runs": [
                {"id": r.id, "status": r.status, "output": r.output, "error": r.error, "tools": r.results}
                for r in s.runs.values()
            ],
            "pending": self.broker.list_for(sid),
            "memory": s.memory.preferences.model_dump(),
            "voice": self.voice.view(sid) if self.voice else {"status": "not_connected", "validated": False},
            "browser": self.integrations.browser_status(sid).model_dump(),
        }
