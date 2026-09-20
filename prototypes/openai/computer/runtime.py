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
from .diagnostics import Diagnostics, failure
from .provider_check import check_provider, api_key
from .selfcheck import startup_checks


@dataclass
class Session:
    id: str
    expires: float
    provider: Provider = field(default_factory=Provider)
    api_key: str = field(default="", repr=False)
    diagnostics: Diagnostics = field(default_factory=lambda: Diagnostics(secrets.token_hex(8)))
    provider_check: dict = field(default_factory=lambda: {"status": "SIMULATED", "message": "Offline-Demo"})
    checked_at: float = 0
    voice_error: str | None = None
    history: list[dict] = field(default_factory=list)
    memory: Memory = field(default_factory=Memory)
    runs: dict[str, Run] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class Runtime:
    def __init__(self, root: Path, agent_factory=OpenAIAgent, local_device=True):
        self.root = root
        self.sessions: dict[str, Session] = {}
        self.broker = Broker(event=self.event)
        self.checks = {}
        self.check_task = None
        self.integrations = Integrations(DriveReader())
        self.registry = Registry(
            self.broker, self.documents_for, self.integrations, local_device=local_device
        )
        self.agent = agent_factory(self.registry)
        self.voice = None
        self.registry.event = self.event

    def new_session(self):
        if len(self.sessions) >= 16:
            raise ValueError("Sitzungslimit erreicht. Abgelaufene Sitzungen werden bereinigt.")
        s = Session(secrets.token_hex(24), time.monotonic() + 8 * 3600)
        self.sessions[s.id] = s
        s.diagnostics.emit("session", "created", provider=s.provider)
        for component, check in self.checks.items():
            s.diagnostics.emit(component, check["status"], level="INFO" if check["status"] == "READY" else "WARNING")
        return s

    def event(self, run, component, event, level="INFO", error=None):
        s = self.sessions.get(run.session_id)
        if s:
            s.diagnostics.emit(component, event, level=level, run=run, error=error)

    async def selfcheck(self):
        try:
            self.checks = await startup_checks()
            for s in list(self.sessions.values()):
                for component, check in self.checks.items():
                    s.diagnostics.emit(component, check["status"], level="INFO" if check["status"] == "READY" else "WARNING")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.checks["selfcheck"] = {"status": "UNAVAILABLE", **failure(exc)}

    async def check_provider(self, s):
        try:
            s.provider_check = await check_provider(s.provider, api_key(s))
            s.diagnostics.emit("provider", "check." + s.provider_check["status"], provider=s.provider)
        except Exception as exc:
            s.provider_check = {"status": "UNAVAILABLE", **failure(exc)}
            s.diagnostics.emit("provider", "check.failed", level="ERROR", provider=s.provider, error=exc)
        s.checked_at = time.monotonic()
        return s.provider_check

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
            run.api_key = api_key(session)
            session.runs[run.id] = run
            self.event(run, "agent" if not tool else "tool", "run.started")
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
                if run.provider.kind != "demo" and time.monotonic() - session.checked_at > 60:
                    await self.check_provider(session)
                if run.provider.kind != "demo" and session.provider_check["status"] == "UNAVAILABLE":
                    run.status = "error"
                    run.error = session.provider_check["message"]
                    self.event(run, "agent", "preflight.failed", "WARNING")
                    return
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
            self.event(run, "agent", "run.completed")
        except asyncio.CancelledError:
            self.event(run, "agent", "run.cancelled")
            run.status = "cancelled"
            run.output = (
                "Auftrag abgebrochen. Bereits abgeschlossene Schritte werden nicht rückgängig gemacht."
            )
        except Exception as exc:
            run.status = "error"
            run.error = failure(exc)["message"] + " Diagnose-ID: " + session.diagnostics.id
            self.event(run, "agent", "run.failed", "ERROR", exc)
        finally:
            run.api_key = ""
            await self.broker.cancel(run.id)

    def get_run(self, sid, rid):
        s = self.session(sid)
        if rid not in s.runs:
            raise ValueError("Auftrag gehört nicht zu dieser Sitzung.")
        return s.runs[rid]

    async def stop(self, sid, rid):
        run = self.get_run(sid, rid)
        self.event(run, "agent", "stop.requested")
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
        self.event(run, "agent", "pause.requested")
        run.resume_gate.clear()
        run.status = "pause_requested"  # In-flight I/O is not falsely claimed frozen.

    async def resume(self, sid, rid):
        run = self.get_run(sid, rid)
        if run.cancelled.is_set() or not run.task or run.task.done():
            raise ValueError("Abgebrochene/beendete Aufträge können nicht fortgesetzt werden.")
        self.event(run, "agent", "resumed")
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
        s.api_key = ""
        s.diagnostics.events.clear()
        s.history.clear()
        s.memory.clear()
        self.integrations.tabs.pop(sid, None)
        self.sessions.pop(sid, None)

    async def close(self):
        if self.check_task and not self.check_task.done():
            self.check_task.cancel()
            await asyncio.gather(self.check_task, return_exceptions=True)
        for sid in list(self.sessions):
            await self.close_session(sid)

    def view(self, sid):
        s = self.session(sid)
        return {
            "session": sid,
            "provider": s.provider.model_dump(),
            "provider_check": s.provider_check,
            "diagnosis_id": s.diagnostics.id,
            "key_configured": bool(api_key(s)),
            "checks": self.checks,
            "checks_running": bool(self.check_task and not self.check_task.done()),
            "conversation": s.history,
            "voice_error": s.voice_error,
            "runs": [
                {"id": r.id, "status": r.status, "output": r.output, "error": r.error, "tools": r.results}
                for r in s.runs.values()
            ],
            "pending": self.broker.list_for(sid),
            "memory": s.memory.preferences.model_dump(),
            "voice": self.voice.view(sid) if self.voice else {"status": "not_connected", "validated": False},
            "browser": self.integrations.browser_status(sid).model_dump(),
        }
