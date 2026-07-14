import { ReactNode, useEffect } from "react";

export function StatusChip({ status }: { status: string }) {
  const map: Record<string, string> = {
    ready: "text-good bg-good/10",
    done: "text-good bg-good/10",
    ingesting: "text-accent-ink bg-accent/10",
    running: "text-accent-ink bg-accent/10",
    queued: "text-fg-muted bg-line/40",
    pending: "text-fg-muted bg-line/40",
    error: "text-bad bg-bad/10",
    failed: "text-bad bg-bad/10",
  };
  return <span className={`chip ${map[status] ?? "text-fg-muted bg-line/40"}`}>{status}</span>;
}

export function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded bg-line">
      <div
        className="h-full bg-accent-deep transition-all"
        style={{ width: `${Math.round(value * 100)}%` }}
      />
    </div>
  );
}

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-xl border border-line bg-ink-2 p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-4 text-lg font-semibold">{title}</h2>
        {children}
      </div>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-line-2 p-10 text-center text-fg-muted">
      {children}
    </div>
  );
}
