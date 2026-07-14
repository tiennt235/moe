#!/usr/bin/env node
// moe — umbrella CLI. `install` is pure Node (deploys the committed dist/ into a host).
// `build` / `scaffold` / `list` shell out to the Python author-time builder (moe.cli).
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

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
function detectProviders(dir) {
  const home = homedir();
  const found = [];
  if (existsSync(join(home, ".claude")) || existsSync(join(dir, ".claude"))) found.push("claude");
  if (existsSync(join(home, ".codex")) || existsSync(join(dir, ".codex"))) found.push("codex");
  if (
    existsSync(join(home, ".agents")) || existsSync(join(dir, ".agents")) ||
    existsSync(join(home, ".pi")) || existsSync(join(dir, ".pi"))
  ) found.push("agents");
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
  const scope = opts.scope === "global" ? "global" : "project";
  let providers = opts.providers ? String(opts.providers).split(",").map((s) => s.trim()) : detectProviders(dir);
  if (!providers.length) {
    providers = ["claude"];
    console.log("• no host detected — defaulting to Claude Code. Use --providers=claude,codex,agents to choose.");
  }
  if (!existsSync(join(REPO, "dist"))) {
    console.error("✗ dist/ not found. Run `npx moe build` first.");
    process.exit(1);
  }
  console.log(`Installing moe → providers: ${providers.join(", ")} · scope: ${scope}`);
  for (const p of providers) {
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

function pythonBuildArgs(sub, rest) {
  // Prefer `uv run` (auto-syncs deps from pyproject); fall back to python3 with PYTHONPATH.
  const uv = spawnSync("uv", ["--version"], { stdio: "ignore" });
  if (uv.status === 0) {
    return { cmd: "uv", args: ["run", "--project", REPO, "python", "-m", "moe", sub, ...rest] };
  }
  return {
    cmd: "python3",
    args: ["-m", "moe", sub, ...rest],
    env: { ...process.env, PYTHONPATH: join(REPO, "src") },
  };
}

function shellPython(sub, rest) {
  const { cmd, args, env } = pythonBuildArgs(sub, rest);
  const r = spawnSync(cmd, args, { stdio: "inherit", cwd: REPO, env: env || process.env });
  if (r.error || r.status !== 0) {
    console.error(
      `✗ '${sub}' needs the Python builder. Install uv (https://astral.sh/uv) or run:\n` +
      `    pip install -e .  &&  python -m moe ${sub}`
    );
    process.exit(r.status || 1);
  }
}

function help() {
  console.log(`moe — a team of domain experts as agent skills

Usage:
  npx moe install [--providers=claude,codex,agents] [--scope=project|global] [--dir=.] [--force]
  npx moe build                      rebuild knowledge + dist (needs Python)
  npx moe scaffold <name> [-d ...]   add a new expert
  npx moe list                       show the roster

Hosts:
  claude  → .claude/skills/moe + .claude/agents/moe-*   (native subagents)
  codex   → .agents/skills/moe + .codex/agents + AGENTS.moe.md
  agents  → .agents/skills/moe                          (Pi & generic Agent-Skills hosts)`);
}

// ---- dispatch ------------------------------------------------------------------------
const [, , sub, ...rest] = process.argv;
const { opts, positional } = parseArgs(rest);
switch (sub) {
  case "install": cmdInstall(opts); break;
  case "build": shellPython("build", rest); break;
  case "scaffold": shellPython("scaffold", positional.concat(rest.filter((a) => a.startsWith("-")))); break;
  case "list": shellPython("list", rest); break;
  case undefined:
  case "help":
  case "--help":
  case "-h": help(); break;
  default:
    console.error(`unknown command: ${sub}\n`); help(); process.exit(1);
}
