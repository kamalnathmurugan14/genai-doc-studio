export type Task = "summarize" | "extract" | "transform";
export interface TaskOptions {
  style: "short" | "detailed" | "bullets";
  schema: "entities" | "invoice" | "contract" | "meeting";
  action: "rewrite" | "translate" | "email" | "report";
  tone: string;
  lang: "ta" | "en";
}
export const DEFAULT_OPTIONS: TaskOptions = {
  style: "short",
  schema: "entities",
  action: "rewrite",
  tone: "professional",
  lang: "ta",
};

interface Props {
  task: Task;
  onTask: (t: Task) => void;
  opts: TaskOptions;
  onOpts: (o: TaskOptions) => void;
}

export function TaskSelector({ task, onTask, opts, onOpts }: Props) {
  const set = (p: Partial<TaskOptions>) => onOpts({ ...opts, ...p });
  return (
    <div className="card">
      <div role="tablist" aria-label="Task" className="segmented">
        {(["summarize", "extract", "transform"] as Task[]).map((t) => (
          <button
            key={t}
            role="tab"
            type="button"
            aria-selected={task === t}
            aria-pressed={task === t}
            onClick={() => onTask(t)}
          >
            {t}
          </button>
        ))}
      </div>
      <div className="row" style={{ marginTop: 10 }}>
        {task === "summarize" && (
          <label>
            Style{" "}
            <select
              value={opts.style}
              onChange={(e) => set({ style: e.target.value as TaskOptions["style"] })}
            >
              <option value="short">short</option>
              <option value="detailed">detailed</option>
              <option value="bullets">bullets</option>
            </select>
          </label>
        )}
        {task === "extract" && (
          <label>
            Schema{" "}
            <select
              value={opts.schema}
              onChange={(e) => set({ schema: e.target.value as TaskOptions["schema"] })}
            >
              <option value="entities">entities</option>
              <option value="invoice">invoice</option>
              <option value="contract">contract</option>
              <option value="meeting">meeting notes</option>
            </select>
          </label>
        )}
        {task === "transform" && (
          <>
            <label>
              Action{" "}
              <select
                value={opts.action}
                onChange={(e) => set({ action: e.target.value as TaskOptions["action"] })}
              >
                <option value="rewrite">rewrite (tone)</option>
                <option value="translate">translate</option>
                <option value="email">draft email</option>
                <option value="report">draft report</option>
              </select>
            </label>
            {(opts.action === "rewrite" || opts.action === "email") && (
              <label>
                Tone <input type="text" value={opts.tone} onChange={(e) => set({ tone: e.target.value })} />
              </label>
            )}
            {opts.action === "translate" && (
              <label>
                Direction{" "}
                <select
                  value={opts.lang}
                  onChange={(e) => set({ lang: e.target.value as TaskOptions["lang"] })}
                >
                  <option value="ta">English → Tamil</option>
                  <option value="en">Tamil → English</option>
                </select>
              </label>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/** Which prompt template a task uses by default. */
export function promptFor(task: Task, o: TaskOptions): string {
  if (task === "summarize") return `summarize_${o.style}`;
  if (task === "extract") return "extract_entities";
  return o.action === "translate"
    ? o.lang === "ta"
      ? "translate_en_ta"
      : "translate_ta_en"
    : o.action === "rewrite"
      ? "rewrite_tone"
      : o.action === "email"
        ? "email_from_doc"
        : "report_from_doc";
}
