# Learning notes

## Prompt engineering notes
A good prompt has **role → task → constraints → output format → input**. Open `backend/app/prompts/*.md`; every template follows this layout.
- **Zero-shot vs few-shot** — zero-shot gives only instructions (what we use); few-shot adds 1–3 worked examples, which helps small models follow a format. *Try:* add an example JSON to `extract_entities` and compare retry counts.
- **Constraints beat hopes** — "Use ONLY the document; write `Not found` if absent" measurably reduces invented details.
- **Temperature** — scales randomness when sampling the next token. 0 ≈ always the most likely token (repeatable, can be dull/repetitive); ~0.3 balanced; ≥1 diverse but error-prone. **top-p** keeps only the smallest set of tokens covering p of the probability mass. Change one at a time.
- **Run it yourself:** `python backend/scripts/temperature_experiment.py meeting_notes.txt` runs 0.0/0.5/1.0 twice each against *your* model and writes `docs/PROMPT_EXPERIMENTS.md` — compare how outputs vary between runs at each setting. (Outputs depend on the model, so none are baked into these docs.)
- **Context window** — prompt + answer must fit; otherwise the start of the prompt is silently dropped. That's why long documents use map-reduce.
- **Hallucination** — models produce plausible text, not verified facts. Mitigate by grounding (document only), quoting evidence, validating structure, low temperature, and human review.

## Milestones
**M0 Scaffold** — health also reports Ollama reachability. **M1 Safe FS** — see project 1.
**M2 Extractors + token-aware chunker** — chunk by estimated tokens (chars÷4) so a "1500-token" chunk really fits. *Mistake:* using characters as if they were tokens; Tamil text uses far more tokens per character.
**M3 LLM client + SSE** — an async generator yields tokens; leaving the `async with` block closes the HTTP stream, which is how **Stop** cancels generation. *Try:* press Stop and watch `ollama ps` / GPU usage drop.
**M4 One-shot summaries** — three templates, one engine. *Try:* edit `summarize_short` to demand "exactly 20 words".
**M5 Map-reduce** — split → summarise parts → combine. *Mistake:* concatenating part summaries that are themselves too long (we reduce hierarchically). Expect some loss of detail — map-reduce trades fidelity for coverage.
**M6 Structured extraction** — Pydantic schema + tolerant JSON parsing (strip fences/prose) + retry with the exact validation errors + evidence verification. *Try:* use a tiny model and watch `attempts` go above 1.
**M7 Transform** — rewrite/translate/email/report; long inputs are chunked in order (rewrite/translate) or condensed first (email/report).
**M8 Prompt editor** — versions, restore (a restore *adds* a version, so history is never rewritten), live Jinja preview, sandboxed rendering.
**M9 Params + history + compare** — token/time counters, run history, A/B on the same document.
**M10 Polish** — docs, demo script, Playwright smoke test.
