import { useEffect, useState } from "react";
import { api, Expert, RetrievalResult } from "../api";

export default function Playground() {
  const [experts, setExperts] = useState<Expert[]>([]);
  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState(8);
  const [synth, setSynth] = useState(false);
  const [pinned, setPinned] = useState<string[]>([]);
  const [result, setResult] = useState<RetrievalResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.experts().then(setExperts).catch(() => {});
  }, []);

  async function ask() {
    if (!question.trim()) return;
    setLoading(true);
    setErr("");
    setResult(null);
    try {
      setResult(
        await api.query({
          question,
          top_k: topK,
          synthesize: synth,
          experts: pinned.length ? pinned : undefined,
        }),
      );
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  const toggle = (n: string) =>
    setPinned((p) => (p.includes(n) ? p.filter((x) => x !== n) : [...p, n]));

  return (
    <div>
      <h1 className="mb-1 text-2xl font-semibold">Playground</h1>
      <p className="mb-6 text-sm text-fg-muted">
        Ask a question — see which experts route, the passages, and their citations.
      </p>

      <div className="card mb-4">
        <textarea
          className="input h-20 resize-none"
          placeholder="Ask the expert team…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => (e.metaKey || e.ctrlKey) && e.key === "Enter" && ask()}
        />
        <div className="mt-3 flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-fg-muted">
            top_k
            <input
              type="number"
              min={1}
              max={20}
              className="input w-16 py-1"
              value={topK}
              onChange={(e) => setTopK(+e.target.value)}
            />
          </label>
          <label className="flex items-center gap-2 text-sm text-fg-muted">
            <input type="checkbox" checked={synth} onChange={(e) => setSynth(e.target.checked)} />
            synthesize answer
          </label>
          <div className="flex flex-wrap gap-1">
            {experts.map((e) => (
              <button
                key={e.name}
                onClick={() => toggle(e.name)}
                className={`chip ${
                  pinned.includes(e.name)
                    ? "bg-accent-deep text-white"
                    : "bg-line/40 text-fg-muted"
                }`}
              >
                {e.name}
              </button>
            ))}
          </div>
          <button className="btn btn-primary ml-auto" onClick={ask} disabled={loading}>
            {loading ? "Thinking…" : "Ask"}
          </button>
        </div>
      </div>

      {err && <div className="mb-4 rounded-md bg-bad/10 px-3 py-2 text-sm text-bad">{err}</div>}

      {result && (
        <div className="space-y-4">
          <div className="text-sm text-fg-muted">
            Routed to:{" "}
            {result.experts_selected.map((e) => (
              <span key={e} className="chip ml-1 bg-accent/10 text-accent-ink">
                {e}
              </span>
            ))}
          </div>

          {result.answer && (
            <div className="card whitespace-pre-wrap text-sm leading-relaxed">{result.answer}</div>
          )}

          <div className="space-y-3">
            {result.passages.map((p, i) => (
              <div key={p.chunk_id} className="card">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="font-mono text-accent-ink">[{i + 1}]</span>
                    <span className="font-medium">{p.citation.title}</span>
                    {p.citation.location && (
                      <span className="text-fg-faint">· {p.citation.location}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 font-mono text-xs text-fg-faint">
                    <span className="chip bg-line/40 text-fg-muted">{p.expert}</span>
                    {p.rerank_score != null && <span>rr {p.rerank_score.toFixed(3)}</span>}
                  </div>
                </div>
                <p className="text-sm leading-relaxed text-fg-muted">{p.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
