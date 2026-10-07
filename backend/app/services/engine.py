"""The task engine: summarize (one-shot + map-reduce), extract (validated JSON), transform. Yields SSE-style event dicts."""

import json
import logging
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.config import Settings
from app.core.chunker import chunk_text
from app.core.extractors import extract as extract_file
from app.core.paths import ext_of, rel_posix, safe_resolve
from app.errors import AppError
from app.llm.client import LLM, Token, Usage, complete
from app.llm.options import GenParams
from app.llm.token_utils import estimate_tokens
from app.schemas.extraction import EXAMPLES, SCHEMAS
from app.services.prompt_store import PromptStore
from app.services.run_store import RunStore

log = logging.getLogger(__name__)
SYSTEM = "You follow instructions exactly, use only the provided document, and never invent information."
STYLES = ("short", "detailed", "bullets")
ACTIONS = {"rewrite": "rewrite_tone", "email": "email_from_doc", "report": "report_from_doc"}
LANG = {"ta": "ta", "tamil": "ta", "en": "en", "english": "en"}


@dataclass
class Recorder:
    """Accumulates what a run produced so it can be stored even if the client disconnects."""

    task: str
    file: str | None = None
    prompt_name: str | None = None
    params: dict = field(default_factory=dict)
    model: str = ""
    input_chars: int = 0
    out: list[str] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    t0: float = field(default_factory=time.perf_counter)
    saved: bool = False

    @property
    def ms(self) -> int:
        return int((time.perf_counter() - self.t0) * 1000)


class Engine:
    def __init__(self, settings: Settings, llm: LLM, prompts: PromptStore, runs: RunStore) -> None:
        self.s, self.llm, self.prompts, self.runs = settings, llm, prompts, runs

    # ---------- helpers ----------
    def load_text(self, rel_path: str) -> tuple[str, str]:
        path = safe_resolve(self.s.docs_root, rel_path)
        if not path.is_file() or ext_of(path.name) not in self.s.extensions:
            raise AppError("NOT_FOUND", "File not found or unsupported type", 404)
        try:
            text = extract_file(path).text
        except Exception as exc:  # noqa: BLE001
            raise AppError("EXTRACT_FAILED", f"Cannot read this file: {type(exc).__name__}", 422) from exc
        if not text.strip():
            raise AppError("NO_TEXT", "This file has no extractable text (scanned PDF?)", 422)
        return text, rel_posix(self.s.docs_root, path)

    def _max_tokens(self, p: GenParams) -> int:
        return p.max_tokens or self.s.default_max_tokens

    def _messages(self, user: str) -> list[dict]:
        return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]

    def _template(self, name: str | None, body: str | None) -> tuple[str, str | None, int | None]:
        if body is not None:
            return body, name, None
        g = self.prompts.get(name or "")
        return g["body"], name, g["version"]

    def _begin(self, task: str, rel: str | None, text: str, p: GenParams, name: str | None) -> Recorder:
        return Recorder(
            task=task,
            file=rel,
            prompt_name=name,
            input_chars=len(text),
            model=p.model or self.llm.default_model,
            params=p.model_dump(exclude_none=True),
        )

    def _save(
        self, rec: Recorder, status: str, version: int | None = None, error: str | None = None, output_json=None
    ) -> int | None:
        if rec.saved:
            return None
        rec.saved = True
        if rec.tokens_in == 0 and rec.tokens_out == 0:  # backend gave no counts -> estimate
            rec.tokens_out = estimate_tokens("".join(rec.out))
        return self.runs.add(
            task=rec.task,
            file_rel_path=rec.file,
            prompt_name=rec.prompt_name,
            prompt_version=version,
            model=rec.model,
            params=rec.params,
            input_chars=rec.input_chars,
            output_text="".join(rec.out),
            output_json=output_json,
            tokens_in=rec.tokens_in,
            tokens_out=rec.tokens_out,
            duration_ms=rec.ms,
            status=status,
            error=error,
        )

    async def _stream(self, user: str, p: GenParams, rec: Recorder) -> AsyncIterator[dict]:
        async for ev in self.llm.stream(self._messages(user), p):
            if isinstance(ev, Token):
                rec.out.append(ev.text)
                yield {"event": "token", "data": {"text": ev.text}}
            elif isinstance(ev, Usage):
                rec.tokens_in += ev.tokens_in
                rec.tokens_out += ev.tokens_out

    async def _complete(self, user: str, p: GenParams, rec: Recorder, messages: list[dict] | None = None) -> str:
        text, usage = await complete(self.llm, messages or self._messages(user), p)
        rec.tokens_in += usage.tokens_in
        rec.tokens_out += usage.tokens_out
        return text

    def _budget(self, overhead_text: str, max_tokens: int) -> int:
        b = self.s.context_tokens - estimate_tokens(overhead_text) - max_tokens - 32
        if b < 200:
            raise AppError(
                "CONTEXT_TOO_SMALL",
                "max_tokens leaves no room for the document in the context window; lower max_tokens or raise CONTEXT_TOKENS",
                422,
            )
        return b

    # ---------- map-reduce core ----------
    async def _map_reduce(self, text: str, p: GenParams, rec: Recorder) -> AsyncIterator[dict]:
        """Yields chunk_summary events, then one internal `_combined` event holding the text that fits the final prompt."""
        map_tmpl = self.prompts.get("map_chunk")["body"]
        red_tmpl = self.prompts.get("reduce")["body"]
        map_p = p.model_copy(update={"max_tokens": 300})
        map_budget = self._budget(self.prompts.render(None, map_tmpl, {"text": "", "index": 1, "total": 99}), 300)
        pieces = chunk_text(text, min(self.s.chunk_tokens, map_budget), self.s.chunk_overlap_tokens)
        yield {"event": "meta", "data": {"mode": "map_reduce", "chunks": len(pieces)}}
        summaries: list[str] = []
        for i, piece in enumerate(pieces, 1):  # sequential: one request at a time keeps small machines responsive
            s = (
                await self._complete(
                    self.prompts.render(None, map_tmpl, {"text": piece, "index": i, "total": len(pieces)}), map_p, rec
                )
            ).strip()
            summaries.append(s)
            yield {"event": "chunk_summary", "data": {"index": i, "total": len(pieces), "level": 1, "text": s}}
        final_budget = self._budget(
            self.prompts.render(None, red_tmpl, {"text": "", "style": "detailed"}), self._max_tokens(p)
        )
        level = 1
        while sum(estimate_tokens(s) for s in summaries) > final_budget and len(summaries) > 1:
            level += 1
            groups, cur, cur_t = [], [], 0
            for s in summaries:  # pack summaries into groups that each fit one prompt
                t = estimate_tokens(s)
                if cur and cur_t + t > final_budget:
                    groups.append(cur)
                    cur, cur_t = [], 0
                cur.append(s)
                cur_t += t
            groups.append(cur)
            if len(groups) >= len(summaries):
                break  # cannot shrink further
            summaries = []
            for j, g in enumerate(groups, 1):
                s = (
                    await self._complete(
                        self.prompts.render(None, red_tmpl, {"text": "\n\n".join(g), "style": "detailed"}), map_p, rec
                    )
                ).strip()
                summaries.append(s)
                yield {"event": "chunk_summary", "data": {"index": j, "total": len(groups), "level": level, "text": s}}
        combined = "\n\n".join(summaries)
        if estimate_tokens(combined) > final_budget:  # last resort: hard cut
            combined = combined[: final_budget * 4]
        yield {"event": "_combined", "data": {"text": combined}}

    # ---------- summarize ----------
    async def summarize(
        self,
        rel_path: str | None,
        text: str | None,
        style: str,
        p: GenParams,
        prompt_name: str | None = None,
        prompt_body: str | None = None,
    ) -> AsyncIterator[dict]:
        if style not in STYLES:
            raise AppError("BAD_STYLE", f"style must be one of {', '.join(STYLES)}", 422)
        rel = None
        if text is None:
            text, rel = self.load_text(rel_path or "")
        name = prompt_name or f"summarize_{style}"
        tmpl, name, version = self._template(name, prompt_body)
        self.prompts.render(None, tmpl, {"text": "", "style": style})  # fail fast on a broken template
        budget = self._budget(
            self.prompts.render(None, tmpl, {"text": "", "style": style}), self._max_tokens(p)
        )  # fail fast -> HTTP 422
        rec = self._begin("summarize", rel, text, p, name)
        return self._summarize_events(rec, text, style, p, tmpl, version, budget)

    async def _summarize_events(
        self, rec: Recorder, text: str, style: str, p: GenParams, tmpl: str, version: int | None, budget: int
    ) -> AsyncIterator[dict]:
        status, err = "cancelled", None
        try:
            if estimate_tokens(text) <= budget:
                yield {
                    "event": "meta",
                    "data": {"task": "summarize", "mode": "one_shot", "model": rec.model, "style": style},
                }
                async for ev in self._stream(self.prompts.render(None, tmpl, {"text": text, "style": style}), p, rec):
                    yield ev
            else:
                combined = ""
                async for ev in self._map_reduce(text, p, rec):
                    if ev["event"] == "_combined":
                        combined = ev["data"]["text"]
                    else:
                        yield ev
                red = (
                    tmpl
                    if rec.prompt_name != f"summarize_{style}" or version is None
                    else self.prompts.get("reduce")["body"]
                )
                async for ev in self._stream(
                    self.prompts.render(None, red, {"text": combined, "style": style}), p, rec
                ):
                    yield ev
            status = "done"
            run_id = self._save(rec, status, version)
            yield {
                "event": "done",
                "data": {"tokens_in": rec.tokens_in, "tokens_out": rec.tokens_out, "ms": rec.ms, "run_id": run_id},
            }
        except AppError as exc:
            status, err = "error", exc.message
            self._save(rec, status, version, err)
            yield {"event": "error", "data": {"code": exc.code, "message": exc.message}}
        finally:
            self._save(rec, "cancelled", version)  # no-op when already saved; records partial output on disconnect

    # ---------- extract ----------
    @staticmethod
    def parse_json(raw: str) -> dict:
        """Tolerant parser: strips ``` fences and any prose around the outermost {...}."""
        t = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
        i, j = t.find("{"), t.rfind("}")
        if i == -1 or j <= i:
            raise ValueError("no JSON object found in the output")
        obj = json.loads(t[i : j + 1])
        if not isinstance(obj, dict):
            raise ValueError("top-level JSON value must be an object")
        return obj

    @staticmethod
    def _norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip().casefold()

    def _verify(self, node, source_norm: str, path: str, unverified: list[dict]):
        """Mark every {value, evidence} item with verified=True/False (evidence must be a real quote)."""
        if isinstance(node, dict):
            if "value" in node and "evidence" in node:
                ev = self._norm(str(node["evidence"]))
                node["verified"] = bool(ev) and ev in source_norm
                if not node["verified"]:
                    unverified.append({"path": path, "value": node["value"]})
                return node
            return {k: self._verify(v, source_norm, f"{path}.{k}" if path else k, unverified) for k, v in node.items()}
        if isinstance(node, list):
            return [self._verify(v, source_norm, f"{path}[{i}]", unverified) for i, v in enumerate(node)]
        return node

    async def extract(
        self, rel_path: str | None, text: str | None, schema_name: str, p: GenParams, prompt_body: str | None = None
    ) -> dict:
        if schema_name not in SCHEMAS:
            raise AppError("BAD_SCHEMA", f"schema_name must be one of {', '.join(SCHEMAS)}", 422)
        rel = None
        if text is None:
            text, rel = self.load_text(rel_path or "")
        tmpl, name, version = self._template("extract_entities", prompt_body)
        p = p.model_copy(
            update={"temperature": 0.0 if p.temperature is None else p.temperature}
        )  # extraction wants determinism
        rec = self._begin("extract", rel, text, p, name)
        schema_cls, example = SCHEMAS[schema_name], EXAMPLES[schema_name]
        budget = self._budget(self.prompts.render(None, tmpl, {"text": "", "schema": example}), self._max_tokens(p))
        truncated = estimate_tokens(text) > budget
        used = text[: budget * 4] if truncated else text
        messages = self._messages(self.prompts.render(None, tmpl, {"text": used, "schema": example}))
        raw, errors, attempts = "", "", 0
        try:
            for attempts in range(1, self.s.json_max_retries + 2):
                raw = await self._complete("", p, rec, messages)
                try:
                    obj = schema_cls.model_validate(self.parse_json(raw))
                    unverified: list[dict] = []
                    data = self._verify(obj.model_dump(), self._norm(used), "", unverified)
                    result = {
                        "data": data,
                        "valid": True,
                        "attempts": attempts,
                        "raw": raw,
                        "unverified": unverified,
                        "truncated": truncated,
                        "schema_name": schema_name,
                    }
                    result["run_id"] = self._save(rec, "done", version, output_json=result)
                    return result
                except (ValueError, ValidationError) as exc:
                    errors = self._errors(exc)
                    messages = [
                        *messages,
                        {"role": "assistant", "content": raw},
                        {
                            "role": "user",
                            "content": f"Your output was invalid: {errors}\nFix these errors and return ONLY the corrected JSON object.",
                        },
                    ]
            result = {
                "data": None,
                "valid": False,
                "attempts": attempts,
                "raw": raw,
                "errors": errors,
                "unverified": [],
                "truncated": truncated,
                "schema_name": schema_name,
            }
            result["run_id"] = self._save(rec, "done", version, errors, output_json=result)
            return result
        except AppError as exc:
            self._save(rec, "error", version, exc.message)
            raise

    @staticmethod
    def _errors(exc: Exception) -> str:
        if isinstance(exc, ValidationError):
            return "; ".join(f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors()[:5])
        return str(exc)[:300]

    # ---------- transform ----------
    async def transform(
        self,
        action: str,
        rel_path: str | None,
        text: str | None,
        tone: str | None,
        target_language: str | None,
        p: GenParams,
        prompt_name: str | None = None,
        prompt_body: str | None = None,
    ) -> AsyncIterator[dict]:
        if action == "translate":
            lang = LANG.get((target_language or "").lower())
            if lang is None:
                raise AppError("BAD_LANGUAGE", "target_language must be 'ta' (Tamil) or 'en' (English)", 422)
            name = "translate_en_ta" if lang == "ta" else "translate_ta_en"
        elif action in ACTIONS:
            name = ACTIONS[action]
        else:
            raise AppError("BAD_ACTION", "action must be one of rewrite, translate, email, report", 422)
        rel = None
        if text is None:
            if not rel_path:
                raise AppError("MISSING_INPUT", "Provide rel_path or text", 422)
            text, rel = self.load_text(rel_path)
        tmpl, name, version = self._template(prompt_name or name, prompt_body)
        self.prompts.render(None, tmpl, {"text": "", "tone": tone or "professional"})
        budget = self._budget(
            self.prompts.render(None, tmpl, {"text": "", "tone": tone or "professional"}), self._max_tokens(p)
        )
        rec = self._begin(f"transform:{action}", rel, text, p, name)
        return self._transform_events(rec, action, text, tone or "professional", tmpl, version, p, budget)

    async def _transform_events(
        self,
        rec: Recorder,
        action: str,
        text: str,
        tone: str,
        tmpl: str,
        version: int | None,
        p: GenParams,
        budget: int,
    ) -> AsyncIterator[dict]:
        try:
            yield {
                "event": "meta",
                "data": {
                    "task": rec.task,
                    "model": rec.model,
                    "note": "Tamil quality varies by model." if "translate" in rec.task else None,
                },
            }
            if estimate_tokens(text) <= budget:
                async for ev in self._stream(self.prompts.render(None, tmpl, {"text": text, "tone": tone}), p, rec):
                    yield ev
            elif action in ("rewrite", "translate"):  # chunk-wise, in order; output = concatenation
                pieces = chunk_text(text, min(budget, self.s.chunk_tokens), 0)
                for i, piece in enumerate(pieces, 1):
                    if i > 1:
                        rec.out.append("\n\n")
                        yield {"event": "token", "data": {"text": "\n\n"}}
                    async for ev in self._stream(
                        self.prompts.render(None, tmpl, {"text": piece, "tone": tone}), p, rec
                    ):
                        yield ev
            else:  # email / report: condense first, then write from the condensed text
                combined = ""
                async for ev in self._map_reduce(text, p, rec):
                    if ev["event"] == "_combined":
                        combined = ev["data"]["text"]
                    else:
                        yield ev
                async for ev in self._stream(self.prompts.render(None, tmpl, {"text": combined, "tone": tone}), p, rec):
                    yield ev
            run_id = self._save(rec, "done", version)
            yield {
                "event": "done",
                "data": {"tokens_in": rec.tokens_in, "tokens_out": rec.tokens_out, "ms": rec.ms, "run_id": run_id},
            }
        except AppError as exc:
            self._save(rec, "error", version, exc.message)
            yield {"event": "error", "data": {"code": exc.code, "message": exc.message}}
        finally:
            self._save(rec, "cancelled", version)

    # ---------- plain streaming (M3 echo/test endpoint) ----------
    async def raw_stream(self, prompt: str, p: GenParams) -> AsyncIterator[dict]:
        rec = Recorder(
            task="stream",
            model=p.model or self.llm.default_model,
            params=p.model_dump(exclude_none=True),
            input_chars=len(prompt),
        )
        try:
            yield {"event": "meta", "data": {"task": "stream", "model": rec.model}}
            async for ev in self._stream(prompt, p, rec):
                yield ev
            run_id = self._save(rec, "done")
            yield {
                "event": "done",
                "data": {"tokens_in": rec.tokens_in, "tokens_out": rec.tokens_out, "ms": rec.ms, "run_id": run_id},
            }
        except AppError as exc:
            self._save(rec, "error", None, exc.message)
            yield {"event": "error", "data": {"code": exc.code, "message": exc.message}}
        finally:
            self._save(rec, "cancelled")


async def collect(events: AsyncIterator[dict]) -> dict:
    """Drain an event stream into one dict (used by /compare)."""
    out: list[str] = []
    chunks: list[dict] = []
    done: dict = {}
    async for ev in events:
        if ev["event"] == "token":
            out.append(ev["data"]["text"])
        elif ev["event"] == "chunk_summary":
            chunks.append(ev["data"])
        elif ev["event"] == "done":
            done = ev["data"]
        elif ev["event"] == "error":
            raise AppError(ev["data"]["code"], ev["data"]["message"], 502)
    return {"output": "".join(out), "chunk_summaries": chunks, **done}
