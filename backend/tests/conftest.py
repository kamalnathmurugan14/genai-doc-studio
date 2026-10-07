import asyncio
import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.config import Settings
from app.deps import Container
from app.errors import AppError
from app.llm.client import Token, Usage
from app.llm.token_utils import estimate_tokens
from app.main import create_app


def make_pdf(path: Path, pages: list[str]) -> None:
    c = canvas.Canvas(str(path))
    for text in pages:
        y = 800
        for line in text.split("\n"):
            c.drawString(50, y, line)
            y -= 16
        c.showPage()
    c.save()


def make_docx(path: Path, paragraphs: list[str]) -> None:
    d = Document()
    for p in paragraphs:
        d.add_paragraph(p)
    d.save(str(path))


INVOICE = (
    "INVOICE\nInvoice number: INV-1042\nBill to: Acme Corp\nSubtotal: $900.00\nGST: $100.00\n"
    "Total due: $1000.00\nDue date: 2026-01-31"
)
CONTRACT = (
    "SERVICE AGREEMENT\nThis agreement is made between the parties. The renewal of this contract happens "
    "yearly. Governing law applies. The party agrees to keep all terms confidential."
)


@pytest.fixture
def docs(tmp_path: Path) -> Path:
    root = tmp_path / "docs"
    (root / "sub").mkdir(parents=True)
    make_pdf(root / "invoice.pdf", [INVOICE])
    make_docx(root / "contract.docx", CONTRACT.split(". "))
    (root / "garage.txt").write_text("The automobile was repaired at the garage last week.", encoding="utf-8")
    (root / "notes.md").write_text(
        "# Notes\n\nQuarterly report: executive summary, findings, conclusion and recommendations.", encoding="utf-8"
    )
    (root / "sub" / "recipe.txt").write_text("Mix flour and eggs. Bake for thirty minutes.", encoding="utf-8")
    return root


class FakeLLM:
    """Scripted stand-in for Ollama: never touches the network. `responder(messages, params) -> str` or a list of replies."""

    default_model = "fake-model"

    def __init__(self, responder: Callable | list[str] | None = None) -> None:
        self.responder = responder
        self.calls: list[dict] = []
        self.closed = 0
        self.available = True
        self.installed = ["fake-model", "other-model"]

    def _reply(self, messages, params) -> str:
        r = self.responder
        if callable(r):
            return r(messages, params)
        if isinstance(r, list):
            return r.pop(0) if len(r) > 1 else r[0]
        return "OK summary of the document."

    async def stream(self, messages, params):
        if not self.available:
            raise AppError("LLM_UNAVAILABLE", "Cannot reach Ollama. Run `ollama pull fake-model`", 503)
        prompt_tokens = sum(estimate_tokens(m["content"]) for m in messages)
        self.calls.append(
            {"messages": messages, "params": params, "prompt_tokens": prompt_tokens, "user": messages[-1]["content"]}
        )
        text = self._reply(messages, params)
        try:
            for w in text.split(" "):
                yield Token(w + " ")
                await asyncio.sleep(0)
            yield Usage(prompt_tokens, estimate_tokens(text))
        finally:
            self.closed += 1

    async def models(self):
        if not self.available:
            raise AppError("LLM_UNAVAILABLE", "down", 503)
        return self.installed

    async def ping(self):
        return self.available


def parse_sse(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        ev, data = None, None
        for line in block.split("\n"):
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                data = line[5:].strip()
        if ev and data:
            out.append((ev, json.loads(data)))
    return out


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def settings(tmp_path: Path, docs: Path) -> Settings:
    prompts = tmp_path / "prompts"
    shutil.copytree(
        Path(__file__).resolve().parent.parent / "app" / "prompts", prompts
    )  # edits never touch the repo files
    return Settings(docs_root=docs, data_dir=tmp_path / "data", prompts_dir=prompts, max_upload_mb=1, _env_file=None)


@pytest.fixture
def container(settings: Settings, llm: FakeLLM) -> Container:
    return Container(settings, llm=llm)


@pytest.fixture
def client(container: Container, settings: Settings):
    with TestClient(create_app(settings, container)) as c:
        yield c


def sse_post(client, path: str, body: dict) -> list[tuple[str, dict]]:
    r = client.post(path, json=body)
    assert r.status_code == 200, r.text
    return parse_sse(r.text)
