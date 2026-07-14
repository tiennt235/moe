import { NavLink, Outlet } from "react-router-dom";

const nav = [
  { to: "/", label: "Team", end: true },
  { to: "/activity", label: "Activity", end: false },
  { to: "/playground", label: "Playground", end: false },
  { to: "/settings", label: "Settings", end: false },
];

export default function App() {
  return (
    <div className="mx-auto flex min-h-screen max-w-6xl gap-6 px-6">
      <aside className="sticky top-0 flex h-screen w-48 shrink-0 flex-col gap-1 py-6">
        <div className="mb-6 px-2">
          <div className="font-mono text-lg font-bold text-accent-ink">moe</div>
          <div className="label">expert team</div>
        </div>
        {nav.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.end}
            className={({ isActive }) =>
              `rounded-md px-3 py-2 text-sm transition ${
                isActive
                  ? "bg-ink-3 text-accent-ink"
                  : "text-fg-muted hover:bg-ink-2 hover:text-fg"
              }`
            }
          >
            {n.label}
          </NavLink>
        ))}
      </aside>
      <main className="min-w-0 flex-1 py-6">
        <Outlet />
      </main>
    </div>
  );
}
