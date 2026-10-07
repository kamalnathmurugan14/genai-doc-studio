# Architecture

| Module | Responsibility |
|---|---|
| `llm/client.py` | `OllamaClient`: async generator over `/api/chat` NDJSON → `Token` / `Usage`. Friendly errors (`LLM_UNAVAILABLE`, `MODEL_MISSING` with `ollama pull` hint, timeouts). Tests inject a fake with the same protocol. |
| `llm/options.py`, `llm/token_utils.py` | sampling params → Ollama options; ~4 chars/token estimate (non-Latin text counted heavier) |
| `services/prompt_store.py` | `.md` files = source of truth; every save → new `prompt_versions` row; Jinja2 **sandboxed** + syntax validation before saving |
| `services/engine.py` | `summarize` (one-shot / map-reduce / hierarchical reduce), `extract` (JSON + retry + evidence), `transform`; all produce `{event,data}` dicts |
| `services/run_store.py` | run history (tokens, ms, params, prompt version, output) |
| `api/sse.py` | dict stream → SSE; closes the upstream generator on disconnect |

## Data flow (summarize)
1. Endpoint validates input *before* streaming (bad style, missing file, template error, context too small → proper HTTP 4xx).
2. Budget = `CONTEXT_TOKENS − prompt overhead − max_tokens`. Fits → render template → stream tokens.
3. Doesn't fit → chunk (paragraph-aware, overlap) → each chunk summarised sequentially (`chunk_summary` events) → if the partial summaries still exceed the budget, reduce hierarchically → stream the final `reduce.md` prompt.
4. A `Recorder` accumulates tokens/output; a `finally` block stores the run as `done`, `error` or `cancelled` (partial output kept).

## Decisions & trade-offs
- **Validate first, stream second** – once SSE headers are sent you can only emit an `error` event, so everything knowable up front is checked before.
- **One request at a time in map-reduce** – local models on laptops saturate quickly; concurrency 1 keeps latency predictable.
- **Evidence quotes** – every extracted value must carry a verbatim quote; we string-match (whitespace/case-insensitive) against the source and flag mismatches. It catches invented values, not subtle misreadings.
- **Retry with the validation error appended** – cheaper than regenerating blindly; stops after `JSON_MAX_RETRIES`, returning `valid:false` plus raw output.
- **Extraction defaults to temperature 0** – determinism helps format compliance.
- **Template sandbox** – prompts are user-editable code; `SandboxedEnvironment` blocks attribute tricks (tested).
- **Token estimation instead of a tokenizer** – avoids a heavy dependency; conservative margins (`−32` tokens) absorb the error.
