"""COMPUTER policy authority. Single-process asyncio ownership is deliberate.

The SDK cannot approve, alter policy, or invoke the underlying handlers directly.
Approvals are exact, scoped, one-shot and expire. Speech is not an identity factor.
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from .contracts import Risk, Run


@dataclass
class Pending:
    id: str
    run_id: str
    session_id: str
    tool: str
    arguments_json: str
    digest: str
    risk: Risk
    expires: float
    future: asyncio.Future

    def public(self):
        return {"id": self.id, "run_id": self.run_id, "tool": self.tool,
                "arguments": json.loads(self.arguments_json), "digest": self.digest,
                "risk": self.risk.value, "expires_in": max(0, round(self.expires-time.monotonic())),
                "phrase": "Kritische Aktion bestätigen" if self.risk == Risk.CRITICAL else "Aktion freigeben"}


class Broker:
    def __init__(self, ttl=120):
        self.ttl = ttl
        self.pending: dict[str, Pending] = {}
        self.lock = asyncio.Lock()
        self.audit: list[dict] = []  # Metadata only; never tool arguments or secrets.

    async def authorize(self, run: Run, tool: str, arguments: dict, risk: Risk) -> bool:
        await run.checkpoint()
        if risk in (Risk.READ, Risk.PREPARE):
            return True
        encoded = json.dumps(arguments, sort_keys=True, ensure_ascii=False, allow_nan=False)
        action = Pending(secrets.token_urlsafe(24), run.id, run.session_id, tool, encoded,
                         hashlib.sha256(encoded.encode()).hexdigest(), risk,
                         time.monotonic()+self.ttl, asyncio.get_running_loop().create_future())
        async with self.lock:
            self.pending[action.id] = action
        run.status = "awaiting_approval"
        try:
            approved = await asyncio.wait_for(action.future, self.ttl)
            await run.checkpoint()
            return approved
        except TimeoutError:
            return False
        finally:
            async with self.lock:
                self.pending.pop(action.id, None)
            if not run.cancelled.is_set():
                run.status = "running" if run.resume_gate.is_set() else "paused"

    async def decide(self, session_id: str, action_id: str, digest: str, phrase: str, approve: bool):
        async with self.lock:
            action = self.pending.get(action_id)
            if (not action or action.session_id != session_id or action.future.done()
                    or action.expires <= time.monotonic() or action.digest != digest):
                raise ValueError("Freigabe unbekannt, abgelaufen oder bereits entschieden.")
            expected = "Kritische Aktion bestätigen" if action.risk == Risk.CRITICAL else "Aktion freigeben"
            # No substring, punctuation stripping, NLP, or negation heuristics.
            if approve and phrase.strip().casefold() != expected.casefold():
                raise ValueError("Bestätigungsphrase stimmt nicht exakt überein.")
            action.future.set_result(approve)
            self.audit.append({"action": action.id, "run": action.run_id, "tool": action.tool,
                               "risk": action.risk.value, "approved": approve})
            self.audit[:] = self.audit[-500:]

    async def cancel(self, run_id: str):
        async with self.lock:
            for a in list(self.pending.values()):
                if a.run_id == run_id:
                    if not a.future.done():
                        a.future.cancel()
                    self.pending.pop(a.id, None)

    def list_for(self, session_id):
        return [a.public() for a in self.pending.values()
                if a.session_id == session_id and not a.future.done()]
