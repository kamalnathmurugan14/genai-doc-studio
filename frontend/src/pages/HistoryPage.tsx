import { useState } from "react";
import type { Run } from "../api/client";
import { JsonViewer } from "../components/JsonViewer";
import { RunHistory } from "../components/RunHistory";

export function HistoryPage() {
  const [run, setRun] = useState<Run | null>(null);
  return (
    <>
      <h2>History</h2>
      <RunHistory onOpen={setRun} />
      {run && (
        <section className="card" aria-label="Run detail">
          <h3 style={{ marginTop: 0 }}>
            Run #{run.id} · {run.task}
          </h3>
          <p className="muted">
            {run.file_rel_path} · {run.prompt_name} v{run.prompt_version ?? "custom"} · {run.model} ·{" "}
            {JSON.stringify(run.params)} · {run.created_at}
          </p>
          {run.error && <p className="error">{run.error}</p>}
          {run.output_json ? (
            <JsonViewer result={run.output_json} />
          ) : (
            <pre className="output">{run.output_text}</pre>
          )}
        </section>
      )}
    </>
  );
}
