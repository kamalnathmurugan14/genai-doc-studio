import { useState } from "react";
import { post, type CompareSide, type Params } from "../api/client";

interface Variant {
  temperature: number;
  prompt: string;
}
interface Props {
  file: string | null;
  style: string;
  promptBody: string;
}

/** A/B: same document, two prompt/temperature variants side by side. */
export function CompareView({ file, style, promptBody }: Props) {
  const [a, setA] = useState<Variant>({ temperature: 0, prompt: "" });
  const [b, setB] = useState<Variant>({ temperature: 1, prompt: "" });
  const [res, setRes] = useState<{ a: CompareSide; b: CompareSide } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const side = (v: Variant) => ({
    task: "summarize",
    rel_path: file,
    style,
    prompt_body: v.prompt || undefined,
    params: { temperature: v.temperature } as Params,
  });
  const run = async () => {
    setBusy(true);
    setErr(null);
    setRes(null);
    try {
      setRes(await post("/compare", { run_a_inputs: side(a), run_b_inputs: side(b) }));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const col = (name: string, v: Variant, set: (v: Variant) => void, r?: CompareSide) => (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>Variant {name}</h3>
      <label>
        Temperature: {v.temperature.toFixed(2)}
        <input
          type="range"
          min={0}
          max={1.5}
          step={0.05}
          value={v.temperature}
          onChange={(e) => set({ ...v, temperature: Number(e.target.value) })}
          aria-label={`Temperature ${name}`}
        />
      </label>
      <label>
        Prompt (optional, uses {"{{ text }}"})
        <textarea
          className="mono"
          rows={3}
          value={v.prompt}
          placeholder={promptBody ? "leave empty for the default template" : ""}
          onChange={(e) => set({ ...v, prompt: e.target.value })}
          aria-label={`Prompt ${name}`}
        />
      </label>
      {r && (
        <>
          <pre className="output">{r.output}</pre>
          <p className="muted">
            {r.tokens_out} tokens out · {(r.ms / 1000).toFixed(1)} s · run #{r.run_id}
          </p>
        </>
      )}
    </div>
  );
  return (
    <section aria-label="Compare">
      <div className="row">
        <button className="primary" type="button" disabled={!file || busy} onClick={run}>
          {busy ? "Running both…" : "Run A and B"}
        </button>
        {!file && <span className="muted">Select a file in the explorer first.</span>}
      </div>
      {err && (
        <p className="error" role="alert">
          {err}
        </p>
      )}
      <div className="two">
        {col("A", a, setA, res?.a)}
        {col("B", b, setB, res?.b)}
      </div>
    </section>
  );
}
