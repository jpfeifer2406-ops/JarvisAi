from __future__ import annotations
import asyncio
import hmac
import os
from urllib.parse import urlsplit
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.exceptions import RequestValidationError
from .diagnostics import failure
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from .contracts import StrictModel, Provider
from .memory import Preferences
from .runtime import Runtime

ORIGIN = "http://127.0.0.1:7861"


class Login(StrictModel):
    token: str = Field(max_length=128)


class Credential(StrictModel):
    key: str = Field(default="", max_length=512, repr=False)


class Message(StrictModel):
    text: str = Field(min_length=1, max_length=8000)


class Invocation(StrictModel):
    tool: str = Field(max_length=80)
    arguments: dict


class Decision(StrictModel):
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    phrase: str = Field(max_length=100)
    approve: bool


class Tab(StrictModel):
    title: str = Field(max_length=300)
    url: str = Field(max_length=2048)


def create_app(root: Path, pairing_token: str, runtime: Runtime | None = None):
    rt = runtime or Runtime(root)
    bridges = {}
    attempts = []
    livekit = os.environ.get("LIVEKIT_URL", "")
    parsed = urlsplit(livekit)
    livekit_csp = ""
    if parsed.scheme in ("ws", "wss") and parsed.hostname and not parsed.username:
        livekit_csp = " " + parsed.scheme + "://" + parsed.netloc
        livekit_csp += " " + ("https" if parsed.scheme == "wss" else "http") + "://" + parsed.netloc

    @asynccontextmanager
    async def lifespan(app):
        async def reap():
            while True:
                await asyncio.sleep(30)
                for sid, session in list(rt.sessions.items()):
                    if session.expires <= time.monotonic():
                        await rt.close_session(sid)

        reaper = asyncio.create_task(reap())
        rt.check_task = asyncio.create_task(rt.selfcheck())
        yield
        reaper.cancel()
        await asyncio.gather(reaper, return_exceptions=True)
        await rt.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.runtime = rt

    @app.middleware("http")
    async def boundary(req, next_handler):
        if req.headers.get("host") != "127.0.0.1:7861":
            return JSONResponse({"detail": "Host gesperrt"}, 403)
        origin = req.headers.get("origin")
        bridge = req.url.path == "/api/bridge/tab"
        if origin and origin != ORIGIN and not (bridge and origin.startswith("chrome-extension://")):
            return JSONResponse({"detail": "Origin gesperrt"}, 403)
        if req.method not in ("GET", "HEAD") and not bridge and origin != ORIGIN:
            return JSONResponse({"detail": "Origin erforderlich"}, 403)
        # Bound body even without Content-Length; endpoints accept JSON only.
        if req.method not in ("GET", "HEAD"):
            if req.headers.get("content-type", "").split(";")[0] != "application/json":
                return JSONResponse({"detail": "JSON erforderlich"}, 415)
            body = bytearray()
            async for part in req.stream():
                body.extend(part)
                if len(body) > 300_000:
                    return JSONResponse({"detail": "Anfrage zu groß"}, 413)
            req._body = bytes(body)
        try:
            response = await next_handler(req)
        except Exception as exc:
            found = rt.sessions.get(req.cookies.get("computer_session", ""))
            if found:
                found.diagnostics.emit("http", "request.failed", level="ERROR", provider=found.provider, error=exc)
            response = JSONResponse({"detail": failure(exc)["message"]}, 500)
        if response.status_code >= 400:
            found = rt.sessions.get(req.cookies.get("computer_session", ""))
            if found:
                found.diagnostics.emit("http", "status." + str(response.status_code), level="WARNING", provider=found.provider)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": f"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'{livekit_csp}; object-src 'none'; frame-ancestors 'none'; base-uri 'none'",
            }
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation(req, exc):
        # FastAPI's default response echoes invalid input, including credential fields.
        return JSONResponse({"detail": "Eingabeformat ungültig; Pflichtfelder und Werte prüfen."}, status_code=422)

    @app.exception_handler(ValueError)
    async def invalid(req, exc):
        found = rt.sessions.get(req.cookies.get("computer_session", ""))
        if found:
            found.diagnostics.emit("http", "invalid_state", level="WARNING", provider=found.provider, error=exc)
        return JSONResponse({"detail": "Eingabe oder aktueller Zustand ungültig."}, status_code=400)

    @app.exception_handler(PermissionError)
    async def unauthorized(req, exc):
        return JSONResponse({"detail": "Sitzung fehlt oder ist abgelaufen."}, status_code=401)

    def session(req: Request):
        return rt.session(req.cookies.get("computer_session", ""))

    @app.post("/api/login")
    async def login(body: Login):
        now = time.monotonic()
        attempts[:] = [t for t in attempts if t > now - 60]
        if len(attempts) >= 10:
            raise HTTPException(429, "Bitte eine Minute warten.")
        attempts.append(now)
        if not hmac.compare_digest(body.token, pairing_token):
            raise HTTPException(401, "Zugangscode ungültig.")
        s = rt.new_session()
        response = JSONResponse({"session": s.id})
        response.set_cookie("computer_session", s.id, httponly=True, samesite="strict", max_age=8 * 3600)
        return response

    @app.post("/api/logout")
    async def logout(s=Depends(session)):
        await rt.close_session(s.id)
        response = JSONResponse({"ok": True})
        response.delete_cookie("computer_session")
        return response

    @app.get("/api/state")
    async def state(s=Depends(session)):
        return rt.view(s.id)

    @app.post("/api/message")
    async def message(body: Message, s=Depends(session)):
        return {"run": (await rt.start(s.id, text=body.text)).id}

    @app.post("/api/tool")
    async def tool(body: Invocation, s=Depends(session)):
        return {"run": (await rt.start(s.id, tool=body.tool, arguments=body.arguments)).id}

    @app.post("/api/run/{rid}/{action}")
    async def control(rid: str, action: Literal["stop", "pause", "resume"], s=Depends(session)):
        await getattr(rt, action)(s.id, rid)
        return {"ok": True}

    @app.post("/api/approval/{aid}")
    async def approval(aid: str, body: Decision, s=Depends(session)):
        await rt.broker.decide(s.id, aid, body.digest, body.phrase, body.approve)
        return {"ok": True}

    @app.post("/api/provider")
    async def provider(body: Provider, s=Depends(session)):
        if rt.active(s):
            raise ValueError("Zuerst laufenden Auftrag beenden.")
        s.provider = body
        s.checked_at = 0
        s.provider_check = {"status": "DEGRADED", "message": "Konfiguration geändert; Verbindung prüfen."}
        s.diagnostics.emit("provider", "configured", provider=body)
        s.history.clear()  # No automatic transfer of an old conversation to a new provider.
        return body

    @app.post("/api/provider/key")
    async def credential(body: Credential, s=Depends(session)):
        if rt.active(s):
            raise ValueError("Zuerst Auftrag beenden.")
        s.api_key = body.key.strip()
        s.checked_at = 0
        s.provider_check = {"status": "DEGRADED", "message": "Key geändert; Verbindung prüfen."}
        s.diagnostics.emit("provider", "credential.updated", provider=s.provider)
        return {"configured": bool(s.api_key)}

    @app.post("/api/provider/check")
    async def provider_check(s=Depends(session)):
        async with s.lock:
            if rt.active(s):
                raise ValueError("Zuerst Auftrag beenden.")
            return await rt.check_provider(s)

    @app.get("/api/diagnostics")
    async def diagnostics(s=Depends(session)):
        return {**s.diagnostics.export(), "checks": rt.checks, "provider_check": s.provider_check}

    @app.post("/api/diagnostics/clear")
    async def clear_diagnostics(s=Depends(session)):
        s.diagnostics.events.clear()
        return {"ok": True}

    @app.post("/api/selfcheck")
    async def selfcheck(s=Depends(session)):
        if not rt.check_task or rt.check_task.done():
            rt.check_task = asyncio.create_task(rt.selfcheck())
        return {"status": "running"}

    @app.post("/api/memory")
    async def memory(body: Preferences, s=Depends(session)):
        s.memory.set(body.model_dump())
        return s.memory.preferences

    @app.post("/api/voice/connect")
    async def voice_connect(s=Depends(session)):
        try:
            s.diagnostics.emit("voice", "initializing", provider=s.provider)
            if rt.voice is None:
                from .adapters.livekit_voice import LiveKitVoice
                rt.voice = LiveKitVoice(rt)
            result = await rt.voice.connect(s.id)
            s.voice_error = None
            return result
        except Exception as exc:
            s.voice_error = failure(exc)["message"]
            s.diagnostics.emit("voice", "initialization.failed", level="ERROR", provider=s.provider, error=exc)
            return JSONResponse({"detail": s.voice_error, "diagnosis_id": s.diagnostics.id}, 503)

    @app.post("/api/voice/{action}")
    async def voice_control(action: Literal["stop", "disconnect", "wake"], s=Depends(session)):
        if not rt.voice:
            return {"status": "not_connected"}
        if action == "wake":
            if rt.voice.owner.session_id != s.id:
                raise ValueError("Audio nicht verbunden.")
            rt.voice.processor.voice.wake()
        else:
            await getattr(rt.voice, action)(s.id)
        return {"ok": True}

    @app.get("/api/documents")
    async def documents(s=Depends(session)):
        return rt.documents_for(s.id).list()

    @app.get("/api/documents/{did}")
    async def document(did: str, s=Depends(session)):
        meta, _, content = rt.documents_for(s.id).read(did)
        types = {
            "txt": "text/plain; charset=utf-8",
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        return Response(
            content,
            media_type=types[meta["format"]],
            headers={"Content-Disposition": f'attachment; filename="computer-{did}.{meta["format"]}"'},
        )

    @app.post("/api/bridge/pair")
    async def bridge_pair(s=Depends(session)):
        token = secrets.token_urlsafe(32)
        # One scoped token per session; only active-tab ingestion, no tools or approvals.
        bridges[s.id] = (token, time.monotonic() + 600)
        return {"token": token, "expires_seconds": 600}

    @app.post("/api/bridge/tab")
    async def bridge_tab(body: Tab, req: Request):
        token = req.headers.get("authorization", "").removeprefix("Bearer ")
        match = next(
            (
                sid
                for sid, (key, exp) in bridges.items()
                if exp > time.monotonic() and hmac.compare_digest(key, token)
            ),
            None,
        )
        if not match:
            raise HTTPException(401, "Bridge nicht gekoppelt.")
        rt.session(match)
        rt.integrations.share_tab(match, body.title, body.url)
        return {"ok": True}

    static = Path(__file__).parent / "static"
    app.mount("/assets", StaticFiles(directory=static), name="assets")

    @app.get("/")
    async def index():
        return FileResponse(static / "index.html")

    return app
