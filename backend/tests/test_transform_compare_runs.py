from tests.conftest import sse_post


def test_rewrite_uses_tone(client, llm):
    ev = sse_post(client, "/transform", {"rel_path": "garage.txt", "action": "rewrite", "tone": "casual"})
    assert ev[-1][0] == "done" and "casual tone" in llm.calls[-1]["user"] and "automobile" in llm.calls[-1]["user"]


def test_translate_directions_and_validation(client, llm):
    sse_post(client, "/transform", {"text": "Hello world", "action": "translate", "target_language": "Tamil"})
    assert "English-to-Tamil" in llm.calls[-1]["user"] and "Hello world" in llm.calls[-1]["user"]
    ev = sse_post(client, "/transform", {"text": "வணக்கம்", "action": "translate", "target_language": "en"})
    assert "Tamil-to-English" in llm.calls[-1]["user"]
    assert "Tamil quality varies" in (ev[0][1]["note"] or "")
    assert (
        client.post("/transform", json={"text": "x", "action": "translate", "target_language": "fr"}).json()["error"][
            "code"
        ]
        == "BAD_LANGUAGE"
    )
    assert client.post("/transform", json={"text": "x", "action": "dance"}).json()["error"]["code"] == "BAD_ACTION"
    assert client.post("/transform", json={"action": "rewrite"}).json()["error"]["code"] == "MISSING_INPUT"


def test_email_and_report(client, llm):
    sse_post(client, "/transform", {"rel_path": "notes.md", "action": "email", "tone": "friendly"})
    assert "subject line" in llm.calls[-1]["user"] and "friendly" in llm.calls[-1]["user"]
    sse_post(client, "/transform", {"rel_path": "notes.md", "action": "report"})
    assert "Key Points" in llm.calls[-1]["user"]


def test_long_rewrite_is_chunked_in_order(client, llm, docs, settings):
    settings.context_tokens, settings.chunk_tokens = 1000, 300
    (docs / "long.txt").write_text("\n\n".join(f"Paragraph {i} " + "text " * 150 for i in range(12)), encoding="utf-8")
    llm.responder = lambda m, p: "REWRITTEN"
    ev = sse_post(client, "/transform", {"rel_path": "long.txt", "action": "rewrite", "params": {"max_tokens": 200}})
    assert len(llm.calls) > 3 and ev[-1][0] == "done"
    assert "Paragraph 0" in llm.calls[0]["user"] and "Paragraph 11" in llm.calls[-1]["user"]
    assert max(c["prompt_tokens"] for c in llm.calls) <= settings.context_tokens


def test_long_report_is_condensed_first(client, llm, docs, settings):
    settings.context_tokens, settings.chunk_tokens = 1500, 400
    (docs / "long.txt").write_text("\n\n".join(f"Paragraph {i} " + "text " * 150 for i in range(20)), encoding="utf-8")
    llm.responder = lambda m, p: "short summary"
    ev = sse_post(client, "/transform", {"rel_path": "long.txt", "action": "report", "params": {"max_tokens": 200}})
    assert any(k == "chunk_summary" for k, _ in ev) and "Key Points" in llm.calls[-1]["user"] and ev[-1][0] == "done"


def test_compare_two_variants(client, llm):
    llm.responder = lambda m, p: f"temp={p.temperature}"
    r = client.post(
        "/compare",
        json={
            "run_a_inputs": {
                "task": "summarize",
                "rel_path": "garage.txt",
                "style": "short",
                "params": {"temperature": 0.0},
            },
            "run_b_inputs": {
                "task": "summarize",
                "rel_path": "garage.txt",
                "prompt_body": "Poem: {{ text }}",
                "params": {"temperature": 1.0},
            },
        },
    ).json()
    assert r["a"]["output"].strip() == "temp=0.0" and r["b"]["output"].strip() == "temp=1.0"
    assert r["a"]["run_id"] != r["b"]["run_id"] and r["a"]["tokens_out"] > 0
    assert "Poem:" in llm.calls[-1]["user"]
    bad = client.post(
        "/compare",
        json={
            "run_a_inputs": {"task": "x", "rel_path": "garage.txt"},
            "run_b_inputs": {"task": "summarize", "rel_path": "garage.txt"},
        },
    )
    assert bad.json()["error"]["code"] == "BAD_TASK"
    t = client.post(
        "/compare",
        json={
            "run_a_inputs": {"task": "transform", "action": "rewrite", "rel_path": "garage.txt"},
            "run_b_inputs": {"task": "transform", "rel_path": "garage.txt"},
        },
    )
    assert t.json()["error"]["code"] == "MISSING_INPUT"


def test_run_history_filters(client):
    sse_post(client, "/summarize", {"rel_path": "garage.txt"})
    sse_post(client, "/transform", {"rel_path": "notes.md", "action": "rewrite"})
    runs = client.get("/runs").json()["runs"]
    assert [r["task"] for r in runs] == ["transform:rewrite", "summarize"]
    assert len(client.get("/runs", params={"task": "summarize"}).json()["runs"]) == 1
    assert client.get("/runs", params={"file": "notes"}).json()["runs"][0]["file_rel_path"] == "notes.md"
    assert client.get("/runs/999").status_code == 404
    full = client.get(f"/runs/{runs[0]['id']}").json()
    assert full["params"] == {} and full["prompt_name"] == "rewrite_tone"
