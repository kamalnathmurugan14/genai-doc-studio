import type { Evidenced, ExtractResult } from "../api/client";

const isItem = (v: unknown): v is Evidenced =>
  typeof v === "object" && v !== null && "value" in v && "evidence" in v;

function Node({ k, v }: { k: string; v: unknown }) {
  if (v == null)
    return (
      <li>
        <strong>{k}:</strong> <span className="muted">not found</span>
      </li>
    );
  if (isItem(v))
    return (
      <li>
        <strong>{k}:</strong> {v.value}{" "}
        <span className={`chip ${v.verified ? "ok" : "warnchip"}`} title={v.evidence}>
          {v.verified ? "✔ verified" : "⚠ unverified"}
        </span>
        <div className="muted quote">“{v.evidence}”</div>
      </li>
    );
  if (Array.isArray(v))
    return (
      <li>
        <strong>{k}:</strong> {v.length === 0 && <span className="muted">none</span>}
        <ul>
          {v.map((x, i) => (
            <Node key={i} k={`#${i + 1}`} v={x} />
          ))}
        </ul>
      </li>
    );
  if (typeof v === "object")
    return (
      <li>
        <strong>{k}</strong>
        <ul>
          {Object.entries(v).map(([kk, vv]) => (
            <Node key={kk} k={kk} v={vv} />
          ))}
        </ul>
      </li>
    );
  return (
    <li>
      <strong>{k}:</strong> {String(v)}
    </li>
  );
}

export function JsonViewer({ result }: { result: ExtractResult }) {
  return (
    <section className="card" aria-label="Extraction result">
      <div className="row">
        <h3 style={{ margin: 0, flex: 1 }}>Extracted data</h3>
        <span className={`chip ${result.valid ? "ok" : "warnchip"}`}>
          {result.valid ? "valid JSON" : "invalid JSON"}
        </span>
        <span className="muted">
          attempt{result.attempts > 1 ? "s" : ""}: {result.attempts}
        </span>
      </div>
      {result.truncated && (
        <p className="warn">
          ⚠ The document was longer than the context window; only the beginning was used.
        </p>
      )}
      {result.valid && result.unverified.length > 0 && (
        <p className="warn" role="alert">
          ⚠ {result.unverified.length} value(s) have evidence that is not in the document — treat as possible
          hallucinations.
        </p>
      )}
      {result.valid && result.data && (
        <ul className="tree">
          {Object.entries(result.data).map(([k, v]) => (
            <Node key={k} k={k} v={v} />
          ))}
        </ul>
      )}
      {!result.valid && (
        <>
          <p className="error" role="alert">
            The model never produced valid JSON: {result.errors}
          </p>
          <details>
            <summary>Raw output</summary>
            <pre className="output">{result.raw}</pre>
          </details>
        </>
      )}
      {result.valid && (
        <details>
          <summary>Raw JSON</summary>
          <pre className="output">{JSON.stringify(result.data, null, 2)}</pre>
        </details>
      )}
    </section>
  );
}
