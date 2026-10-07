import asyncio

import pytest

from app.llm.options import GenParams
from tests.conftest import FakeLLM, parse_sse, sse_post

BIG = "\n\n".join(
    f"Section {i}. " + ("The quarterly figures and the renewal terms were discussed in detail. " * 12)
    for i in range(120)
)


def test_one_shot_streams_tokens_and_records_run(client, llm):
    ev = sse_post(client, "/summarize", {"rel_path": "garage.txt", "style": "short"})
    kinds = [k for k, _ in ev]
    assert kinds[0] == "meta" and kinds[-1] == "done" and kinds.count("token") >= 4
    assert ev[0][1]["mode"] == "one_shot"
    assert "".join(d["text"] for k, d in ev if k == "token").startswith("OK summary")
    done = ev[-1][1]
    assert done["tokens_in"] > 0 and done["tokens_out"] > 0 and done["ms"] >= 0
    assert "automobile was repaired" in llm.calls[0]["user"]  # the document text was rendered into the prompt
    run = client.get(f"/runs/{done['run_id']}").json()
    assert (
        run["task"] == "summarize"
        and run["status"] == "done"
        and run["file_rel_path"] == "garage.txt"
        and run["prompt_version"] == 1
    )
    assert run["output_text"].startswith("OK summary") and run["model"] == "fake-model"


@pytest.mark.parametrize(
    "style,marker", [("short", "2-3 sentences"), ("detailed", "detailed summary"), ("bullets", "bullet points")]
)
def test_styles_use_their_templates(client, llm, style, marker):
    sse_post(client, "/summarize", {"rel_path": "garage.txt", "style": style})
    assert marker in llm.calls[-1]["user"]


def test_params_reach_the_model(client, llm):
    sse_post(
        client,
        "/summarize",
        {
            "rel_path": "garage.txt",
            "params": {"temperature": 0.9, "top_p": 0.5, "max_tokens": 123, "model": "other-model"},
        },
    )
    p = llm.calls[-1]["params"]
    assert (p.temperature, p.top_p, p.max_tokens, p.model) == (0.9, 0.5, 123, "other-model")


def test_custom_prompt_body_and_name(client, llm):
    sse_post(client, "/summarize", {"rel_path": "garage.txt", "prompt_body": "PIRATE MODE: {{ text }}"})
    assert llm.calls[-1]["user"].startswith("PIRATE MODE: The automobile")
    sse_post(client, "/summarize", {"rel_path": "garage.txt", "prompt_name": "summarize_bullets"})
    assert "bullet points" in llm.calls[-1]["user"]


def test_validation_errors_are_http_errors(client):
    assert (
        client.post("/summarize", json={"rel_path": "garage.txt", "style": "poem"}).json()["error"]["code"]
        == "BAD_STYLE"
    )
    assert client.post("/summarize", json={"rel_path": "nope.txt"}).status_code == 404
    assert client.post("/summarize", json={"rel_path": "../../etc/passwd"}).status_code == 400
    assert client.post("/summarize", json={"rel_path": "garage.txt", "params": {"temperature": 5}}).status_code == 422
    assert (
        client.post("/summarize", json={"rel_path": "garage.txt", "params": {"max_tokens": 4000}}).json()["error"][
            "code"
        ]
        == "CONTEXT_TOO_SMALL"
    )
    assert (
        client.post("/summarize", json={"rel_path": "garage.txt", "prompt_body": "{{ text "}).json()["error"]["code"]
        == "TEMPLATE_SYNTAX"
    )


def test_empty_file_and_llm_down(client, llm, docs):
    (docs / "empty.txt").write_text("   ")
    assert client.post("/summarize", json={"rel_path": "empty.txt"}).json()["error"]["code"] == "NO_TEXT"
    llm.available = False
    ev = sse_post(client, "/summarize", {"rel_path": "garage.txt"})
    assert ev[-1][0] == "error" and ev[-1][1]["code"] == "LLM_UNAVAILABLE" and "ollama pull" in ev[-1][1]["message"]
    assert client.get("/runs", params={"task": "summarize"}).json()["runs"][0]["status"] == "error"


def test_map_reduce_30_page_doc_stays_within_context(client, llm, docs, settings):
    (docs / "big.txt").write_text(BIG, encoding="utf-8")  # ~ 110k chars ~ 28k tokens, far beyond a 4096 window
    llm.responder = lambda m, p: "Short part summary." if "ONE PART" in m[-1]["content"] else "FINAL SUMMARY TEXT"
    ev = sse_post(client, "/summarize", {"rel_path": "big.txt", "style": "bullets"})
    kinds = [k for k, _ in ev]
    meta = [d for k, d in ev if k == "meta"][0]
    assert meta["mode"] == "map_reduce" and meta["chunks"] >= 15
    summaries = [d for k, d in ev if k == "chunk_summary"]
    assert (
        len(summaries) >= meta["chunks"]
        and summaries[0]["index"] == 1
        and summaries[0]["text"] == "Short part summary."
    )
    assert kinds[-1] == "done" and "FINAL SUMMARY TEXT" in "".join(d["text"] for k, d in ev if k == "token")
    assert (
        max(c["prompt_tokens"] + 800 for c in llm.calls) <= settings.context_tokens + 64
    )  # every request fits the window (incl. answer)
    assert "bullets" in llm.calls[-1]["user"]  # final call is the reduce template with the chosen style
    run = client.get("/runs?task=summarize").json()["runs"][0]
    assert run["tokens_in"] > 0


def test_hierarchical_reduce_when_summaries_do_not_fit(client, llm, docs, settings):
    settings.context_tokens, settings.chunk_tokens = 1500, 300
    (docs / "big.txt").write_text(BIG[:40000], encoding="utf-8")
    llm.responder = lambda m, p: (
        ("word " * 250)
        if "PART" in m[-1]["content"].upper() and "partial summaries" not in m[-1]["content"]
        else "FINAL"
    )
    ev = sse_post(client, "/summarize", {"rel_path": "big.txt", "params": {"max_tokens": 200}})
    levels = {d["level"] for k, d in ev if k == "chunk_summary"}
    assert 2 in levels and ev[-1][0] == "done"
    assert max(c["prompt_tokens"] for c in llm.calls) <= settings.context_tokens


def test_client_disconnect_aborts_stream_and_records_cancelled(container, llm):
    llm.responder = lambda m, p: "one two three four five six seven eight nine ten"

    async def go():
        gen = await container.engine.summarize("garage.txt", None, "short", GenParams())
        seen = 0
        async for ev in gen:
            if ev["event"] == "token":
                seen += 1
                if seen == 3:
                    break
        await gen.aclose()  # what Starlette does on disconnect

    asyncio.run(go())
    assert llm.closed == 1  # upstream generator (the Ollama HTTP stream) was closed
    run = container.runs.list_all()[0]
    assert run["status"] == "cancelled" and run["output_text"].startswith("one two three")


def test_raw_stream_endpoint(client, llm):
    llm.responder = lambda m, p: "echo " + m[-1]["content"]
    ev = sse_post(client, "/stream", {"prompt": "ping pong"})
    assert "".join(d["text"] for k, d in ev if k == "token").strip() == "echo ping pong"
    assert client.post("/stream", json={"prompt": ""}).status_code == 422


def test_models_endpoint(client, llm):
    assert client.get("/models").json() == {"models": ["fake-model", "other-model"], "default": "fake-model"}
    llm.available = False
    assert client.get("/models").status_code == 503
    assert parse_sse('event: x\r\ndata: {"a": 1}\r\n\r\n') == [("x", {"a": 1})]
    assert isinstance(FakeLLM(), FakeLLM)
