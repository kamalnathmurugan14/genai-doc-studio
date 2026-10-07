import asyncio
import json

import httpx
import pytest

import app.llm.client as client_mod
from app.config import Settings
from app.errors import AppError
from app.llm.client import OllamaClient, Token, Usage, complete
from app.llm.options import GenParams
from app.llm.token_utils import estimate_tokens

REAL_CLIENT = httpx.AsyncClient  # captured once: patching twice must not wrap the patch


def patch_transport(monkeypatch, handler):
    monkeypatch.setattr(
        client_mod.httpx, "AsyncClient", lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw)
    )


def ndjson(*objs) -> bytes:
    return ("\n".join(json.dumps(o) for o in objs) + "\n").encode()


def test_streams_tokens_and_usage(monkeypatch):
    seen = {}

    def handler(req: httpx.Request):
        seen.update(json.loads(req.content))
        return httpx.Response(
            200,
            content=ndjson(
                {"message": {"content": "Hel"}, "done": False},
                {"message": {"content": "lo"}, "done": False},
                {"message": {"content": ""}, "done": True, "prompt_eval_count": 11, "eval_count": 2},
            ),
        )

    patch_transport(monkeypatch, handler)
    c = OllamaClient(Settings(_env_file=None))
    text, usage = asyncio.run(
        complete(c, [{"role": "user", "content": "hi"}], GenParams(temperature=0.7, max_tokens=50))
    )
    assert text == "Hello" and usage == Usage(11, 2)
    assert seen["options"]["temperature"] == 0.7 and seen["options"]["num_predict"] == 50 and seen["stream"] is True
    assert seen["model"] == "llama3.2:3b"


def test_missing_model_gives_pull_hint(monkeypatch):
    patch_transport(monkeypatch, lambda req: httpx.Response(404, json={"error": "model not found"}))
    c = OllamaClient(Settings(_env_file=None))
    with pytest.raises(AppError) as e:
        asyncio.run(complete(c, [{"role": "user", "content": "x"}], GenParams(model="nope")))
    assert e.value.code == "MODEL_MISSING" and "ollama pull nope" in e.value.message


def test_ollama_down(monkeypatch):
    def handler(req):
        raise httpx.ConnectError("refused")

    patch_transport(monkeypatch, handler)
    c = OllamaClient(Settings(_env_file=None))
    with pytest.raises(AppError) as e:
        asyncio.run(complete(c, [{"role": "user", "content": "x"}], GenParams()))
    assert e.value.code == "LLM_UNAVAILABLE" and "ollama serve" in e.value.message and e.value.status == 503
    assert asyncio.run(c.ping()) is False


def test_models_list_and_stream_error_line(monkeypatch):
    patch_transport(monkeypatch, lambda req: httpx.Response(200, json={"models": [{"name": "b"}, {"name": "a"}]}))
    c = OllamaClient(Settings(_env_file=None))
    assert asyncio.run(c.models()) == ["a", "b"] and asyncio.run(c.ping()) is True
    patch_transport(monkeypatch, lambda req: httpx.Response(200, content=ndjson({"error": "out of memory"})))
    with pytest.raises(AppError) as e:
        asyncio.run(complete(c, [{"role": "user", "content": "x"}], GenParams()))
    assert e.value.code == "LLM_ERROR"


def test_estimate_tokens():
    assert estimate_tokens("a" * 400) == 100
    assert estimate_tokens("வணக்கம்") > estimate_tokens("hello!!")  # non-Latin text costs more tokens per char
    assert estimate_tokens("") == 0
    assert isinstance(Token("x").text, str)
