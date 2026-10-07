def test_list_and_get(client):
    names = {p["name"] for p in client.get("/prompts").json()["prompts"]}
    assert {
        "summarize_short",
        "summarize_detailed",
        "summarize_bullets",
        "map_chunk",
        "reduce",
        "extract_entities",
        "rewrite_tone",
        "translate_en_ta",
        "translate_ta_en",
        "email_from_doc",
        "report_from_doc",
    } <= names
    g = client.get("/prompts/summarize_short").json()
    assert g["version"] == 1 and "text" in g["variables"] and "{{ text }}" in g["body"]
    assert client.get("/prompts/nope").status_code == 404
    assert client.get("/prompts/Bad-Name").status_code == 422
    assert client.get("/prompts/..%2Fetc").status_code in (404, 422)


def test_save_creates_version_and_file(client, settings):
    r = client.put("/prompts/summarize_short", json={"body": "Summarize in French: {{ text }}", "note": "french"})
    assert r.status_code == 200 and r.json()["version"] == 2
    assert (settings.prompts_dir / "summarize_short.md").read_text() == "Summarize in French: {{ text }}"
    vs = client.get("/prompts/summarize_short/versions").json()["versions"]
    assert [v["version"] for v in vs] == [2, 1] and vs[0]["note"] == "french"


def test_invalid_template_rejected_and_file_untouched(client, settings):
    before = (settings.prompts_dir / "reduce.md").read_text()
    r = client.put("/prompts/reduce", json={"body": "Hello {{ text "})
    assert r.status_code == 422 and r.json()["error"]["code"] == "TEMPLATE_SYNTAX"
    assert (settings.prompts_dir / "reduce.md").read_text() == before
    assert client.put("/prompts/reduce", json={"body": "   "}).json()["error"]["code"] == "EMPTY_PROMPT"
    assert len(client.get("/prompts/reduce/versions").json()["versions"]) == 1


def test_restore_makes_new_version_with_old_body(client):
    original = client.get("/prompts/summarize_bullets").json()["body"]
    client.put("/prompts/summarize_bullets", json={"body": "changed {{ text }}"})
    r = client.post("/prompts/summarize_bullets/restore/1").json()
    assert r["version"] == 3 and r["body"] == original
    assert client.post("/prompts/summarize_bullets/restore/99").status_code == 404


def test_preview_renders_sample_and_catches_errors(client):
    p = client.post("/prompts/rewrite_tone/preview").json()
    assert "friendly" in p["rendered"] and "Acme Corp" in p["rendered"]
    p = client.post("/prompts/rewrite_tone/preview", json={"body": "X {{ text }} {{ tone }}"}).json()
    assert p["variables"] == ["text", "tone"] and p["rendered"].startswith("X Acme")
    assert client.post("/prompts/rewrite_tone/preview", json={"body": "{% if %}"}).status_code == 422


def test_sandbox_blocks_dangerous_templates(client):
    r = client.post("/prompts/rewrite_tone/preview", json={"body": "{{ ''.__class__.__mro__[1].__subclasses__() }}"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "TEMPLATE_RENDER"
