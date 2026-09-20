from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Risk(StrEnum):
    READ = "READ"
    PREPARE = "PREPARE"
    EXECUTE = "EXECUTE"
    CRITICAL = "CRITICAL"


class ToolResult(StrictModel):
    status: Literal["ok", "error", "denied", "cancelled", "simulated", "unavailable"]
    message: str = Field(max_length=2000)
    data: dict[str, Any] = Field(default_factory=dict)
    validated: bool = False


class Provider(StrictModel):
    kind: Literal["demo", "openai", "local"] = "demo"
    model: str = Field(default="", max_length=120, pattern=r"^[\w.:/\-]*$")
    temperature: float | None = Field(default=None, ge=0, le=2)
    # URLs and credentials are operator-owned, never supplied by tools/themes.


@dataclass
class Run:
    id: str
    session_id: str
    provider: Provider
    api_key: str = field(default="", repr=False)
    status: str = "running"
    output: str = ""
    error: str | None = None
    cancelled: asyncio.Event = field(default_factory=asyncio.Event)
    resume_gate: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task | None = None
    results: list[dict] = field(default_factory=list)

    def __post_init__(self):
        self.resume_gate.set()

    async def checkpoint(self):
        if self.cancelled.is_set():
            raise asyncio.CancelledError
        await self.resume_gate.wait()
        if self.cancelled.is_set():
            raise asyncio.CancelledError


class AgentPort(Protocol):
    async def respond(self, text: str, history: list[dict], run: Run, dispatch) -> str: ...
