import { useState } from "react";
import { api, qs, type Run } from "../api/client";
import { useAsync } from "../hooks/useAsync";

export function RunHistory({ onOpen }: { onOpen: (r: Run) => void }) {
  const [task, setTask] = useState("");
  const [file, setFile] = useState("");
  const runs = useAsync(() => api<{ runs: Run[] }>("/runs?" + qs({ task, file })), [task, file]);
  return (
    <section className="card" aria-label="Run history">
      <div className="row">
        <label>
          Task{" "}
          <select value={task} onChange={(e) => setTask(e.target.value)}>
            <option value="">all</option>
            <option>summarize</option>
            <option>extract</option>
            <option value="transform:rewrite">transform:rewrite</option>
            <option value="transform:translate">transform:translate</option>
            <option value="transform:email">transform:email</option>
            <option value="transform:report">transform:report</option>
          </select>
        </label>
        <label>
          File{" "}
          <input
            type="text"
            placeholder="filter by name"
            value={file}
            onChange={(e) => setFile(e.target.value)}
          />
        </label>
        <button type="button" onClick={runs.reload}>
          Refresh
        </button>
      </div>
      {runs.loading && <p className="muted">Loading…</p>}
      {runs.error && (
        <p className="error" role="alert">
          {runs.error}
        </p>
      )}
      {runs.data?.runs.length === 0 && <p className="empty">No runs yet.</p>}
      {!!runs.data?.runs.length && (
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>task</th>
              <th>file</th>
              <th>model</th>
              <th className="num">tokens</th>
              <th className="num">time</th>
              <th>status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {runs.data.runs.map((r) => (
              <tr key={r.id}>
                <td>{r.id}</td>
                <td>{r.task}</td>
                <td>{r.file_rel_path ?? "–"}</td>
                <td>{r.model}</td>
                <td className="num">
                  {r.tokens_in}/{r.tokens_out}
                </td>
                <td className="num">{(r.duration_ms / 1000).toFixed(1)}s</td>
                <td className={r.status === "error" ? "error" : ""}>{r.status}</td>
                <td>
                  <button type="button" onClick={() => onOpen(r)}>
                    Open
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
