"""NetworkX graphs for imports and calls."""

from __future__ import annotations

from typing import Any

import networkx as nx

from aegis.intelligence.models import CallEdge, ImportEdge


def build_import_graph(edges: list[ImportEdge]) -> nx.DiGraph:
    g: nx.DiGraph = nx.DiGraph()
    for e in edges:
        if not e.source_module or not e.target_module:
            continue
        g.add_edge(
            e.source_module,
            e.target_module,
            names=e.names,
            file=e.file,
            line=e.line,
            relative=e.is_relative,
        )
    return g


def build_call_graph(edges: list[CallEdge]) -> nx.DiGraph:
    g: nx.DiGraph = nx.DiGraph()
    for e in edges:
        g.add_edge(
            e.caller,
            e.callee,
            file=e.file,
            line=e.line,
            raw=e.raw_callee,
            confidence=e.confidence.value,
            resolved=e.resolved,
        )
    return g


def find_cycles(g: nx.DiGraph, *, limit: int = 50) -> list[list[str]]:
    cycles: list[list[str]] = []
    try:
        for cycle in nx.simple_cycles(g):
            cycles.append(cycle)
            if len(cycles) >= limit:
                break
    except nx.NetworkXNoCycle:
        return []
    return cycles


def importers_of(g: nx.DiGraph, module: str) -> list[str]:
    module = _match_node(g, module)
    if module is None:
        return []
    return sorted(g.predecessors(module))


def imports_of(g: nx.DiGraph, module: str) -> list[str]:
    module = _match_node(g, module)
    if module is None:
        return []
    return sorted(g.successors(module))


def callers_of(g: nx.DiGraph, name: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for u, v, data in g.edges(data=True):
        if _name_match(v, name) or _name_match(str(data.get("raw") or ""), name):
            results.append(
                {
                    "caller": u,
                    "callee": v,
                    "file": data.get("file"),
                    "line": data.get("line"),
                    "confidence": data.get("confidence", "low"),
                    "resolved": data.get("resolved", False),
                }
            )
    return results


def callees_of(g: nx.DiGraph, name: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for u, v, data in g.edges(data=True):
        if _name_match(u, name):
            results.append(
                {
                    "caller": u,
                    "callee": v,
                    "file": data.get("file"),
                    "line": data.get("line"),
                    "confidence": data.get("confidence", "low"),
                    "resolved": data.get("resolved", False),
                }
            )
    return results


def _match_node(g: nx.DiGraph, name: str) -> str | None:
    if name in g:
        return name
    matches = [n for n in g.nodes if n == name or str(n).endswith("." + name)]
    return matches[0] if matches else None


def _name_match(node: str, name: str) -> bool:
    if not node:
        return False
    if node == name or node.endswith("." + name):
        return True
    return node.split(".")[-1] == name.split(".")[-1] and (
        name in node or node.endswith(name) or node.split(".")[-1] == name
    )
