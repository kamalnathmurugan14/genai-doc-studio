import type { StreamState } from "../hooks/useStream";

function download(name: string, text: string, type: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

interface Props {
  state: StreamState;
  onStop: () => void;
  filename?: string;
}

export function StreamingOutput({ state, onStop, filename = "output" }: Props) {
  const { text, running, error, stats } = state;
  return (
    <section className="card" aria-label="Output">
      <div className="row">
        <h3 style={{ margin: 0, flex: 1 }}>Output</h3>
        {running && (
          <button type="button" onClick={onStop}>
            ■ Stop
          </button>
        )}
        <button type="button" disabled={!text} onClick={() => navigator.clipboard?.writeText(text)}>
          Copy
        </button>
        <button
          type="button"
          disabled={!text}
          onClick={() => download(`${filename}.md`, text, "text/markdown")}
        >
          .md
        </button>
        <button
          type="button"
          disabled={!text}
          onClick={() => download(`${filename}.txt`, text, "text/plain")}
        >
          .txt
        </button>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {!text && !running && !error && <p className="empty">Pick a file, choose a task and press Run.</p>}
      <pre className="output" aria-live="polite">
        {text}
        {running && (
          <span className="cursor" aria-hidden>
            ▌
          </span>
        )}
      </pre>
      <p className="muted" role="status">
        {running
          ? "streaming…"
          : stats
            ? `${stats.tokens_in} tokens in · ${stats.tokens_out} tokens out · ${(stats.ms / 1000).toFixed(1)} s`
            : text
              ? "stopped"
              : ""}
      </p>
    </section>
  );
}
