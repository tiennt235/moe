import { useEffect, useState } from "react";
import { api, Job } from "../api";
import { Empty, ProgressBar, StatusChip } from "../components/ui";

export default function Activity() {
  const [jobs, setJobs] = useState<Job[]>([]);

  useEffect(() => {
    const load = () => api.jobs().then(setJobs).catch(() => {});
    load();
    const t = setInterval(load, 1500); // poll while jobs may be running
    return () => clearInterval(t);
  }, []);

  return (
    <div>
      <h1 className="mb-1 text-2xl font-semibold">Activity</h1>
      <p className="mb-6 text-sm text-fg-muted">Ingestion jobs — running and recent.</p>
      {jobs.length === 0 ? (
        <Empty>No jobs yet.</Empty>
      ) : (
        <div className="space-y-2">
          {jobs.map((jb) => (
            <div key={jb.id} className="card">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-fg-faint">{jb.id}</span>
                  <span className="text-sm">
                    {jb.kind}
                    {jb.expert ? ` · ${jb.expert}` : ""}
                  </span>
                </div>
                <StatusChip status={jb.status} />
              </div>
              <div className="mt-2 font-mono text-xs text-fg-muted">{jb.stage}</div>
              {(jb.status === "running" || jb.status === "queued") && (
                <div className="mt-2">
                  <ProgressBar value={jb.progress} />
                </div>
              )}
              {jb.error && <div className="mt-2 text-sm text-bad">{jb.error}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
