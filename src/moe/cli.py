"""``moe-build`` — the author-time Python CLI (extraction + compile). The user-facing umbrella
is the Node ``npx moe`` (see package.json); its ``build`` / ``scaffold`` subcommands shell out
to this. Everything here runs at author time; installation needs no Python."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table

from moe import render
from moe.knowledge import build_expert_knowledge
from moe.models import slugify
from moe.roster import load_roster

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
    console.print("Next: [bold]npx moe install[/] (or `npx skills add <repo>`)")


@app.command()
def scaffold(
    name: str = typer.Argument(..., help="New expert name"),
    description: str = typer.Option("", "--description", "-d"),
    root: str = typer.Option(".", "--root"),
):
    """Create experts/<name>/ (EXPERT.md + materials/) and add a roster entry to experts.yaml."""
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
        data["experts"].append(
            {
                "name": name,
                "description": description or f"TODO: describe what the {name} expert knows.",
                "materials": [],
                "tools": ["Read", "Grep", "Glob"],
            }
        )
        roster_path.write_text(yaml.safe_dump(data, sort_keys=False))
    console.print(
        f"[green]✓[/] scaffolded [bold]{slug}[/] → add material to "
        f"experts/{slug}/materials/, edit its description, then `npx moe build`."
    )


@app.command("list")
def list_experts(root: str = typer.Option(".", "--root")):
    """List the team roster."""
    roster = load_roster(Path(root).resolve() / "experts.yaml")
    table = Table("Expert", "Agent", "Sources", "Description")
    for e in roster.experts:
        desc = (e.description.strip()[:60] + "…") if len(e.description.strip()) > 61 else e.description.strip()
        table.add_row(e.name, e.agent_name, str(len(e.materials)), desc)
    console.print(table)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
