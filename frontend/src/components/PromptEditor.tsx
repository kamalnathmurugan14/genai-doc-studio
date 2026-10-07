import { useEffect, useState } from "react";
import { api, post, type PromptFull, type PromptVersion } from "../api/client";
import { useAsync } from "../hooks/useAsync";

interface Props {
  name: string;
  onBodyChange?: (body: string | undefined) => void;
}

/** Edit a template, see a live render with sample text, save a new version, or restore an old one. */
export function PromptEditor({ name, onBodyChange }: Props) {
  const prompt = useAsync(() => api<PromptFull>(`/prompts/${name}`), [name]);
  const versions = useAsync(() => api<{ versions: PromptVersion[] }>(`/prompts/${name}/versions`), [name]);
  const [body, setBody] = useState("");
  const [rendered, setRendered] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    if (prompt.data) {
      setBody(prompt.data.body);
      onBodyChange?.(undefined);
    }
  }, [prompt.data]); // eslint-disable-line react-hooks/exhaustive-deps

  // debounced live preview
  useEffect(() => {
    if (!body) return;
    const t = setTimeout(() => {
      post<{ rendered: string }>(`/prompts/${name}/preview`, { body })
        .then((r) => {
          setRendered(r.rendered);
          setErr(null);
        })
        .catch((e: Error) => setErr(e.message));
    }, 350);
    return () => clearTimeout(t);
  }, [body, name]);

  const dirty = prompt.data != null && body !== prompt.data.body;
  const save = async () => {
    try {
      await api(`/prompts/${name}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body, note: note || undefined }),
      });
      setMsg("Saved as a new version");
      setNote("");
      prompt.reload();
      versions.reload();
    } catch (e) {
      setMsg((e as Error).message);
    }
  };
  const restore = async (v: number) => {
    try {
      await post(`/prompts/${name}/restore/${v}`);
      setMsg(`Restored v${v} as a new version`);
      prompt.reload();
      versions.reload();
    } catch (e) {
      setMsg((e as Error).message);
    }
  };

  return (
    <section className="card" aria-label="Prompt editor">
      <div className="row">
        <h3 style={{ margin: 0, flex: 1 }}>
          Prompt: {name} {prompt.data && <span className="muted">v{prompt.data.version}</span>}
        </h3>
        {onBodyChange && (
          <button
            type="button"
            disabled={!dirty}
            onClick={() => onBodyChange(body)}
            title="Use the edited text for the next run without saving"
          >
            Use unsaved text
          </button>
        )}
      </div>
      {prompt.error && (
        <p className="error" role="alert">
          {prompt.error}
        </p>
      )}
      <label className="sr-only" htmlFor="prompt-body">
        Prompt template
      </label>
      <textarea
        id="prompt-body"
        className="mono"
        rows={12}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        spellCheck={false}
      />
      {err && (
        <p className="error" role="alert">
          {err}
        </p>
      )}
      <div className="row">
        <input
          type="text"
          placeholder="note (optional)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          aria-label="Version note"
        />
        <button className="primary" type="button" disabled={!dirty || !!err} onClick={save}>
          Save new version
        </button>
      </div>
      {msg && <p role="status">{msg}</p>}
      <details open>
        <summary>Live preview (sample text)</summary>
        <pre className="output">{rendered}</pre>
      </details>
      <details>
        <summary>Versions ({versions.data?.versions.length ?? 0})</summary>
        <ul>
          {versions.data?.versions.map((v) => (
            <li key={v.version}>
              v{v.version} · {new Date(v.created_at).toLocaleString()}{" "}
              {v.note && <span className="muted">— {v.note}</span>}{" "}
              <button type="button" onClick={() => restore(v.version)}>
                Restore
              </button>
            </li>
          ))}
        </ul>
      </details>
    </section>
  );
}
