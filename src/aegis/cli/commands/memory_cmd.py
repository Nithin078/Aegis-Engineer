"""`aegis memory` — list / show / forget / export / import repository memory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from aegis.config.loader import load_config
from aegis.memory.models import MemoryKind
from aegis.memory.store import MemoryStore

console = Console()

app = typer.Typer(
    name="memory",
    help="Repository / global memory (past fixes, failures, patterns).",
    no_args_is_help=True,
)


def _store(workspace: Path) -> MemoryStore:
    config = load_config()
    return MemoryStore(
        workspace,
        store_dir=config.memory.store_dir,
        global_enabled=config.memory.global_memory_enabled,
        max_entries_per_repo=config.memory.max_entries_per_repo,
    )


@app.command("list")
def memory_list(
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    kind: str | None = typer.Option(
        None,
        "--kind",
        "-k",
        help="Filter: solved|failure|pattern|preference|global|note",
    ),
    scope: str | None = typer.Option(None, "--scope", help="repo|global"),
    limit: int = typer.Option(50, "--limit", "-n"),
    as_json: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """List memory entries for a workspace (includes global by default)."""
    store = _store(workspace)
    entries = store.list_entries(kind=kind, scope=scope, limit=limit)
    if as_json:
        typer.echo(json.dumps([e.model_dump(mode="json") for e in entries], indent=2))
        return
    if not entries:
        console.print("[dim]No memory entries.[/dim]")
        return
    table = Table(title=f"Memory · {store.repo_id}")
    table.add_column("ID")
    table.add_column("Kind")
    table.add_column("Scope")
    table.add_column("Title")
    table.add_column("Created")
    for e in entries:
        table.add_row(
            e.id,
            e.kind.value,
            e.scope,
            (e.title or e.summary)[:50],
            e.created_at.isoformat()[:19],
        )
    console.print(table)


@app.command("show")
def memory_show(
    entry_id: str = typer.Argument(..., help="Memory entry id (mem_...)"),
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    as_json: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """Show a single memory entry."""
    store = _store(workspace)
    entry = store.get(entry_id)
    if not entry:
        console.print(f"[red]Not found:[/red] {entry_id}")
        raise typer.Exit(1)
    if as_json:
        typer.echo(json.dumps(entry.model_dump(mode="json"), indent=2))
        return
    console.print(f"[bold]{entry.id}[/bold]  {entry.kind.value}  ({entry.scope})")
    console.print(f"title: {entry.title}")
    console.print(f"summary: {entry.summary}")
    if entry.files:
        console.print(f"files: {', '.join(entry.files)}")
    if entry.issue_text:
        console.print("\n[dim]issue[/dim]")
        console.print(entry.issue_text[:2000])
    if entry.payload:
        console.print("\n[dim]payload[/dim]")
        console.print(json.dumps(entry.payload, indent=2)[:2000])


@app.command("query")
def memory_query(
    text: str = typer.Argument(..., help="Free-text similarity query"),
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    limit: int = typer.Option(5, "--limit", "-n"),
    as_json: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """Search memory for similar past issues/fixes."""
    store = _store(workspace)
    result = store.query(text, limit=limit)
    if as_json:
        typer.echo(json.dumps(result.model_dump(mode="json"), indent=2))
        return
    console.print(store.format_for_prompt(result) if result.entries else "[dim]No hits.[/dim]")


@app.command("forget")
def memory_forget(
    entry_id: str | None = typer.Argument(None, help="Entry id to remove"),
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    kind: str | None = typer.Option(None, "--kind", "-k"),
    all_repo: bool = typer.Option(False, "--all-repo", help="Clear all repo memory"),
    all_global: bool = typer.Option(False, "--all-global", help="Clear global memory"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Delete memory entries."""
    if not entry_id and not kind and not all_repo and not all_global:
        console.print("[red]Specify entry id, --kind, --all-repo, or --all-global[/red]")
        raise typer.Exit(1)
    if (all_repo or all_global) and not yes:
        console.print("[yellow]Refusing bulk delete without --yes[/yellow]")
        raise typer.Exit(1)
    store = _store(workspace)
    n = store.forget(entry_id=entry_id, kind=kind, all_repo=all_repo, all_global=all_global)
    console.print(f"Removed {n} entr{'y' if n == 1 else 'ies'}.")


@app.command("export")
def memory_export(
    output: Path = typer.Option(
        Path("aegis-memory-export.json"),
        "--output",
        "-o",
        help="Output JSON path",
    ),
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Export all memory (repo + global) to JSON."""
    store = _store(workspace)
    data = store.export_all()
    output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    console.print(f"Wrote {len(data.get('entries', []))} entries → {output}")


@app.command("import")
def memory_import(
    path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Import memory entries from a JSON export file."""
    raw: Any = json.loads(path.read_text(encoding="utf-8"))
    store = _store(workspace)
    n = store.import_entries(raw)
    console.print(f"Imported {n} entries into {store.repo_id}")


@app.command("add")
def memory_add(
    title: str = typer.Option(..., "--title", "-t"),
    summary: str = typer.Option("", "--summary", "-s"),
    kind: str = typer.Option("note", "--kind", "-k"),
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    global_scope: bool = typer.Option(False, "--global", help="Store in global memory"),
) -> None:
    """Manually add a memory note/pattern."""
    from aegis.memory.models import MemoryEntry

    store = _store(workspace)
    entry = MemoryEntry(
        kind=MemoryKind(kind),
        scope="global" if global_scope else "repo",
        title=title,
        summary=summary or title,
    )
    store.add(entry)
    console.print(f"Added {entry.id} ({entry.kind.value})")
