import type { ChunkSummary } from "../api/client";

export function ChunkSummaries({ chunks, total }: { chunks: ChunkSummary[]; total?: number }) {
  if (chunks.length === 0) return null;
  return (
    <section className="card" aria-label="Chunk summaries">
      <h3 style={{ marginTop: 0 }}>
        Map-reduce steps {total ? `(${chunks.filter((c) => c.level === 1).length}/${total} chunks)` : ""}
      </h3>
      {chunks.map((c, i) => (
        <details key={i}>
          <summary>
            {c.level > 1 ? `Level ${c.level} · ` : ""}Part {c.index} of {c.total}
          </summary>
          <p>{c.text}</p>
        </details>
      ))}
    </section>
  );
}
