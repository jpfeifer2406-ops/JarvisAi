"""Append-only drafts. UUID paths, exclusive staging, integrity-checked canonical text.

Only COMPUTER-generated documents are revised; arbitrary PDF/DOCX import is not
silently converted or truncated. A PDF revision is explicitly a text re-render.
"""

from __future__ import annotations
import hashlib
import io
import json
import os
import re
import shutil
import uuid
import asyncio
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape


class Documents:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def path(self, doc_id: str):
        if not re.fullmatch(r"[a-f0-9]{32}", doc_id):
            raise ValueError("Ungültige Dokument-ID.")
        path = self.root / doc_id
        if path.is_symlink() or path.resolve().parent != self.root:
            raise ValueError("Unsicherer Dokumentpfad.")
        return path

    @staticmethod
    def render(text: str, kind: str) -> bytes:
        output = io.BytesIO()
        if kind == "txt":
            return text.encode("utf-8")
        if kind == "docx":
            from docx import Document

            doc = Document()
            for line in text.split("\n"):
                doc.add_paragraph(line)
            doc.save(output)
        elif kind == "pdf":
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            import reportlab

            styles = getSampleStyleSheet()
            font = TTFont("ComputerVera", str(Path(reportlab.__file__).parent / "fonts/Vera.ttf"))
            if any(ord(c) not in font.face.charToGlyph for c in text if c not in "\n\r\t"):
                raise ValueError("Zeichen im PDF-Font nicht verfügbar; TXT oder DOCX verwenden.")
            pdfmetrics.registerFont(font)
            styles["Normal"].fontName = "ComputerVera"
            # Full source is also retained; no character-count truncation.
            flow = [Paragraph(escape(line) or "&#160;", styles["Normal"]) for line in text.split("\n")]
            SimpleDocTemplate(output).build([x for p in flow for x in (p, Spacer(1, 4))])
        else:
            raise ValueError("Format muss txt, docx oder pdf sein.")
        return output.getvalue()

    def create(self, title: str, text: str, kind: str, parent: str | None = None):
        if len(text) > 200_000 or not text or len(title) > 120:
            raise ValueError("Dokumentgröße ungültig.")
        blob = self.render(text, kind)
        return self.commit(title, text, kind, blob, parent)

    async def create_async(self, title, text, kind, parent=None):
        if not text or len(text) > 200_000 or len(title) > 120:
            raise ValueError("Dokumentgröße ungültig.")
        # Rendering is killable and cannot block the API stop channel.
        with tempfile.TemporaryDirectory(prefix="computer-render-") as folder:
            output = Path(folder) / "rendered"
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "computer.adapters.document_worker",
                str(output),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                async with asyncio.timeout(25):
                    await process.communicate(json.dumps({"text": text, "format": kind}).encode())
                if process.returncode:
                    raise ValueError("Dokument konnte nicht verlustfrei gerendert werden.")
                blob = output.read_bytes()
            finally:
                if process.returncode is None:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), 3)
                    except TimeoutError:
                        process.kill()
                        await process.wait()
        return self.commit(title, text, kind, blob, parent)

    def commit(self, title, text, kind, blob, parent=None):
        if len(blob) > 10_000_000 or len(self.list()) >= 200:
            raise ValueError("Dokumentlimit erreicht.")
        doc_id = uuid.uuid4().hex
        stage = self.root / (".draft-" + doc_id)
        stage.mkdir(mode=0o700)
        meta = {
            "id": doc_id,
            "title": title,
            "format": kind,
            "parent": parent,
            "sha256": hashlib.sha256(blob).hexdigest(),
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "characters": len(text),
        }
        try:
            for name, data in (
                ("document." + kind, blob),
                ("source.txt", text.encode()),
                ("meta.json", json.dumps(meta, ensure_ascii=False).encode()),
            ):
                with (stage / name).open("xb") as file:
                    file.write(data)
                    file.flush()
                    os.fsync(file.fileno())
            stage.rename(self.path(doc_id))
        finally:
            if stage.exists():
                shutil.rmtree(stage)
        return meta

    def read(self, doc_id: str):
        folder = self.path(doc_id)
        for p in folder.iterdir():
            if p.is_symlink() or not p.is_file():
                raise ValueError("Unsicheres Dokumentobjekt.")
        meta = json.loads((folder / "meta.json").read_text("utf-8"))
        if meta["format"] not in ("txt", "docx", "pdf"):
            raise ValueError("Format ungültig.")
        blob = (folder / ("document." + meta["format"])).read_bytes()
        text = (folder / "source.txt").read_text("utf-8")
        if (
            hashlib.sha256(blob).hexdigest() != meta["sha256"]
            or hashlib.sha256(text.encode()).hexdigest() != meta["text_sha256"]
        ):
            raise ValueError("Integritätsprüfung fehlgeschlagen.")
        return meta, text, blob

    def revise(self, doc_id, old, new):
        if not old:
            raise ValueError("Suchtext darf nicht leer sein.")
        meta, text, _ = self.read(doc_id)
        if old not in text:
            raise ValueError("Suchtext nicht gefunden.")
        return self.create(meta["title"], text.replace(old, new), meta["format"], parent=doc_id)

    def list(self):
        return [self.read(p.name)[0] for p in self.root.iterdir() if re.fullmatch(r"[a-f0-9]{32}", p.name)][
            :200
        ]

    async def revise_async(self, doc_id, old, new):
        meta, text, _ = self.read(doc_id)
        if not old or old not in text:
            raise ValueError("Suchtext nicht gefunden.")
        return await self.create_async(meta["title"], text.replace(old, new), meta["format"], doc_id)
