import { ReactNode, useEffect, useState } from "react";
import { api, Health } from "../api";
import { StatusChip } from "../components/ui";

const RERANK_REGIONS = ["us-west-2", "ca-central-1", "eu-central-1", "ap-northeast-1"];

export default function Settings() {
  const [health, setHealth] = useState<Health | null>(null);
  const [exported, setExported] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    api.health().then(setHealth).catch((e) => setErr(String(e)));
  }, []);

  async function exportTeam() {
    setErr("");
    try {
      const { path } = await api.exportTeam();
      setExported(path);
    } catch (e) {
      setErr(String(e));
    }
  }

  const regionOk = health && RERANK_REGIONS.includes(health.rerank_region);

  return (
    <div>
      <h1 className="mb-1 text-2xl font-semibold">Settings & health</h1>
      <p className="mb-6 text-sm text-fg-muted">Connectivity, models, and team export.</p>

      {err && <div className="mb-4 rounded-md bg-bad/10 px-3 py-2 text-sm text-bad">{err}</div>}

      {health && (
        <div className="grid gap-3 sm:grid-cols-2">
          <Row label="Qdrant">
            <StatusChip status={health.qdrant === "ok" ? "ready" : "error"} />
          </Row>
          <Row label="Rerank region">
            <span className={regionOk ? "text-good" : "text-bad"}>
              {health.rerank_region} {regionOk ? "" : "(not a rerank region!)"}
            </span>
          </Row>
          <Row label="Embed model">
            <span className="font-mono text-xs">{health.embed_model}</span>
          </Row>
          <Row label="Rerank model">
            <span className="font-mono text-xs">{health.rerank_model}</span>
          </Row>
          <Row label="Experts">
            <span className="font-mono tabular-nums">{health.experts}</span>
          </Row>
        </div>
      )}

      <div className="card mt-6">
        <div className="mb-2 font-medium">Team portability</div>
        <p className="mb-3 text-sm text-fg-muted">
          Export the whole expert team as a portable bundle to move it to another machine.
        </p>
        <button className="btn" onClick={exportTeam}>
          Export team
        </button>
        {exported && (
          <div className="mt-3 font-mono text-xs text-good">exported → {exported}</div>
        )}
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="card flex items-center justify-between">
      <span className="label">{label}</span>
      <span className="text-sm">{children}</span>
    </div>
  );
}
