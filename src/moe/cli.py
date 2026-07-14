"""``moe`` — the author-time Python CLI (extraction + compile): build, scaffold, list. Run via
``uv run moe <cmd>``, ``python -m moe <cmd>``, or ``pip install -e . && moe <cmd>``. The
user/agent-facing installer is the Node ``npx github:tiennt235/moe install`` (see package.json)
and needs no Python. Everything here runs at author time."""

from __future__ import annotations

from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

from moe import render
from moe.knowledge import build_expert_knowledge
from moe.models import slugify
from moe.roster import BUILDER_TOOLS, DEFAULT_TOOLS, load_roster

app = typer.Typer(help="moe — build a distributable team of domain experts.", no_args_is_help=True)
console = Console()


@app.command()
def build(root: str = typer.Option(".", "--root", help="Repo root (holds experts.yaml)")):
    """Extract materials → knowledge (+ INDEX), then compile per-host builds into dist/."""
    rootp = Path(root).resolve()
    roster = load_roster(rootp / "experts.yaml")
    if not roster.experts:
        raise typer.BadParameter("experts.yaml has no experts")

    console.print(f"[bold]Building knowledge[/] for {len(roster.experts)} expert(s)…")
    for e in roster.experts:
        summary = build_expert_knowledge(e, rootp)
        console.print(
            f"  [green]✓[/] {summary['expert']}: "
            f"{summary['sources']} source(s), {summary['sections']} section(s)"
        )

    builds = render.build_all(roster, rootp)
    console.print(f"[green]✓[/] compiled dist/: {', '.join(builds)} (+ plugin/plugin.json)")
    console.print(
        "Next: [bold]npx github:tiennt235/moe install[/] (or `npx skills add tiennt235/moe`). "
        "Maintainers: [bold]npx github:tiennt235/moe install --dev[/] for the dev build "
        "(all experts, incl. the expert-builder)."
    )


@app.command()
def scaffold(
    name: str = typer.Argument(..., help="New expert name"),
    description: str = typer.Option("", "--description", "-d"),
    kind: str = typer.Option(
        "knowledge", "--kind", help="knowledge (default) or builder (a dev-only meta-expert)"
    ),
    root: str = typer.Option(".", "--root"),
):
    """Create experts/<name>/ (EXPERT.md + materials/) and add a roster entry to experts.yaml."""
    if kind not in ("knowledge", "builder"):
        raise typer.BadParameter("--kind must be 'knowledge' or 'builder'")
    rootp = Path(root).resolve()
    slug = slugify(name)
    edir = rootp / "experts" / slug
    (edir / "materials").mkdir(parents=True, exist_ok=True)
    expert_md = edir / "EXPERT.md"
    if not expert_md.exists():
        expert_md.write_text(f"# Additional guidance — {name}\n\n- (optional domain notes)\n")

    roster_path = rootp / "experts.yaml"
    data = yaml.safe_load(roster_path.read_text()) if roster_path.exists() else {"experts": []}
    data.setdefault("experts", [])
    if any(slugify(e.get("name", "")) == slug for e in data["experts"]):
        console.print(f"[yellow]•[/] expert [bold]{name}[/] already in roster")
    else:
        entry = {
            "name": name,
            "description": description or f"TODO: describe what the {name} expert knows.",
            "materials": [],
            "tools": list(BUILDER_TOOLS if kind == "builder" else DEFAULT_TOOLS),
        }
        if kind == "builder":
            # A builder is a procedural, dev-only meta-expert (needs the repo + Python to run).
            entry["kind"] = "builder"
            entry["dev_only"] = True
        data["experts"].append(entry)
        roster_path.write_text(yaml.safe_dump(data, sort_keys=False))
    console.print(
        f"[green]✓[/] scaffolded [bold]{slug}[/] → add material to "
        f"experts/{slug}/materials/, edit its description, then `uv run moe build`."
    )


@app.command("list")
def list_experts(root: str = typer.Option(".", "--root")):
    """List the team roster."""
    roster = load_roster(Path(root).resolve() / "experts.yaml")
    table = Table("Expert", "Agent", "Sources", "Description")
    for e in roster.experts:
        d = e.description.strip()
        desc = (d[:60] + "…") if len(d) > 61 else d
        table.add_row(e.name, e.agent_name, str(len(e.materials)), desc)
    console.print(table)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
