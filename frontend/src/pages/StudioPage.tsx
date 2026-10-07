import { useEffect, useState } from "react";
import { api, post, type ExtractResult, type Entry, type Params } from "../api/client";
import { ChunkSummaries } from "../components/ChunkSummaries";
import { CompareView } from "../components/CompareView";
import { FileExplorer } from "../components/FileExplorer";
import { JsonViewer } from "../components/JsonViewer";
import { ParamsPanel } from "../components/ParamsPanel";
import { PromptEditor } from "../components/PromptEditor";
import { StreamingOutput } from "../components/StreamingOutput";
import {
  DEFAULT_OPTIONS,
  promptFor,
  TaskSelector,
  type Task,
  type TaskOptions,
} from "../components/TaskSelector";
import { useStream } from "../hooks/useStream";

export function StudioPage() {
  const [file, setFile] = useState<Entry | null>(null);
  const [task, setTask] = useState<Task>("summarize");
  const [opts, setOpts] = useState<TaskOptions>(DEFAULT_OPTIONS);
  const [params, setParams] = useState<Params>({});
  const [models, setModels] = useState<string[]>([]);
  const [override, setOverride] = useState<string | undefined>();
  const [showPrompt, setShowPrompt] = useState(false);
  const [mode, setMode] = useState<"run" | "compare">("run");
  const [extract, setExtract] = useState<ExtractResult | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { state, start, stop, reset } = useStream();

  useEffect(() => {
    api<{ models: string[] }>("/models")
      .then((r) => setModels(r.models))
      .catch(() => setModels([]));
  }, []);
  useEffect(() => {
    reset();
    setExtract(null);
    setError(null);
  }, [task, reset]);

  const run = async () => {
    if (!file) return;
    setError(null);
    setExtract(null);
    if (task === "summarize")
      await start("/summarize", { rel_path: file.path, style: opts.style, params, prompt_body: override });
    else if (task === "transform")
      await start("/transform", {
        rel_path: file.path,
        action: opts.action,
        tone: opts.tone,
        target_language: opts.lang,
        params,
        prompt_body: override,
      });
    else {
      setExtracting(true);
      try {
        setExtract(
          await post<ExtractResult>("/extract", {
            rel_path: file.path,
            schema_name: opts.schema,
            params,
            prompt_body: override,
          }),
        );
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setExtracting(false);
      }
    }
  };
  const busy = state.running || extracting;
  const chunkTotal = (state.meta?.chunks as number | undefined) ?? undefined;

  return (
    <>
      <h2>Studio</h2>
      <div className="studio">
        <div>
          <FileExplorer onOpenFile={setFile} />
          {file && (
            <p className="muted">
              Selected: <strong>{file.path}</strong>
            </p>
          )}
        </div>
        <div>
          <TaskSelector task={task} onTask={setTask} opts={opts} onOpts={setOpts} />
          <div className="row" style={{ margin: "8px 0" }}>
            <div className="segmented" role="group" aria-label="Mode">
              <button type="button" aria-pressed={mode === "run"} onClick={() => setMode("run")}>
                Run
              </button>
              <button
                type="button"
                aria-pressed={mode === "compare"}
                onClick={() => setMode("compare")}
                disabled={task === "extract"}
              >
                A/B compare
              </button>
            </div>
            {mode === "run" && (
              <button className="primary" type="button" disabled={!file || busy} onClick={run}>
                {busy ? "Running…" : "▶ Run"}
              </button>
            )}
            <button type="button" onClick={() => setShowPrompt((s) => !s)}>
              {showPrompt ? "Hide" : "Edit"} prompt &amp; params
            </button>
            {override && <span className="chip warnchip">using unsaved prompt text</span>}
          </div>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {mode === "run" ? (
            <>
              {task === "extract" ? (
                <>
                  {extracting && (
                    <p className="muted" role="status">
                      Extracting and validating JSON…
                    </p>
                  )}
                  {extract && <JsonViewer result={extract} />}
                  {!extract && !extracting && !error && (
                    <p className="empty">Pick a file and a schema, then press Run.</p>
                  )}
                </>
              ) : (
                <>
                  <ChunkSummaries chunks={state.chunks} total={chunkTotal} />
                  <StreamingOutput
                    state={state}
                    onStop={stop}
                    filename={file ? file.name.replace(/\.[^.]+$/, "") + "_" + task : "output"}
                  />
                </>
              )}
            </>
          ) : (
            <CompareView file={file?.path ?? null} style={opts.style} promptBody={override ?? ""} />
          )}
        </div>
        {showPrompt && (
          <div>
            <ParamsPanel
              params={params}
              onChange={setParams}
              models={models}
              defaults={{ temperature: 0.3, max_tokens: 800 }}
            />
            <PromptEditor name={promptFor(task, opts)} onBodyChange={setOverride} />
          </div>
        )}
      </div>
    </>
  );
}
