"""Run history."""

import json
from datetime import UTC, datetime

from app.config import Settings
from app.db.session import connect
from app.errors import AppError


class RunStore:
    def __init__(self, settings: Settings) -> None:
        self.s = settings

    def add(self, **f) -> int:
        row = {
            "task": "",
            "file_rel_path": None,
            "prompt_name": None,
            "prompt_version": None,
            "model": None,
            "params": {},
            "input_chars": 0,
            "output_text": None,
            "output_json": None,
            "tokens_in": 0,
            "tokens_out": 0,
            "duration_ms": 0,
            "status": "done",
            "error": None,
            **f,
        }
        with connect(self.s.db_path) as con:
            return int(
                con.execute(
                    "INSERT INTO runs(task,file_rel_path,prompt_name,prompt_version,model,params_json,input_chars,output_text,output_json,"
                    "tokens_in,tokens_out,duration_ms,status,error,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        row["task"],
                        row["file_rel_path"],
                        row["prompt_name"],
                        row["prompt_version"],
                        row["model"],
                        json.dumps(row["params"]),
                        row["input_chars"],
                        row["output_text"],
                        json.dumps(row["output_json"]) if row["output_json"] is not None else None,
                        row["tokens_in"],
                        row["tokens_out"],
                        row["duration_ms"],
                        row["status"],
                        row["error"],
                        datetime.now(UTC).isoformat(timespec="seconds"),
                    ),
                ).lastrowid
            )

    @staticmethod
    def _row(r, full: bool) -> dict:
        d = dict(r)
        d["params"] = json.loads(d.pop("params_json") or "{}")
        d["output_json"] = json.loads(d["output_json"]) if d["output_json"] else None
        if not full and d["output_text"]:
            d["output_text"] = d["output_text"][:300]
        return d

    def list_all(self, task: str = "", file: str = "", limit: int = 100) -> list[dict]:
        sql, args = "SELECT * FROM runs WHERE 1=1", []
        if task:
            sql += " AND task=?"
            args.append(task)
        if file:
            sql += " AND file_rel_path LIKE ?"
            args.append(f"%{file}%")
        with connect(self.s.db_path) as con:
            rows = con.execute(sql + " ORDER BY id DESC LIMIT ?", (*args, limit)).fetchall()
        return [self._row(r, False) for r in rows]

    def get(self, run_id: int) -> dict:
        with connect(self.s.db_path) as con:
            r = con.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if r is None:
            raise AppError("RUN_NOT_FOUND", "Run not found", 404)
        return self._row(r, True)
