"""Link call edges to definition index; improve cross-module resolution."""

from __future__ import annotations

from aegis.intelligence.models import (
    CallEdge,
    CodeLocation,
    Confidence,
    IntelligenceIndex,
    SymbolKind,
)


def build_definition_index(symbols: list[CodeLocation]) -> dict[str, list[CodeLocation]]:
    """Map qualname and short name → definitions."""
    index: dict[str, list[CodeLocation]] = {}
    for s in symbols:
        if s.symbol_type is SymbolKind.MODULE:
            continue
        index.setdefault(s.qualname, []).append(s)
        index.setdefault(s.symbol_name, []).append(s)
        # also last two components: Class.method
        parts = s.qualname.split(".")
        if len(parts) >= 2:
            index.setdefault(".".join(parts[-2:]), []).append(s)
    return index


def refine_calls(
    calls: list[CallEdge],
    definitions: dict[str, list[CodeLocation]],
    module_bindings: dict[str, dict[str, str]],
) -> list[CallEdge]:
    """Second pass: attach better callees using the global definition index."""
    refined: list[CallEdge] = []
    for edge in calls:
        e = edge.model_copy()
        # If already high confidence and defined, keep
        if e.resolved and e.confidence is Confidence.HIGH and e.callee in definitions:
            refined.append(e)
            continue

        candidates = _lookup(e.callee, definitions)
        if not candidates and e.raw_callee:
            candidates = _lookup(e.raw_callee, definitions)

        # Try short name
        short = e.callee.split(".")[-1]
        if not candidates:
            candidates = definitions.get(short, [])

        if len(candidates) == 1:
            e.callee = candidates[0].qualname
            e.resolved = True
            if e.confidence is Confidence.LOW:
                e.confidence = Confidence.MEDIUM
            refined.append(e)
            continue

        if len(candidates) > 1:
            # Prefer same package as caller
            caller_mod = e.caller.rsplit(".", 1)[0] if "." in e.caller else ""
            same = [
                c
                for c in candidates
                if c.module == caller_mod
                or c.qualname.startswith(caller_mod + ".")
            ]
            if len(same) == 1:
                e.callee = same[0].qualname
                e.resolved = True
                e.confidence = Confidence.MEDIUM
            elif e.confidence is Confidence.HIGH and e.callee in definitions:
                e.resolved = True
            refined.append(e)
            continue

        # unresolved
        refined.append(e)
    return refined


def _lookup(name: str, definitions: dict[str, list[CodeLocation]]) -> list[CodeLocation]:
    if name in definitions:
        return definitions[name]
    # suffix match on qualnames
    hits: list[CodeLocation] = []
    for qn, locs in definitions.items():
        if qn.endswith("." + name) or qn == name:
            hits.extend(locs)
    return hits


def callers_of_symbol(
    index: IntelligenceIndex,
    name: str,
) -> list[dict]:
    """Return callers of a symbol with confidence, preferring resolved edges."""
    definitions = build_definition_index(index.symbols)
    # resolve target definition(s)
    targets = _lookup(name, definitions)
    target_qns = {t.qualname for t in targets} if targets else {name}
    # also accept short name and any edge pointing at name
    target_qns.add(name)
    if "." in name:
        target_qns.add(name.split(".")[-1])

    results: list[dict] = []
    seen: set[str] = set()
    for edge in index.calls:
        callee = edge.callee
        short = callee.split(".")[-1]
        match = (
            callee in target_qns
            or short == name
            or callee.endswith("." + name)
            or name.endswith("." + short)
            or edge.raw_callee == name
            or edge.raw_callee.endswith("." + name.split(".")[-1])
        )
        if not match:
            continue
        # If we have exact definitions, prefer edges that resolve to them
        if targets and edge.resolved and edge.callee not in {t.qualname for t in targets}:
            # still allow short-name high-confidence? skip weak mismatches
            if edge.confidence is Confidence.LOW:
                continue
        key = f"{edge.caller}|{edge.callee}|{edge.file}|{edge.line}"
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "caller": edge.caller,
                "callee": edge.callee,
                "raw_callee": edge.raw_callee,
                "file": edge.file,
                "line": edge.line,
                "confidence": edge.confidence.value,
                "resolved": edge.resolved,
            }
        )

    # sort: high confidence first
    order = {"high": 0, "medium": 1, "low": 2}
    results.sort(key=lambda r: (order.get(r["confidence"], 9), r["caller"], r["line"]))
    return results


def definitions_of(index: IntelligenceIndex, name: str) -> list[dict]:
    defs = build_definition_index(index.symbols)
    locs = _lookup(name, defs)
    # unique by qualname
    seen: set[str] = set()
    out: list[dict] = []
    for loc in locs:
        if loc.qualname in seen:
            continue
        seen.add(loc.qualname)
        out.append(loc.model_dump(mode="json"))
    return out
