import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { parseBlock } from "../api/sse";
import type { ExtractResult } from "../api/client";
import type { StreamState } from "../hooks/useStream";
import { ChunkSummaries } from "./ChunkSummaries";
import { JsonViewer } from "./JsonViewer";
import { ParamsPanel } from "./ParamsPanel";
import { StreamingOutput } from "./StreamingOutput";
import { DEFAULT_OPTIONS, promptFor, TaskSelector } from "./TaskSelector";

afterEach(() => vi.restoreAllMocks());

const st = (p: Partial<StreamState>): StreamState => ({
  text: "",
  running: false,
  error: null,
  chunks: [],
  meta: null,
  stats: null,
  ...p,
});

describe("parseBlock", () => {
  it("parses event + JSON data and ignores comments", () => {
    expect(parseBlock('event: token\ndata: {"text":"hi"}')).toEqual({ event: "token", data: { text: "hi" } });
    expect(parseBlock(": ping")).toBeNull();
    expect(parseBlock("event: x\ndata: not json")).toBeNull();
  });
});

describe("StreamingOutput", () => {
  it("shows stop button + cursor while streaming and calls onStop", async () => {
    const onStop = vi.fn();
    render(<StreamingOutput state={st({ text: "Hello", running: true })} onStop={onStop} />);
    expect(screen.getByText("Hello")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /stop/i }));
    expect(onStop).toHaveBeenCalled();
    expect(screen.getByRole("status")).toHaveTextContent("streaming");
  });
  it("shows counters when done, an empty state and errors", () => {
    const { rerender } = render(
      <StreamingOutput
        state={st({ text: "x", stats: { tokens_in: 10, tokens_out: 5, ms: 1500, run_id: 1 } })}
        onStop={() => {}}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("10 tokens in · 5 tokens out · 1.5 s");
    expect(screen.queryByRole("button", { name: /stop/i })).toBeNull();
    rerender(<StreamingOutput state={st({})} onStop={() => {}} />);
    expect(screen.getByText(/press Run/i)).toBeInTheDocument();
    rerender(<StreamingOutput state={st({ error: "Ollama down" })} onStop={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Ollama down");
  });
});

describe("JsonViewer", () => {
  const base: ExtractResult = {
    data: {
      people: [
        { value: "Priya", evidence: "Priya will confirm", verified: true },
        { value: "Bob", evidence: "made up", verified: false },
      ],
      vendor: null,
    },
    valid: true,
    attempts: 2,
    raw: "",
    unverified: [{ path: "people[1]", value: "Bob" }],
    truncated: false,
    schema_name: "entities",
    run_id: 1,
  };
  it("marks verified and unverified values", () => {
    render(<JsonViewer result={base} />);
    expect(screen.getByText("valid JSON")).toBeInTheDocument();
    expect(screen.getByText("✔ verified")).toBeInTheDocument();
    expect(screen.getByText("⚠ unverified")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("1 value(s)");
    expect(screen.getByText("not found")).toBeInTheDocument();
  });
  it("shows the raw output when invalid", () => {
    render(
      <JsonViewer
        result={{ ...base, valid: false, data: null, raw: "garbage", errors: "no JSON object found" }}
      />,
    );
    expect(screen.getByText("invalid JSON")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("no JSON object found");
  });
});

describe("misc components", () => {
  it("ChunkSummaries renders one accordion per step and nothing when empty", () => {
    const { container, rerender } = render(<ChunkSummaries chunks={[]} />);
    expect(container).toBeEmptyDOMElement();
    rerender(
      <ChunkSummaries
        total={2}
        chunks={[
          { index: 1, total: 2, level: 1, text: "first" },
          { index: 2, total: 2, level: 1, text: "second" },
        ]}
      />,
    );
    expect(screen.getAllByText(/Part \d of 2/)).toHaveLength(2);
  });
  it("TaskSelector switches tasks and picks the matching prompt", async () => {
    const onTask = vi.fn();
    render(<TaskSelector task="summarize" onTask={onTask} opts={DEFAULT_OPTIONS} onOpts={() => {}} />);
    await userEvent.click(screen.getByRole("tab", { name: "extract" }));
    expect(onTask).toHaveBeenCalledWith("extract");
    expect(promptFor("summarize", { ...DEFAULT_OPTIONS, style: "bullets" })).toBe("summarize_bullets");
    expect(promptFor("transform", { ...DEFAULT_OPTIONS, action: "translate", lang: "en" })).toBe(
      "translate_ta_en",
    );
  });
  it("ParamsPanel reports slider changes", async () => {
    const onChange = vi.fn();
    render(
      <ParamsPanel
        params={{}}
        onChange={onChange}
        models={["a", "b"]}
        defaults={{ temperature: 0.3, max_tokens: 800 }}
      />,
    );
    await userEvent.selectOptions(screen.getByRole("combobox"), "b");
    expect(onChange).toHaveBeenCalledWith({ model: "b" });
  });
});
