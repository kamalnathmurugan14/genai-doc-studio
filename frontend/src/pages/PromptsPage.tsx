import { useState } from "react";
import { api, type PromptInfo } from "../api/client";
import { PromptEditor } from "../components/PromptEditor";
import { useAsync } from "../hooks/useAsync";

export function PromptsPage() {
  const list = useAsync(() => api<{ prompts: PromptInfo[] }>("/prompts"), []);
  const [name, setName] = useState<string | null>(null);
  return (
    <>
      <h2>Prompt templates</h2>
      <p className="muted">
        Templates are Jinja2 files in <code>backend/app/prompts</code>. Every save creates a new version; the
        file always holds the latest.
      </p>
      {list.error && (
        <p className="error" role="alert">
          {list.error}
        </p>
      )}
      <div className="two">
        <div className="card">
          {list.loading && <p className="muted">Loading…</p>}
          <ul className="plain">
            {list.data?.prompts.map((p) => (
              <li key={p.name}>
                <button
                  type="button"
                  className={name === p.name ? "chip active" : "chip"}
                  onClick={() => setName(p.name)}
                >
                  {p.name}
                </button>{" "}
                <span className="muted">
                  v{p.version} · {p.variables.join(", ")}
                </span>
              </li>
            ))}
          </ul>
        </div>
        {name ? <PromptEditor key={name} name={name} /> : <p className="empty">Choose a template to edit.</p>}
      </div>
    </>
  );
}
