#!/usr/bin/env node
// moe — the user/agent-facing installer. Pure Node, no Python: it deploys the committed
// dist/ into a host (Claude Code / Codex / generic). Authoring (build/scaffold/list) is the
// separate Python dev path — see `npx github:tiennt235/moe help`.
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const TEXT_EXT = new Set([".md", ".toml", ".json", ".txt", ".yaml", ".yml"]);

// ---- tiny arg parser -----------------------------------------------------------------
function parseArgs(argv) {
  const opts = {}, positional = [];
  for (const a of argv) {
    if (a.startsWith("--")) {
      const [k, v] = a.slice(2).split("=");
      opts[k] = v === undefined ? true : v;
    } else positional.push(a);
  }
  return { opts, positional };
}

// ---- recursive copy with token substitution ------------------------------------------
function copyTree(src, dst, subs) {
  mkdirSync(dst, { recursive: true });
  for (const entry of readdirSync(src)) {
    const s = join(src, entry), d = join(dst, entry);
    if (statSync(s).isDirectory()) copyTree(s, d, subs);
    else {
      const ext = entry.slice(entry.lastIndexOf("."));
      if (TEXT_EXT.has(ext)) {
        let text = readFileSync(s, "utf8");
        for (const [k, v] of Object.entries(subs)) text = text.split(k).join(v);
        writeFileSync(d, text);
      } else {
        writeFileSync(d, readFileSync(s));
      }
    }
  }
}

// ---- host detection ------------------------------------------------------------------
// Detect which agents are present and where. Prefer a project-local harness folder over a
// global one, so `npx github:tiennt235/moe install` with no flags does the right thing.
function detectHosts(dir) {
  const home = homedir();
  const defs = [
    { provider: "claude", project: [join(dir, ".claude")], global: [join(home, ".claude")] },
    { provider: "codex", project: [join(dir, ".codex")], global: [join(home, ".codex")] },
    {
      provider: "agents",
      project: [join(dir, ".agents"), join(dir, ".pi")],
      global: [join(home, ".agents"), join(home, ".pi")],
    },
  ];
  const found = [];
  for (const d of defs) {
    const p = d.project.find(existsSync);
    const g = d.global.find(existsSync);
    if (p) found.push({ provider: d.provider, scope: "project", at: p });
    else if (g) found.push({ provider: d.provider, scope: "global", at: g });
  }
  return found;
}

// ---- providers -----------------------------------------------------------------------
// Each returns the copy operations for a given scope. Only the Claude build uses the
// {{MOE_ROOT}} placeholder (its subagents live apart from the skill/knowledge); Codex and
// generic builds reference knowledge relative to the skill dir, so need no substitution.
function planFor(provider, dir, scope) {
  const home = homedir();
  const distDir = join(REPO, "dist");
  const base = scope === "global" ? home : dir;
  if (provider === "claude") {
    const moeRoot = scope === "global" ? join(home, ".claude", "skills", "moe") : ".claude/skills/moe";
    return {
      dist: join(distDir, "claude-code"),
      copies: [{ from: join(distDir, "claude-code", ".claude"), to: join(base, ".claude") }],
      subs: { "{{MOE_ROOT}}": moeRoot },
      note: "skill → .claude/skills/moe · subagents → .claude/agents/moe-*",
    };
  }
  if (provider === "codex") {
    return {
      dist: join(distDir, "codex"),
      copies: [
        { from: join(distDir, "codex", ".agents"), to: join(base, ".agents") },
        { from: join(distDir, "codex", ".codex"), to: join(base, ".codex") },
      ],
      files: [{ from: join(distDir, "codex", "AGENTS.moe.md"), to: join(base, "AGENTS.moe.md") }],
      subs: {},
      note: "skill → .agents/skills/moe · agents → .codex/agents · paste AGENTS.moe.md into AGENTS.md",
    };
  }
  if (provider === "agents") {
    return {
      dist: join(distDir, "agents"),
      copies: [{ from: join(distDir, "agents", ".agents"), to: join(base, ".agents") }],
      subs: {},
      note: "generic skill → .agents/skills/moe (Pi & any Agent-Skills host)",
    };
  }
  throw new Error(`unknown provider: ${provider}`);
}

// ---- commands ------------------------------------------------------------------------
function cmdInstall(opts) {
  const dir = resolve(opts.dir || ".");
  const forcedScope = opts.scope === "global" || opts.scope === "project" ? opts.scope : null;

  // Zero-arg: auto-detect provider AND scope. Flags override.
  let targets;
  if (opts.providers) {
    targets = String(opts.providers).split(",").map((s) => s.trim()).filter(Boolean)
      .map((provider) => ({ provider, scope: forcedScope || "project" }));
  } else {
    targets = detectHosts(dir).map((t) => ({ ...t, scope: forcedScope || t.scope }));
    if (targets.length) {
      console.log("Detected: " + targets.map((t) => `${t.provider} → ${t.scope}`).join(", "));
    } else {
      targets = [{ provider: "claude", scope: forcedScope || "project" }];
      console.log("• no agent detected — defaulting to Claude Code (project). Override with --providers / --scope.");
    }
  }

  if (!existsSync(join(REPO, "dist"))) {
    console.error("✗ dist/ not found. Build it first (dev path): `uv run moe build`.");
    process.exit(1);
  }
  for (const { provider: p, scope } of targets) {
    const plan = planFor(p, dir, scope);
    if (!existsSync(plan.dist)) {
      console.log(`  ⚠ ${p}: no build at ${plan.dist} (skipped)`);
      continue;
    }
    for (const c of plan.copies) {
      if (!existsSync(c.from)) continue;
      copyTree(c.from, c.to, plan.subs);  // merges: overwrites moe's files, leaves others
    }
    for (const f of plan.files || []) {
      if (!existsSync(f.from)) continue;
      mkdirSync(dirname(f.to), { recursive: true });
      writeFileSync(f.to, readFileSync(f.from, "utf8"));
    }
    console.log(`  ✓ ${p}: ${plan.note}`);
  }
  console.log("Done. In your agent, try:  /moe ask \"…\"   (or /moe list)");
}

function authoringHint(sub) {
  const rest = sub === "scaffold" ? " <name> [-d \"…\"]" : "";
  console.log(`'moe ${sub}' is part of the Python authoring/dev path (it extracts material, so it needs Python).

Run it one of these ways from the repo:
  uv run moe ${sub}${rest}            # recommended (auto-installs deps)
  pip install -e . && moe ${sub}${rest}
  python -m moe ${sub}${rest}

npx is the user/agent-facing installer:
  npx github:tiennt235/moe install [--providers=…] [--scope=project|global]`);
}

function help() {
  console.log(`moe — a team of domain experts as agent skills

User / agent facing  (Node, no Python — auto-detects your agent(s) with no flags):
  npx github:tiennt235/moe install [--providers=claude,codex,agents] [--scope=project|global] [--dir=.] [--force]

Authoring / dev  (Python — extracts material, builds knowledge + dist/):
  uv run moe build                    rebuild knowledge + dist/
  uv run moe scaffold <name> [-d …]   add a new expert
  uv run moe list                     show the roster
  (or:  pip install -e . && moe <cmd>   ·   python -m moe <cmd>)

Install targets:
  claude  → .claude/skills/moe + .claude/agents/moe-*   (native subagents)
  codex   → .agents/skills/moe + .codex/agents + AGENTS.moe.md
  agents  → .agents/skills/moe                          (Pi & generic Agent-Skills hosts)`);
}

// ---- dispatch ------------------------------------------------------------------------
const [, , sub] = process.argv;
const { opts } = parseArgs(process.argv.slice(3));
switch (sub) {
  case "install": cmdInstall(opts); break;
  case "build":
  case "scaffold":
  case "list": authoringHint(sub); break;
  case undefined:
  case "help":
  case "--help":
  case "-h": help(); break;
  default:
    console.error(`unknown command: ${sub}\n`); help(); process.exit(1);
}
