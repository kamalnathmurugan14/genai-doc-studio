import { useCallback, useRef, useState } from "react";
import type { ChunkSummary } from "../api/client";
import { streamPost } from "../api/sse";

export interface StreamState {
  text: string;
  running: boolean;
  error: string | null;
  chunks: ChunkSummary[];
  meta: Record<string, unknown> | null;
  stats: { tokens_in: number; tokens_out: number; ms: number; run_id: number } | null;
}
const EMPTY: StreamState = { text: "", running: false, error: null, chunks: [], meta: null, stats: null };

/** Runs a streaming task; `stop()` aborts the fetch, which makes the backend abort the Ollama request. */
export function useStream() {
  const [state, setState] = useState<StreamState>(EMPTY);
  const ctrl = useRef<AbortController | null>(null);

  const start = useCallback(async (path: string, body: unknown) => {
    ctrl.current?.abort();
    const c = new AbortController();
    ctrl.current = c;
    setState({ ...EMPTY, running: true });
    try {
      await streamPost(
        path,
        body,
        (e) => {
          setState((s) => {
            if (e.event === "token") return { ...s, text: s.text + e.data.text };
            if (e.event === "chunk_summary") return { ...s, chunks: [...s.chunks, e.data] };
            if (e.event === "meta") return { ...s, meta: e.data };
            if (e.event === "done") return { ...s, stats: e.data };
            if (e.event === "error") return { ...s, error: e.data.message };
            return s;
          });
        },
        c.signal,
      );
    } catch (e) {
      setState((s) => ({ ...s, error: (e as Error).message }));
    } finally {
      setState((s) => ({ ...s, running: false }));
    }
  }, []);

  const stop = useCallback(() => ctrl.current?.abort(), []);
  const reset = useCallback(() => setState(EMPTY), []);
  return { state, start, stop, reset };
}
