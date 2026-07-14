"""``moe-ingest`` — CLI mirror of the dashboard, for scripting and CI. Same core, same
SQLite registry, so the two surfaces never diverge."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

from moe import service
from moe.models import ChunkParams

app = typer.Typer(help="Manage the mixture-of-domain-experts knowledge base.", no_args_is_help=True)
console = Console()


@app.command("create-expert")
def create_expert(
    name: str = typer.Option(..., "--name", "-n"),
    description: str = typer.Option(..., "--description", "-d"),
    contextual: Optional[bool] = typer.Option(None, "--contextual/--no-contextual"),
    target_tokens: Optional[int] = typer.Option(None, "--target-tokens"),
):
    """Create (or update) an expert and its Qdrant collection."""
    chunk = ChunkParams(contextual=contextual, target_tokens=target_tokens)
    expert = service.ensure_expert(name, description, chunk)
    console.print(f"[green]✓[/] expert [bold]{expert.name}[/] ready (collection {expert.collection})")


@app.command()
def add(
    expert: str = typer.Option(..., "--expert", "-e"),
    path: list[str] = typer.Option([], "--path", "-p", help="File path(s)"),
    url: list[str] = typer.Option([], "--url", "-u", help="URL(s)"),
    directory: Optional[str] = typer.Option(None, "--dir", help="Ingest a whole folder"),
    force: bool = typer.Option(False, "--force", help="Re-ingest even if unchanged"),
):
    """Add material to an expert (files, URLs, or a directory)."""
    items: list[service.Item] = []
    items += [service.item_from_path(p) for p in path]
    items += [service.item_from_url(u) for u in url]
    if directory:
        items += service.items_from_dir(directory)
    if not items:
        raise typer.BadParameter("provide --path, --url, or --dir")

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("starting", total=100)

        def update(stage: str, frac: float) -> None:
            progress.update(task, description=stage[:60], completed=frac * 100)

        sources = service.ingest_items(expert, items, force=force, update=update)
    console.print(f"[green]✓[/] ingested {len(sources)} source(s) into [bold]{expert}[/]")


@app.command("list")
def list_experts():
    """List experts with source and chunk counts."""
    table = Table("Expert", "Description", "Sources", "Chunks", "Updated")
    for e in service.list_experts():
        table.add_row(
            e.name,
            (e.description[:48] + "…") if len(e.description) > 49 else e.description,
            str(e.n_sources),
            str(e.n_chunks),
            e.updated_at.strftime("%Y-%m-%d %H:%M") if e.updated_at else "—",
        )
    console.print(table)


@app.command()
def sources(expert: str = typer.Option(..., "--expert", "-e")):
    """List an expert's ingested sources."""
    table = Table("Source ID", "Title", "Format", "Chunks", "Status")
    for s in service.list_sources(expert):
        table.add_row(s.source_id, s.title or "—", s.fmt.value, str(s.n_chunks), s.status.value)
    console.print(table)


@app.command()
def remove(
    expert: str = typer.Option(..., "--expert", "-e"),
    source: str = typer.Option(..., "--source", "-s"),
):
    """Remove a single source from an expert."""
    service.delete_source(expert, source)
    console.print(f"[green]✓[/] removed {source}")


@app.command()
def reindex(expert: str = typer.Option(..., "--expert", "-e")):
    """Re-ingest all of an expert's stored sources."""
    items = [
        service.item_from_path(s.origin, title=s.title)
        for s in service.list_sources(expert)
    ]
    with Progress(
        TextColumn("{task.description}"), BarColumn(), TextColumn("{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("reindexing", total=100)
        service.ingest_items(
            expert, items, force=True,
            update=lambda stage, frac: progress.update(task, description=stage[:60], completed=frac * 100),
        )
    console.print(f"[green]✓[/] reindexed [bold]{expert}[/]")


@app.command()
def drop(
    expert: str = typer.Option(..., "--expert", "-e"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete an expert, its collection, and its registry records."""
    if not yes:
        typer.confirm(f"Delete expert '{expert}' and all its data?", abort=True)
    service.delete_expert(expert)
    console.print(f"[green]✓[/] dropped [bold]{expert}[/]")


@app.command()
def doctor():
    """Preflight: check Qdrant + Bedrock connectivity and region."""
    from moe.clients.bedrock import get_bedrock
    from moe.clients.qdrant import get_kb
    from moe.config import RERANK_REGIONS, get_settings

    s = get_settings()
    console.print(f"[bold]Qdrant[/] {s.qdrant_url}: {get_kb().check()}")
    region = s.region_for("rerank")
    ok = "[green]ok[/]" if region in RERANK_REGIONS else "[red]NOT a rerank region[/]"
    console.print(f"[bold]Rerank region[/] {region}: {ok}")
    console.print("[bold]Bedrock:[/]")
    for svc, status in get_bedrock().check().items():
        mark = "[green]✓[/]" if status == "ok" else "[red]✗[/]"
        console.print(f"  {mark} {svc}: {status}")


@app.command()
def sync():
    """Rebuild the local registry from Qdrant + experts.yaml (same-cluster handoff)."""
    from moe import portability

    n = portability.sync_from_qdrant()
    console.print(f"[green]✓[/] synced {n} expert(s) from Qdrant")


@app.command("export")
def export_team(
    out: str = typer.Option("team.tar.zst", "--out", "-o"),
    experts: list[str] = typer.Option([], "--experts"),
    with_materials: bool = typer.Option(False, "--with-materials"),
    with_snapshots: bool = typer.Option(False, "--with-snapshots"),
):
    """Export the expert team to a portable bundle."""
    from moe import portability

    portability.export_team(
        out, experts=experts or None, with_materials=with_materials,
        with_snapshots=with_snapshots,
    )
    console.print(f"[green]✓[/] exported team to {out}")


@app.command("import")
def import_team(
    bundle: str = typer.Argument(...),
    restore_snapshots: bool = typer.Option(False, "--restore-snapshots"),
    reingest: bool = typer.Option(False, "--reingest"),
    experts: list[str] = typer.Option([], "--experts"),
):
    """Import an expert team bundle into this machine's Qdrant + registry."""
    from moe import portability

    portability.import_team(
        bundle, restore_snapshots=restore_snapshots, reingest=reingest,
        experts=experts or None,
    )
    console.print(f"[green]✓[/] imported team from {bundle}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
