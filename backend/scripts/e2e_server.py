"""Throw-away backend for Playwright with a scripted fake LLM (no Ollama needed). Served on :8000."""

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import uvicorn  # noqa: E402

from app.config import DEFAULT_PROMPTS, Settings  # noqa: E402
from app.deps import Container  # noqa: E402
from app.llm.client import Token, Usage  # noqa: E402
from app.main import create_app  # noqa: E402


class DemoLLM:
    default_model = "demo-model"

    async def stream(self, messages, params):
        prompt = messages[-1]["content"]
        reply = (
            '{"dates": [{"value": "2026-01-31", "evidence": "due 2026-01-31"}], "people": [], "amounts": [], "action_items": []}'
            if '"evidence"' in prompt
            else "This is a streamed demo summary of the document. " * 6
        )
        for w in reply.split(" "):
            yield Token(w + " ")
            await asyncio.sleep(0.15 if '"evidence"' not in prompt else 0)
        yield Usage(50, len(reply.split()))

    async def models(self):
        return ["demo-model"]

    async def ping(self):
        return True


tmp = Path(tempfile.mkdtemp())
(tmp / "docs").mkdir()
(tmp / "docs" / "invoice.txt").write_text("Invoice INV-1042. Payment due 2026-01-31. Total $1,000.", encoding="utf-8")
prompts = tmp / "prompts"
shutil.copytree(DEFAULT_PROMPTS, prompts)
s = Settings(docs_root=tmp / "docs", data_dir=tmp / "data", prompts_dir=prompts, _env_file=None)
uvicorn.run(create_app(s, Container(s, llm=DemoLLM())), host="127.0.0.1", port=8000, log_level="warning")
