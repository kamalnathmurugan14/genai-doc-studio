import json

import pytest

from app.services.engine import Engine

DOC = "Invoice INV-1042 from Acme Corp. Total due: $1,000.00 by 2026-01-31. Priya will confirm payment."


@pytest.fixture
def doc(docs):
    (docs / "inv.txt").write_text(DOC, encoding="utf-8")
    return "inv.txt"


def good(**over):
    base = {
        "dates": [{"value": "2026-01-31", "evidence": "by 2026-01-31"}],
        "people": [{"value": "Priya", "evidence": "Priya will confirm"}],
        "amounts": [{"value": "$1,000.00", "evidence": "Total due: $1,000.00"}],
        "action_items": [],
    }
    return json.dumps({**base, **over})


def test_valid_json_with_verified_evidence(client, llm, doc):
    llm.responder = lambda m, p: good()
    r = client.post("/extract", json={"rel_path": doc, "schema_name": "entities"}).json()
    assert r["valid"] is True and r["attempts"] == 1 and r["unverified"] == []
    assert r["data"]["people"][0] == {"value": "Priya", "evidence": "Priya will confirm", "verified": True}
    assert llm.calls[0]["params"].temperature == 0.0  # extraction defaults to deterministic sampling
    assert '"evidence"' in llm.calls[0]["user"] and DOC in llm.calls[0]["user"]
    run = client.get(f"/runs/{r['run_id']}").json()
    assert run["task"] == "extract" and run["output_json"]["valid"] is True


def test_hallucinated_evidence_is_flagged(client, llm, doc):
    llm.responder = lambda m, p: good(
        people=[
            {"value": "Bob", "evidence": "Bob approved the budget"},
            {"value": "Priya", "evidence": "PRIYA   will   confirm"},
        ]
    )
    r = client.post("/extract", json={"rel_path": doc}).json()
    assert r["valid"] is True
    assert r["unverified"] == [{"path": "people[0]", "value": "Bob"}]
    assert (
        r["data"]["people"][0]["verified"] is False and r["data"]["people"][1]["verified"] is True
    )  # case/whitespace-insensitive match


def test_broken_json_triggers_retry_with_error_feedback(client, llm, doc):
    llm.responder = ["Sure! here you go: {dates: [oops", good()]
    r = client.post("/extract", json={"rel_path": doc}).json()
    assert r["valid"] is True and r["attempts"] == 2
    retry = llm.calls[1]["messages"]
    assert retry[-2]["role"] == "assistant" and "oops" in retry[-2]["content"]
    assert "Fix these errors" in retry[-1]["content"] and "invalid" in retry[-1]["content"]


def test_schema_violation_retries_then_succeeds(client, llm, doc):
    llm.responder = [json.dumps({"dates": "2026-01-31"}), good()]
    r = client.post("/extract", json={"rel_path": doc}).json()
    assert r["attempts"] == 2 and "dates" in llm.calls[1]["user"] or "dates" in llm.calls[1]["messages"][-1]["content"]


def test_gives_up_after_max_retries(client, llm, doc, settings):
    llm.responder = ["this is not json at all"]
    r = client.post("/extract", json={"rel_path": doc}).json()
    assert r["valid"] is False and r["data"] is None and r["attempts"] == settings.json_max_retries + 1
    assert r["raw"].strip() == "this is not json at all" and r["errors"]
    assert len(llm.calls) == settings.json_max_retries + 1


def test_tolerant_parsing():
    assert Engine.parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert Engine.parse_json('Here: {"a": {"b": 2}} Hope it helps') == {"a": {"b": 2}}
    for bad in ("", "[1,2]", "{oops}", "no braces"):
        with pytest.raises(ValueError):
            Engine.parse_json(bad)


def test_other_schemas_and_nulls(client, llm, doc):
    llm.responder = lambda m, p: json.dumps(
        {"invoice_number": {"value": "INV-1042", "evidence": "Invoice INV-1042"}, "vendor": None, "line_items": []}
    )
    r = client.post("/extract", json={"rel_path": doc, "schema_name": "invoice"}).json()
    assert r["valid"] and r["data"]["invoice_number"]["verified"] is True and r["data"]["vendor"] is None
    assert "invoice_number" in llm.calls[0]["user"]
    assert (
        client.post("/extract", json={"rel_path": doc, "schema_name": "nope"}).json()["error"]["code"] == "BAD_SCHEMA"
    )
    assert client.post("/extract", json={"rel_path": "nope.txt"}).status_code == 404


def test_long_document_is_truncated_with_flag(client, llm, docs):
    (docs / "long.txt").write_text("filler words here. " * 6000, encoding="utf-8")
    llm.responder = lambda m, p: good()
    r = client.post("/extract", json={"rel_path": "long.txt"}).json()
    assert r["truncated"] is True and llm.calls[0]["prompt_tokens"] < 4096


def test_llm_down_is_http_503(client, llm, doc):
    llm.available = False
    r = client.post("/extract", json={"rel_path": doc})
    assert r.status_code == 503 and r.json()["error"]["code"] == "LLM_UNAVAILABLE"
