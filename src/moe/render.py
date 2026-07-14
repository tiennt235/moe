"""Multi-build compiler: canonical sources + roster → committed per-host outputs in ``dist/``.

One source, three builds — the impeccable.style mechanism, applied to an expert team:
  * ``dist/claude-code/`` — router skill + native subagents (``.claude/agents/moe-*.md``)
  * ``dist/codex/``       — router skill + custom-agent TOMLs + an AGENTS.md snippet
  * ``dist/agents/``      — generic Agent-Skills build (Pi/others): router + inline expert modes

Each build only differs in *how it delegates*; routing + citations are identical. The knowledge
folders are copied into every build so the deployed skill is self-contained.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from moe import __version__
from moe.knowledge import knowledge_dir
from moe.roster import ExpertSpec, Roster

# Placeholder the Node installer substitutes with the deployed skill root (so an expert can
# locate its knowledge regardless of project vs global scope). For skill-centric builds
# (Codex/generic) knowledge sits next to SKILL.md, so a relative path is used instead.
MOE_ROOT = "{{MOE_ROOT}}"

_TEMPLATES = Path(__file__).resolve().parent.parent.parent / "templates"
_SKILL_SRC = Path(__file__).resolve().parent.parent.parent / "skill" / "moe"


# --------------------------------------------------------------------------------------
# Shared rendering
# --------------------------------------------------------------------------------------
def _load(path: Path) -> str:
    return path.read_text()


def shipped_experts(roster: Roster) -> list[ExpertSpec]:
    """Experts that go into the end-user builds and the router roster (dev_only excluded)."""
    return [e for e in roster.experts if not e.dev_only]


def render_roster_list(experts: list[ExpertSpec]) -> str:
    return "\n".join(
        f"- **{e.name}** (`moe-{e.slug}`) — {e.description.strip()}" for e in experts
    )


_TEMPLATE_BY_KIND = {"knowledge": "expert-behavior.md", "builder": "builder-behavior.md"}


def expert_body(expert: ExpertSpec, knowledge_path: str, root: Path) -> str:
    tmpl = _load(_TEMPLATES / _TEMPLATE_BY_KIND[expert.kind])
    body = (
        tmpl.replace("{{NAME}}", expert.name)
        .replace("{{DESCRIPTION}}", expert.description.strip())
        .replace("{{KNOWLEDGE_PATH}}", knowledge_path)
    )
    extra = root / "experts" / expert.slug / "EXPERT.md"
    if extra.exists():
        body += "\n\n" + extra.read_text().strip() + "\n"
    return body


def router_skill(experts: list[ExpertSpec], delegation: str) -> str:
    body = _load(_SKILL_SRC / "SKILL.md")
    return body.replace("{{ROSTER}}", render_roster_list(experts)).replace(
        "{{DELEGATION}}", delegation
    )


def _skill_description(experts: list[ExpertSpec]) -> str:
    domains = ", ".join(e.name for e in experts)
    return (
        "Route a domain question to the right expert(s) and answer with citations. "
        f"Use for questions about: {domains}."
    )


# Shown in the `/moe ` autocomplete hint (Claude Code reads `argument-hint`).
SKILL_ARG_HINT = 'ask "<q>" | route "<q>" | list | add-expert | build'


def _skill_frontmatter(experts: list[ExpertSpec]) -> str:
    return _frontmatter(
        [
            ("name", "moe"),
            ("description", _skill_description(experts)),
            ("argument-hint", SKILL_ARG_HINT),
        ]
    )


def _frontmatter(fields: list[tuple[str, str | None]]) -> str:
    lines = ["---"]
    for k, v in fields:
        if v:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def _copy_knowledge(expert: ExpertSpec, root: Path, dest_knowledge: Path) -> None:
    src_dir = knowledge_dir(expert.slug, root)
    dst = dest_knowledge / expert.slug
    if dst.exists():
        shutil.rmtree(dst)
    if src_dir.exists():
        shutil.copytree(src_dir, dst)
    else:
        dst.mkdir(parents=True, exist_ok=True)


def _copy_commands(dest: Path) -> None:
    cmd_src = _SKILL_SRC / "commands"
    cmd_dst = dest / "commands"
    if cmd_dst.exists():
        shutil.rmtree(cmd_dst)
    shutil.copytree(cmd_src, cmd_dst)


def _reset(dirpath: Path) -> Path:
    if dirpath.exists():
        shutil.rmtree(dirpath)
    dirpath.mkdir(parents=True, exist_ok=True)
    return dirpath


# --------------------------------------------------------------------------------------
# Delegation prose (the only real per-host difference)
# --------------------------------------------------------------------------------------
CC_DELEGATION = (
    "   - Spawn the expert's subagent via the Agent/Task tool with "
    "`subagent_type: \"moe-<name>\"`, passing the question. Run several in parallel when\n"
    "     more than one expert applies; each subagent searches its own "
    "knowledge and returns cited findings."
)
CODEX_DELEGATION = (
    "   - Delegate to the expert's custom agent in `.codex/agents/moe-<name>.toml` "
    "(e.g. tell Codex to \"use the moe-<name> agent\"); up to 8 run in parallel. If subagents\n"
    "     are unavailable, adopt the expert's mode inline (read its knowledge "
    "folder and follow its instructions)."
)
GENERIC_DELEGATION = (
    "   - This host has no subagents: **adopt the selected expert's mode inline** — find it under "
    "\"## Experts\" below, follow its instructions, and search its knowledge folder yourself."
)


# --------------------------------------------------------------------------------------
# Builds
# --------------------------------------------------------------------------------------
def _build_claude_layout(experts: list[ExpertSpec], root: Path, base: Path) -> None:
    """The Claude Code layout (skill + native subagents). Shared by the shipped `claude-code`
    build (knowledge experts only) and the maintainer `dev` build (all experts)."""
    skill_dir = base / ".claude" / "skills" / "moe"
    agents_dir = base / ".claude" / "agents"
    skill_dir.mkdir(parents=True, exist_ok=True)
    agents_dir.mkdir(parents=True, exist_ok=True)

    (skill_dir / "SKILL.md").write_text(
        _skill_frontmatter(experts) + router_skill(experts, CC_DELEGATION)
    )
    _copy_commands(skill_dir)

    for e in experts:
        _copy_knowledge(e, root, skill_dir / "knowledge")
        kpath = f"{MOE_ROOT}/knowledge/{e.slug}"
        desc = e.description.strip().replace("\n", " ")
        if e.proactive:
            desc += f" Use proactively for {e.name} questions."
        fm = _frontmatter(
            [
                ("name", e.agent_name),
                ("description", desc),
                ("tools", ", ".join(e.tools)),
                ("model", e.model),
            ]
        )
        (agents_dir / f"{e.agent_name}.md").write_text(fm + expert_body(e, kpath, root))


def build_claude_code(roster: Roster, root: Path, dist: Path) -> None:
    _build_claude_layout(shipped_experts(roster), root, _reset(dist / "claude-code"))


def build_dev(roster: Roster, root: Path, dist: Path) -> None:
    """Maintainer build: the Claude Code layout with *all* experts (dev_only included), so the
    expert-builder is available as a real subagent in the repo. Installed with `--dev`."""
    _build_claude_layout(list(roster.experts), root, _reset(dist / "dev"))


def build_codex(roster: Roster, root: Path, dist: Path) -> None:
    base = _reset(dist / "codex")
    skill_dir = base / ".agents" / "skills" / "moe"
    agents_dir = base / ".codex" / "agents"
    skill_dir.mkdir(parents=True, exist_ok=True)
    agents_dir.mkdir(parents=True, exist_ok=True)

    experts = shipped_experts(roster)
    (skill_dir / "SKILL.md").write_text(
        _skill_frontmatter(experts) + router_skill(experts, CODEX_DELEGATION)
    )
    _copy_commands(skill_dir)

    for e in experts:
        _copy_knowledge(e, root, skill_dir / "knowledge")
        kpath = f"knowledge/{e.slug}"  # relative to the skill dir
        body = expert_body(e, kpath, root)
        # Best-effort custom-agent TOML. Keys may vary by Codex version; the skill + AGENTS.md
        # snippet are the reliable delegation path if this file is ignored.
        toml = [
            "# Codex custom agent (generated by `moe build`).",
            f'name = "{e.agent_name}"',
            f'description = {_toml_str(e.description.strip())}',
        ]
        if e.model:
            toml.append(f'model = "{e.model}"')
        toml.append(f"instructions = {_toml_multiline(body)}")
        (agents_dir / f"{e.agent_name}.toml").write_text("\n".join(toml) + "\n")

    (base / "AGENTS.moe.md").write_text(_agents_snippet(experts))


def build_generic(roster: Roster, root: Path, dist: Path) -> None:
    """Generic Agent-Skills build (Pi and any host without subagents). Everything lives in one
    skill dir; expert 'modes' are inlined so a single SKILL.md is self-contained."""
    base = _reset(dist / "agents")
    skill_dir = base / ".agents" / "skills" / "moe"
    skill_dir.mkdir(parents=True, exist_ok=True)

    experts = shipped_experts(roster)
    inline = ["", "## Experts", "", "Adopt the mode of the selected expert:"]
    for e in experts:
        _copy_knowledge(e, root, skill_dir / "knowledge")
        kpath = f"knowledge/{e.slug}"  # relative to this skill dir
        inline.append("")
        inline.append(f"### {e.name}  (`moe-{e.slug}`)")
        inline.append("")
        inline.append(expert_body(e, kpath, root).strip())

    (skill_dir / "SKILL.md").write_text(
        _skill_frontmatter(experts)
        + router_skill(experts, GENERIC_DELEGATION)
        + "\n"
        + "\n".join(inline)
        + "\n"
    )
    _copy_commands(skill_dir)


def _agents_snippet(experts: list[ExpertSpec]) -> str:
    return (
        "<!-- moe: paste into your AGENTS.md so Codex delegates automatically -->\n"
        "## moe experts (auto-delegation)\n\n"
        "When a question matches a domain below, delegate to the matching `moe-<name>` custom "
        "agent (or adopt its mode inline) and answer **with citations**. Experts:\n\n"
        + render_roster_list(experts)
        + "\n\nThe full protocol is in `.agents/skills/moe/SKILL.md`.\n"
    )


def _toml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def _toml_multiline(s: str) -> str:
    return '"""\n' + s.replace("\\", "\\\\").replace('"""', '\\"\\"\\"') + '\n"""'


# --------------------------------------------------------------------------------------
# Plugin manifest (Claude Code marketplace)
# --------------------------------------------------------------------------------------
def write_plugin_manifest(roster: Roster, root: Path) -> None:
    import json

    plugin_dir = root / "plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": "moe",
        "version": __version__,
        "description": _skill_description(shipped_experts(roster)),
        "author": "moe",
        "skills": ["./dist/claude-code/.claude/skills/moe"],
        "agents": ["./dist/claude-code/.claude/agents"],
    }
    (plugin_dir / "plugin.json").write_text(json.dumps(manifest, indent=2) + "\n")


# --------------------------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------------------------
def build_all(roster: Roster, root: Path) -> list[str]:
    dist = root / "dist"
    build_claude_code(roster, root, dist)
    build_codex(roster, root, dist)
    build_generic(roster, root, dist)
    build_dev(roster, root, dist)
    write_plugin_manifest(roster, root)
    return ["claude-code", "codex", "agents", "dev"]
