"""`aegis intelligence` — build and query the Repository Intelligence Engine."""

from __future__ import annotations

import json
import re
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from aegis.intelligence.engine import IntelligenceEngine

console = Console()

app = typer.Typer(
    name="intelligence",
    help="Build and query repository structure graphs (AST / imports / calls).",
    no_args_is_help=True,
)


def _engine(workspace: Path) -> IntelligenceEngine:
    return IntelligenceEngine(workspace)


@app.command("build")
def build_cmd(
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    incremental: bool = typer.Option(
        False,
        "--incremental",
        "-i",
        help="Reuse unchanged file hashes when possible",
    ),
    as_json: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """Parse Python sources and cache intelligence under .aegis/intelligence/."""
    eng = _engine(workspace)
    index = eng.build(incremental=incremental)
    stats = index.stats
    if as_json:
        typer.echo(json.dumps(stats.model_dump(mode="json"), indent=2))
        return
    table = Table(title="Intelligence Build", show_header=True, header_style="bold")
    table.add_column("Metric")
    table.add_column("Value")
    for k, v in stats.model_dump(mode="json").items():
        table.add_row(str(k), str(v))
    console.print(table)
    console.print(f"[dim]Cached under {workspace / '.aegis' / 'intelligence'}[/dim]")


@app.command("status")
def status_cmd(
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
    """Show whether intelligence is built and summary stats."""
    eng = _engine(workspace)
    st = eng.status()
    if as_json:
        typer.echo(json.dumps(st, indent=2, default=str))
        return
    if not st.get("built"):
        console.print("[yellow]Not built.[/yellow] Run: aegis intelligence build")
        raise typer.Exit(1)
    for k, v in st.items():
        console.print(f"[bold]{k}:[/bold] {v}")


@app.command("query")
def query_cmd(
    question: str = typer.Argument(..., help='e.g. "who calls greet"'),
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
    """Query call/import relationships with natural phrases."""
    eng = _engine(workspace)
    if not eng.index:
        eng.build()
    result = eng.query(question)
    if as_json:
        typer.echo(json.dumps(result, indent=2, default=str))
        return
    if result.get("error"):
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(1)
    console.print(f"[bold]type:[/bold] {result.get('type')}")
    if result.get("definitions"):
        console.print("[bold]definitions:[/bold]")
        for d in result["definitions"][:10]:
            console.print(
                f"  {d.get('qualname')}  {d.get('file')}:{d.get('line_start')}"
            )
    results = result.get("results") or []
    if not results:
        console.print("[dim]No results.[/dim]")
        return
    console.print(f"[bold]results ({len(results)}):[/bold]")
    if isinstance(results[0], dict):
        for item in results[:40]:
            conf = item.get("confidence", "")
            conf_s = f" [{conf}]" if conf else ""
            if "caller" in item:
                console.print(
                    f"  {item.get('caller')} → {item.get('callee')}{conf_s}  "
                    f"({item.get('file')}:{item.get('line')})"
                )
            else:
                console.print(f"  {item}")
    else:
        for item in results[:40]:
            console.print(f"- {item}")


@app.command("callers")
def callers_cmd(
    symbol: str = typer.Argument(..., help="Function/method name or qualname"),
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
    """List callers of a symbol (resolved when possible)."""
    eng = _engine(workspace)
    if not eng.index:
        eng.build()
    results = eng.callers(symbol)
    defs = eng.definitions(symbol)
    payload = {"symbol": symbol, "definitions": defs, "callers": results}
    if as_json:
        typer.echo(json.dumps(payload, indent=2, default=str))
        return
    if defs:
        console.print("[bold]definitions:[/bold]")
        for d in defs[:10]:
            console.print(f"  {d.get('qualname')} @ {d.get('file')}:{d.get('line_start')}")
    console.print(f"[bold]callers ({len(results)}):[/bold]")
    for item in results[:50]:
        conf = item.get("confidence", "")
        console.print(
            f"  [{conf}] {item.get('caller')} → {item.get('callee')}  "
            f"({item.get('file')}:{item.get('line')})"
        )


@app.command("impact")
def impact_cmd(
    target: str = typer.Argument(
        ...,
        help="File or file:line or file:start-end (e.g. src/app.py:10-20)",
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
    as_json: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """Estimate blast radius of changing a file or line range."""
    file_path = target
    line_start, line_end = 1, None
    m = re.match(r"^(.+):(\d+)(?:-(\d+))?$", target)
    if m:
        file_path = m.group(1)
        line_start = int(m.group(2))
        line_end = int(m.group(3)) if m.group(3) else line_start

    eng = _engine(workspace)
    result = eng.impact(file_path, line_start, line_end)
    if as_json:
        typer.echo(json.dumps(result, indent=2, default=str))
        return
    if result.get("error"):
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(1)
    console.print(f"[bold]risk:[/bold] {result.get('risk_level')}")
    console.print(f"[bold]symbols:[/bold] {len(result.get('symbols') or [])}")
    console.print(f"[bold]callers:[/bold] {len(result.get('callers') or [])}")
    console.print(f"[bold]importers:[/bold] {result.get('importers')}")
    for c in (result.get("callers") or [])[:15]:
        console.print(f"  {c}")


@app.command("search")
def search_cmd(
    text: str = typer.Argument(..., help="Natural language or keyword search"),
    workspace: Path = typer.Option(
        Path("."),
        "--workspace",
        "-w",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    limit: int = typer.Option(20, "--limit", "-n"),
    keyword_only: bool = typer.Option(
        False,
        "--keyword",
        help="Keyword-only (skip hybrid TF-IDF)",
    ),
    as_json: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """Hybrid search over symbols (semantic TF-IDF + keywords + graph)."""
    eng = _engine(workspace)
    if not eng.index:
        eng.build()
    hits = (
        eng.search(text, limit=limit)
        if keyword_only
        else eng.hybrid_search(text, limit=limit)
    )
    if as_json:
        typer.echo(json.dumps(hits, indent=2, default=str))
        return
    if not hits:
        console.print("[dim]No matches. Build first if needed.[/dim]")
        return
    for h in hits:
        src = h.get("source") or ""
        console.print(
            f"[bold]{h.get('qualname')}[/bold]  "
            f"score={h.get('score')}  {src}  "
            f"{h.get('file')}:{h.get('line_start')}"
        )


@app.command("graph")
def graph_cmd(
    graph_type: str = typer.Option(
        "import",
        "--type",
        "-t",
        help="import | call | class | dependency",
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
    as_json: bool = typer.Option(False, "--json", "-j"),
) -> None:
    """Summarize import, call, class, or dependency graph."""
    if graph_type not in {"import", "call", "class", "dependency"}:
        console.print("[red]--type must be import|call|class|dependency[/red]")
        raise typer.Exit(2)
    eng = _engine(workspace)
    if not eng.index:
        eng.build()
    result = eng.graph_summary(graph_type)
    if as_json:
        typer.echo(json.dumps(result, indent=2, default=str))
        return
    if result.get("error"):
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(1)
    console.print(
        f"[bold]{graph_type} graph[/bold]: "
        f"{result.get('nodes')} nodes, {result.get('edges')} edges"
    )
    for e in (result.get("sample_edges") or [])[:20]:
        console.print(f"  {e.get('from')} → {e.get('to')}")
    if graph_type == "dependency" and result.get("packages"):
        for p in (result.get("packages") or [])[:15]:
            console.print(f"  {p.get('name')} {p.get('spec') or ''} ({p.get('source')})")


@app.command("deps")
def deps_cmd(
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
    """List external dependencies and which modules import them."""
    eng = _engine(workspace)
    if not eng.index:
        eng.build()
    result = eng.dependencies()
    if as_json:
        typer.echo(json.dumps(result, indent=2, default=str))
        return
    for p in result.get("packages") or []:
        name = p.get("name")
        imps = (result.get("importers") or {}).get(name, [])
        console.print(
            f"[bold]{name}[/bold] {p.get('spec') or ''}  "
            f"importers={len(imps)}  ({p.get('source')})"
        )
