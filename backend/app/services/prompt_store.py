"""Prompt templates: .md files are the source of truth, every save also creates a DB version."""

import re
from datetime import UTC, datetime

from jinja2 import TemplateSyntaxError
from jinja2.meta import find_undeclared_variables
from jinja2.sandbox import SandboxedEnvironment

from app.config import Settings
from app.db.session import connect
from app.errors import AppError

NAME_RE = re.compile(r"^[a-z0-9_]{1,60}$")
ENV = SandboxedEnvironment(autoescape=False, trim_blocks=False)
SAMPLE = {
    "text": "Acme Corp invoice INV-1042 for $1,000 is due on 2026-01-31. Priya will confirm payment.",
    "style": "short",
    "language": "Tamil",
    "tone": "friendly",
    "schema": '{"example": "..."}',
    "index": 1,
    "total": 3,
}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def check_template(body: str) -> list[str]:
    """Validate Jinja syntax; return the variables the template uses. Raises 422 on errors."""
    try:
        ast = ENV.parse(body)
        ENV.from_string(body)
    except TemplateSyntaxError as exc:
        raise AppError("TEMPLATE_SYNTAX", f"Template error on line {exc.lineno}: {exc.message}", 422) from exc
    return sorted(find_undeclared_variables(ast))


def render_template(body: str, variables: dict) -> str:
    try:
        return ENV.from_string(body).render(**variables)
    except Exception as exc:  # noqa: BLE001 - e.g. sandbox violations
        raise AppError("TEMPLATE_RENDER", f"Template could not be rendered: {type(exc).__name__}", 422) from exc


class PromptStore:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self.dir = settings.prompts_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        for f in sorted(self.dir.glob("*.md")):  # seed version 1 for every file that has no history
            with connect(self.s.db_path) as con:
                if con.execute("SELECT 1 FROM prompt_versions WHERE name=?", (f.stem,)).fetchone() is None:
                    con.execute(
                        "INSERT INTO prompt_versions(name,version,body,note,created_at) VALUES(?,?,?,?,?)",
                        (f.stem, 1, f.read_text(encoding="utf-8"), "initial", _now()),
                    )

    def _path(self, name: str):
        if not NAME_RE.match(name):
            raise AppError("BAD_PROMPT_NAME", "Prompt names may contain a-z, 0-9 and _ only", 422)
        return self.dir / f"{name}.md"

    def names(self) -> list[str]:
        return sorted(p.stem for p in self.dir.glob("*.md"))

    def get(self, name: str) -> dict:
        p = self._path(name)
        if not p.exists():
            raise AppError("PROMPT_NOT_FOUND", f"No prompt named '{name}'", 404)
        body = p.read_text(encoding="utf-8")
        with connect(self.s.db_path) as con:
            v = con.execute("SELECT MAX(version) FROM prompt_versions WHERE name=?", (name,)).fetchone()[0]
        return {"name": name, "body": body, "version": v or 1, "variables": check_template(body)}

    def list_all(self) -> list[dict]:
        out = []
        for n in self.names():
            g = self.get(n)
            out.append({"name": n, "version": g["version"], "variables": g["variables"]})
        return out

    def save(self, name: str, body: str, note: str | None = None) -> dict:
        p = self._path(name)
        if not body.strip():
            raise AppError("EMPTY_PROMPT", "Prompt body must not be empty", 422)
        check_template(body)  # validate BEFORE touching the file
        with connect(self.s.db_path) as con:
            v = (con.execute("SELECT MAX(version) FROM prompt_versions WHERE name=?", (name,)).fetchone()[0] or 0) + 1
            con.execute(
                "INSERT INTO prompt_versions(name,version,body,note,created_at) VALUES(?,?,?,?,?)",
                (name, v, body, note, _now()),
            )
        p.write_text(body, encoding="utf-8")
        return self.get(name)

    def versions(self, name: str) -> list[dict]:
        self.get(name)
        with connect(self.s.db_path) as con:
            rows = con.execute(
                "SELECT version, note, created_at, body FROM prompt_versions WHERE name=? ORDER BY version DESC",
                (name,),
            ).fetchall()
        return [dict(r) for r in rows]

    def restore(self, name: str, version: int) -> dict:
        with connect(self.s.db_path) as con:
            row = con.execute("SELECT body FROM prompt_versions WHERE name=? AND version=?", (name, version)).fetchone()
        if row is None:
            raise AppError("VERSION_NOT_FOUND", f"Prompt '{name}' has no version {version}", 404)
        return self.save(name, row["body"], f"restored from v{version}")

    def render(self, name_or_none: str | None, body: str | None, variables: dict) -> str:
        text = body if body is not None else self.get(name_or_none or "")["body"]
        check_template(text)
        return render_template(text, variables)

    def preview(self, name: str, body: str | None) -> dict:
        text = body if body is not None else self.get(name)["body"]
        used = check_template(text)
        return {"variables": used, "rendered": render_template(text, SAMPLE)}
