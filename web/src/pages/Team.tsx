import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Expert } from "../api";
import { Empty, Modal } from "../components/ui";

export default function Team() {
  const [experts, setExperts] = useState<Expert[] | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [err, setErr] = useState("");

  const load = () => api.experts().then(setExperts).catch((e) => setErr(String(e)));
  useEffect(() => {
    load();
  }, []);

  async function create() {
    setErr("");
    try {
      await api.createExpert(name, desc);
      setShowNew(false);
      setName("");
      setDesc("");
      load();
    } catch (e) {
      setErr(String(e));
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Expert team</h1>
          <p className="text-sm text-fg-muted">Domain knowledge bases the router chooses between.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowNew(true)}>
          + New expert
        </button>
      </div>

      {err && <div className="mb-4 rounded-md bg-bad/10 px-3 py-2 text-sm text-bad">{err}</div>}

      {experts === null ? (
        <div className="text-fg-muted">Loading…</div>
      ) : experts.length === 0 ? (
        <Empty>No experts yet. Create one, then add material to it.</Empty>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {experts.map((e) => (
            <Link key={e.name} to={`/experts/${e.name}`} className="card hover:border-accent-deep">
              <div className="font-mono text-sm font-semibold text-accent-ink">{e.name}</div>
              <p className="mt-1 line-clamp-2 min-h-[2.5rem] text-sm text-fg-muted">
                {e.description}
              </p>
              <div className="mt-3 flex gap-4 font-mono text-xs text-fg-faint">
                <span>{e.n_sources} sources</span>
                <span>{e.n_chunks.toLocaleString()} chunks</span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {showNew && (
        <Modal title="New expert" onClose={() => setShowNew(false)}>
          <div className="space-y-3">
            <div>
              <label className="label">Name</label>
              <input
                className="input mt-1"
                placeholder="cardiology"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div>
              <label className="label">Description (drives routing)</label>
              <textarea
                className="input mt-1 h-24 resize-none"
                placeholder="What this expert knows — used to route questions to it."
                value={desc}
                onChange={(e) => setDesc(e.target.value)}
              />
            </div>
            {err && <div className="text-sm text-bad">{err}</div>}
            <div className="flex justify-end gap-2 pt-1">
              <button className="btn" onClick={() => setShowNew(false)}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={create} disabled={!name || !desc}>
                Create
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
