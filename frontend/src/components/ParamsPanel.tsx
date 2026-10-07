import type { Params } from "../api/client";

interface Props {
  params: Params;
  onChange: (p: Params) => void;
  models: string[];
  defaults: { temperature: number; max_tokens: number };
}

export function ParamsPanel({ params, onChange, models, defaults }: Props) {
  const set = (patch: Params) => onChange({ ...params, ...patch });
  return (
    <fieldset className="card params">
      <legend>Model &amp; sampling</legend>
      <label>
        Model
        {models.length > 0 ? (
          <select value={params.model ?? ""} onChange={(e) => set({ model: e.target.value || undefined })}>
            <option value="">default</option>
            {models.map((m) => (
              <option key={m}>{m}</option>
            ))}
          </select>
        ) : (
          <input
            type="text"
            placeholder="default (Ollama not reachable)"
            value={params.model ?? ""}
            onChange={(e) => set({ model: e.target.value || undefined })}
          />
        )}
      </label>
      <label>
        Temperature: {(params.temperature ?? defaults.temperature).toFixed(2)}
        <input
          type="range"
          min={0}
          max={1.5}
          step={0.05}
          value={params.temperature ?? defaults.temperature}
          onChange={(e) => set({ temperature: Number(e.target.value) })}
        />
        <span className="muted">0 = focused / repeatable · 1+ = creative / risky</span>
      </label>
      <label>
        Top-p: {(params.top_p ?? 0.9).toFixed(2)}
        <input
          type="range"
          min={0.1}
          max={1}
          step={0.05}
          value={params.top_p ?? 0.9}
          onChange={(e) => set({ top_p: Number(e.target.value) })}
        />
      </label>
      <label>
        Max tokens
        <input
          type="number"
          min={16}
          max={8192}
          step={50}
          value={params.max_tokens ?? defaults.max_tokens}
          onChange={(e) => set({ max_tokens: Number(e.target.value) })}
        />
      </label>
    </fieldset>
  );
}
