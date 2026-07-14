import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, Expert, Job, Source, streamJob } from "../api";
import { ProgressBar, StatusChip } from "../components/ui";

export default function ExpertDetail() {
  const { name = "" } = useParams();
  const nav = useNavigate();
  const [expert, setExpert] = useState<Expert | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [urls, setUrls] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [err, setErr] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    api
      .expert(name)
      .then((d) => {
        setExpert(d.expert);
        setSources(d.sources);
      })
      .catch((e) => setErr(String(e)));
  }, [name]);
  useEffect(() => {
    load();
  }, [load]);

  const watch = useCallback(
    (jobId: string) => {
      streamJob(jobId, (j) => {
        setJob(j);
        if (j.status === "done" || j.status === "failed") {
          load();
          if (j.status === "done") setTimeout(() => setJob(null), 1500);
        }
      });
    },
    [load],
  );

  async function upload(files: File[]) {
    setErr("");
    if (!files.length && !urls.trim()) return;
    try {
      const { job_id } = await api.addSources(name, files, urls);
      setUrls("");
      watch(job_id);
    } catch (e) {
      setErr(String(e));
    }
  }

  async function reindex() {
    const { job_id } = await api.reindex(name);
    watch(job_id);
  }

  async function removeSource(sid: string) {
    await api.deleteSource(name, sid);
    load();
  }

  async function removeExpert() {
    if (!confirm(`Delete expert "${name}" and all its data?`)) return;
    await api.deleteExpert(name);
    nav("/");
  }

  if (!expert) return <div className="text-fg-muted">{err || "Loading…"}</div>;

  return (
    <div>
      <Link to="/" className="text-sm text-fg-muted hover:text-fg">
        ← Team
      </Link>
      <div className="mb-6 mt-2 flex items-start justify-between gap-4">
        <div>
          <h1 className="font-mono text-2xl font-semibold text-accent-ink">{expert.name}</h1>
          <p className="mt-1 max-w-xl text-sm text-fg-muted">{expert.description}</p>
          <div className="mt-2 flex gap-4 font-mono text-xs text-fg-faint">
            <span>{expert.n_sources} sources</span>
            <span>{expert.n_chunks.toLocaleString()} chunks</span>
          </div>
        </div>
        <div className="flex gap-2">
          <button className="btn" onClick={reindex} disabled={!sources.length}>
            Reindex
          </button>
          <button className="btn text-bad" onClick={removeExpert}>
            Delete
          </button>
        </div>
      </div>

      {err && <div className="mb-4 rounded-md bg-bad/10 px-3 py-2 text-sm text-bad">{err}</div>}

      {/* upload */}
      <div
        className={`card mb-4 border-dashed transition ${
          dragOver ? "border-accent-deep bg-accent/5" : ""
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          upload(Array.from(e.dataTransfer.files));
        }}
      >
        <div className="text-sm text-fg-muted">
          Drag files here (PDF / EPUB / MOBI / HTML / Markdown) or{" "}
          <button className="text-accent-ink underline" onClick={() => fileRef.current?.click()}>
            browse
          </button>
          .
        </div>
        <input
          ref={fileRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => upload(Array.from(e.target.files ?? []))}
        />
        <div className="mt-3 flex gap-2">
          <input
            className="input"
            placeholder="…or paste a URL and press Add"
            value={urls}
            onChange={(e) => setUrls(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && upload([])}
          />
          <button className="btn" onClick={() => upload([])} disabled={!urls.trim()}>
            Add URL
          </button>
        </div>
      </div>

      {/* live job */}
      {job && (
        <div className="card mb-4">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="font-mono text-fg-muted">{job.stage || job.status}</span>
            <StatusChip status={job.status} />
          </div>
          <ProgressBar value={job.progress} />
          {job.error && <div className="mt-2 text-sm text-bad">{job.error}</div>}
        </div>
      )}

      {/* sources */}
      <div className="card overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left">
              {["Title", "Format", "Chunks", "Status", ""].map((h) => (
                <th key={h} className="label px-4 py-3">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sources.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-fg-muted">
                  No sources yet — add material above.
                </td>
              </tr>
            ) : (
              sources.map((s) => (
                <tr key={s.source_id} className="border-b border-line/50 last:border-0">
                  <td className="px-4 py-3">
                    {s.title || "—"}
                    {s.error && <div className="text-xs text-bad">{s.error}</div>}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-fg-muted">{s.fmt}</td>
                  <td className="px-4 py-3 font-mono tabular-nums">{s.n_chunks}</td>
                  <td className="px-4 py-3">
                    <StatusChip status={s.status} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      className="text-xs text-fg-faint hover:text-bad"
                      onClick={() => removeSource(s.source_id)}
                    >
                      remove
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
