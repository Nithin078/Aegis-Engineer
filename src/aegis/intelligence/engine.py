"""Repository Intelligence Engine — build, query, impact, search."""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegis.intelligence.class_graph import bases_of, extract_classes, subclasses_of
from aegis.intelligence.dependencies import (
    load_external_deps,
    map_external_importers,
)
from aegis.intelligence.embeddings import build_symbol_tfidf, hybrid_search
from aegis.intelligence.graphs import (
    build_call_graph,
    build_import_graph,
    callees_of,
    find_cycles,
    importers_of,
    imports_of,
)
from aegis.intelligence.models import (
    CodeLocation,
    ExternalDep,
    InheritanceEdge,
    IntelligenceIndex,
    IntelligenceStats,
    SymbolKind,
)
from aegis.intelligence.python_ast import (
    file_hash,
    iter_python_files,
    parse_python_file,
)
from aegis.intelligence.resolve import (
    build_definition_index,
    callers_of_symbol,
    definitions_of,
    refine_calls,
)
from aegis.intelligence.store import load_index, save_index


class IntelligenceEngine:
    """Structural + resolved call/import/class/deps intelligence."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.index: IntelligenceIndex | None = load_index(self.root)
        self._import_g = None
        self._call_g = None
        self._definitions: dict[str, list[CodeLocation]] = {}
        self._tfidf = None
        if self.index:
            self._rebuild_graphs()

    def _rebuild_graphs(self) -> None:
        assert self.index is not None
        self._import_g = build_import_graph(self.index.imports)
        self._call_g = build_call_graph(self.index.calls)
        self._definitions = build_definition_index(self.index.symbols)
        self._tfidf = build_symbol_tfidf(self.index.symbols)

    def build(self, *, incremental: bool = False) -> IntelligenceIndex:
        _ = incremental  # reserved
        started = time.perf_counter()
        files = iter_python_files(self.root)
        symbols: list[CodeLocation] = []
        imports = []
        calls = []
        hashes: dict[str, str] = {}
        module_bindings: dict[str, dict[str, str]] = {}

        for path in files:
            rel = path.relative_to(self.root).as_posix()
            hashes[rel] = file_hash(path)
            syms, imps, cls, bindings = parse_python_file(path, self.root)
            symbols.extend(syms)
            imports.extend(imps)
            calls.extend(cls)
            mod = next((s.module for s in syms if s.module), "")
            if mod and bindings:
                module_bindings[mod] = bindings

        definitions = build_definition_index(symbols)
        calls = refine_calls(calls, definitions, module_bindings)

        class_infos, inheritance = extract_classes(self.root)
        # store inheritance as models (already InheritanceEdge)
        inh_edges: list[InheritanceEdge] = list(inheritance)

        ext_raw = load_external_deps(self.root)
        ext_deps = [
            ExternalDep(name=d.name, spec=d.spec, source=d.source) for d in ext_raw
        ]
        ext_names = {d.name for d in ext_deps}
        ext_importers = map_external_importers(imports, ext_names)

        functions = sum(
            1
            for s in symbols
            if s.symbol_type
            in (SymbolKind.FUNCTION, SymbolKind.ASYNC_FUNCTION, SymbolKind.METHOD)
        )
        classes = sum(1 for s in symbols if s.symbol_type is SymbolKind.CLASS)
        modules = {s.module for s in symbols if s.module}
        resolved = sum(1 for c in calls if c.resolved)

        import_g = build_import_graph(imports)
        cycles = find_cycles(import_g)
        elapsed = (time.perf_counter() - started) * 1000

        stats = IntelligenceStats(
            files=len(files),
            symbols=len(symbols),
            functions=functions,
            classes=classes,
            import_edges=len(imports),
            call_edges=len(calls),
            resolved_calls=resolved,
            inheritance_edges=len(inh_edges),
            external_deps=len(ext_deps),
            modules=len(modules),
            cycles=len(cycles),
            build_ms=elapsed,
            built_at=datetime.now(UTC),
            root=str(self.root),
        )
        self.index = IntelligenceIndex(
            root=str(self.root),
            file_hashes=hashes,
            symbols=symbols,
            imports=imports,
            calls=calls,
            module_bindings=module_bindings,
            inheritance=inh_edges,
            class_infos=class_infos,
            external_deps=ext_deps,
            external_importers=ext_importers,
            stats=stats,
        )
        self._rebuild_graphs()
        save_index(self.root, self.index)
        return self.index

    def status(self) -> dict[str, Any]:
        if not self.index:
            return {"built": False, "root": str(self.root)}
        return {"built": True, **self.index.to_summary()}

    def ensure_built(self) -> bool:
        if self.index:
            return True
        self.build()
        return True

    def find_symbol(self, name: str) -> list[CodeLocation]:
        if not self.index:
            return []
        return [
            s
            for s in self.index.symbols
            if s.symbol_name == name
            or s.qualname == name
            or s.qualname.endswith("." + name)
        ]

    def definitions(self, name: str) -> list[dict[str, Any]]:
        if not self.index:
            return []
        return definitions_of(self.index, name)

    def callers(self, name: str) -> list[dict[str, Any]]:
        if not self.index:
            return []
        return callers_of_symbol(self.index, name)

    def callees(self, name: str) -> list[dict[str, Any]]:
        if not self.index or not self._call_g:
            return []
        return callees_of(self._call_g, name)

    def query(self, text: str) -> dict[str, Any]:
        if not self.index:
            return {"error": "intelligence not built — run: aegis intelligence build"}

        q = text.strip()
        ql = q.lower()

        # who calls / callers of
        m = re.search(
            r"(?:who calls|callers?\s+of|who invokes|references?\s+to)\s+"
            r"[`'\"]?([A-Za-z_][A-Za-z0-9_.]*)[`'\"]?",
            q,
            re.I,
        )
        if m:
            name = m.group(1)
            results = self.callers(name)
            defs = self.definitions(name)
            return {
                "query": q,
                "type": "callers",
                "symbol": name,
                "definitions": defs,
                "results": results,
                "count": len(results),
            }

        m = re.search(
            r"(?:what does|callees?\s+of|calls made by|what calls does)\s+"
            r"[`'\"]?([A-Za-z_][A-Za-z0-9_.]*)[`'\"]?",
            q,
            re.I,
        )
        if m:
            name = m.group(1)
            return {
                "query": q,
                "type": "callees",
                "symbol": name,
                "results": self.callees(name),
            }

        m = re.search(
            r"(?:who imports|importers?\s+of)\s+[`'\"]?([A-Za-z_][A-Za-z0-9_.]*)[`'\"]?",
            q,
            re.I,
        )
        if m:
            mod = m.group(1)
            assert self._import_g is not None
            return {
                "query": q,
                "type": "importers",
                "module": mod,
                "results": importers_of(self._import_g, mod),
            }

        m = re.search(
            r"(?:imports of)\s+[`'\"]?([A-Za-z_][A-Za-z0-9_.]*)[`'\"]?",
            q,
            re.I,
        )
        if m:
            mod = m.group(1)
            assert self._import_g is not None
            return {
                "query": q,
                "type": "imports",
                "module": mod,
                "results": imports_of(self._import_g, mod),
            }

        m = re.search(
            r"(?:where is|define|definition of|find)\s+[`'\"]?([A-Za-z_][A-Za-z0-9_.]*)[`'\"]?",
            q,
            re.I,
        )
        if m or ql.startswith("def "):
            name = m.group(1) if m else q.split()[-1]
            return {
                "query": q,
                "type": "definitions",
                "symbol": name,
                "results": self.definitions(name),
            }

        m = re.search(
            r"(?:subclasses? of|children of|who extends)\s+"
            r"[`'\"]?([A-Za-z_][A-Za-z0-9_.]*)[`'\"]?",
            q,
            re.I,
        )
        if m:
            name = m.group(1)
            return {
                "query": q,
                "type": "subclasses",
                "symbol": name,
                "results": self.subclasses(name),
            }

        m = re.search(
            r"(?:bases? of|parents? of|superclasses? of)\s+"
            r"[`'\"]?([A-Za-z_][A-Za-z0-9_.]*)[`'\"]?",
            q,
            re.I,
        )
        if m:
            name = m.group(1)
            return {
                "query": q,
                "type": "bases",
                "symbol": name,
                "results": self.bases(name),
            }

        if "dependenc" in ql or "external package" in ql:
            return {"query": q, "type": "dependencies", **self.dependencies()}

        # default: hybrid search
        return {
            "query": q,
            "type": "hybrid_search",
            "results": self.hybrid_search(q.strip("`\"'")),
        }

    def impact(
        self,
        file: str,
        line_start: int = 1,
        line_end: int | None = None,
    ) -> dict[str, Any]:
        if not self.index:
            return {"error": "intelligence not built"}

        rel = file.replace("\\", "/").lstrip("./")
        symbols_in_range = [
            s
            for s in self.index.symbols
            if s.file.replace("\\", "/") == rel
            or s.file.endswith("/" + rel)
            or s.file.endswith(rel)
        ]
        if line_end is not None:
            symbols_in_range = [
                s
                for s in symbols_in_range
                if not (s.line_end < line_start or s.line_start > line_end)
            ]

        affected: list[dict[str, Any]] = []
        for s in symbols_in_range:
            if s.symbol_type is SymbolKind.MODULE:
                continue
            affected.extend(self.callers(s.qualname))

        modules = {s.module for s in symbols_in_range if s.module}
        importers: list[str] = []
        assert self._import_g is not None
        for mod in modules:
            importers.extend(importers_of(self._import_g, mod))

        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for c in affected:
            key = f"{c['caller']}->{c['callee']}:{c.get('line')}"
            if key not in seen:
                seen.add(key)
                unique.append(c)

        risk = "low"
        if len(unique) > 10 or len(set(importers)) > 5:
            risk = "high"
        elif len(unique) > 3 or len(set(importers)) > 1:
            risk = "medium"

        return {
            "file": rel,
            "line_start": line_start,
            "line_end": line_end,
            "symbols": [s.model_dump(mode="json") for s in symbols_in_range[:40]],
            "callers": unique[:80],
            "importers": sorted(set(importers))[:50],
            "risk_level": risk,
        }

    def search(self, text: str, *, limit: int = 30) -> list[dict[str, Any]]:
        """Keyword search over symbol names (legacy)."""
        if not self.index:
            return []
        tokens = [t.lower() for t in re.split(r"\W+", text) if t]
        if not tokens:
            return []
        scored: list[tuple[int, CodeLocation]] = []
        for s in self.index.symbols:
            blob = f"{s.symbol_name} {s.qualname} {s.file}".lower()
            score = sum(1 for t in tokens if t in blob)
            if score:
                scored.append((score, s))
        scored.sort(key=lambda x: (-x[0], x[1].qualname))
        return [{"score": sc, **loc.model_dump(mode="json")} for sc, loc in scored[:limit]]

    def hybrid_search(self, text: str, *, limit: int = 25) -> list[dict[str, Any]]:
        """TF-IDF semantic + keyword + light graph expansion."""
        if not self.index:
            return []
        if self._tfidf is None:
            self._tfidf = build_symbol_tfidf(self.index.symbols)
        keyword = self.search(text, limit=limit)
        # expand using top keyword hit's callers
        expand: list[dict[str, Any]] = []
        for h in keyword[:3]:
            qn = h.get("qualname") or h.get("symbol_name") or ""
            if qn:
                expand.extend(self.callers(str(qn))[:10])
        return hybrid_search(
            text,
            tfidf=self._tfidf,
            keyword_hits=keyword,
            expand_callers=expand,
            limit=limit,
        )

    def subclasses(self, name: str) -> list[str]:
        if not self.index:
            return []
        return subclasses_of(self.index.inheritance, name)

    def bases(self, name: str) -> list[str]:
        if not self.index:
            return []
        return bases_of(self.index.inheritance, name)

    def dependencies(self) -> dict[str, Any]:
        if not self.index:
            return {"error": "intelligence not built"}
        return {
            "packages": [d.model_dump(mode="json") for d in self.index.external_deps],
            "importers": self.index.external_importers,
        }

    def graph_summary(self, graph_type: str = "import") -> dict[str, Any]:
        if not self.index:
            return {"error": "intelligence not built"}
        if graph_type == "call":
            assert self._call_g is not None
            g = self._call_g
            sample = list(g.edges(data=True))[:100]
            return {
                "type": "call",
                "nodes": g.number_of_nodes(),
                "edges": g.number_of_edges(),
                "sample_edges": [
                    {
                        "from": u,
                        "to": v,
                        **{
                            k: d
                            for k, d in data.items()
                            if k in ("file", "line", "confidence", "resolved")
                        },
                    }
                    for u, v, data in sample
                ],
            }
        if graph_type == "class":
            edges = self.index.inheritance[:100]
            return {
                "type": "class",
                "nodes": len(self.index.class_infos),
                "edges": len(self.index.inheritance),
                "sample_edges": [
                    {
                        "from": e.child,
                        "to": e.parent,
                        "file": e.file,
                        "line": e.line,
                        "resolved": e.resolved,
                    }
                    for e in edges
                ],
            }
        if graph_type == "dependency":
            return {
                "type": "dependency",
                "nodes": len(self.index.external_deps),
                "edges": sum(len(v) for v in self.index.external_importers.values()),
                "packages": [d.model_dump(mode="json") for d in self.index.external_deps[:50]],
                "importers_sample": {
                    k: v[:10] for k, v in list(self.index.external_importers.items())[:20]
                },
            }
        # import default
        assert self._import_g is not None
        g = self._import_g
        edges = list(g.edges(data=True))[:100]
        return {
            "type": "import",
            "nodes": g.number_of_nodes(),
            "edges": g.number_of_edges(),
            "sample_edges": [
                {
                    "from": u,
                    "to": v,
                    **{k: d for k, d in data.items() if k in ("file", "line")},
                }
                for u, v, data in edges
            ],
            "cycles_sample": find_cycles(self._import_g)[:10],  # type: ignore[arg-type]
        }

    def graph_query(self, op: str, target: str, **kwargs: Any) -> dict[str, Any]:
        """Unified API for tools/agents."""
        self.ensure_built()
        op = op.lower().strip()
        if op in {"callers", "who_calls", "references"}:
            return {"op": "callers", "target": target, "results": self.callers(target)}
        if op in {"callees", "calls"}:
            return {"op": "callees", "target": target, "results": self.callees(target)}
        if op in {"definitions", "define", "where"}:
            return {
                "op": "definitions",
                "target": target,
                "results": self.definitions(target),
            }
        if op in {"importers"}:
            assert self._import_g is not None
            return {
                "op": "importers",
                "target": target,
                "results": importers_of(self._import_g, target),
            }
        if op in {"imports"}:
            assert self._import_g is not None
            return {
                "op": "imports",
                "target": target,
                "results": imports_of(self._import_g, target),
            }
        if op in {"subclasses", "children"}:
            return {
                "op": "subclasses",
                "target": target,
                "results": self.subclasses(target),
            }
        if op in {"bases", "parents", "superclasses"}:
            return {"op": "bases", "target": target, "results": self.bases(target)}
        if op in {"deps", "dependencies"}:
            return {"op": "dependencies", **self.dependencies()}
        if op in {"impact"}:
            file_path = target
            ls, le = 1, None
            m = re.match(r"^(.+):(\d+)(?:-(\d+))?$", target)
            if m:
                file_path = m.group(1)
                ls = int(m.group(2))
                le = int(m.group(3)) if m.group(3) else ls
            return {"op": "impact", **self.impact(file_path, ls, le)}
        if op in {"search"}:
            return {"op": "search", "results": self.search(target)}
        if op in {"hybrid", "semantic", "codesearch"}:
            return {
                "op": "hybrid",
                "target": target,
                "results": self.hybrid_search(target),
            }
        return {
            "error": f"unknown op: {op}",
            "supported": [
                "callers",
                "callees",
                "definitions",
                "importers",
                "imports",
                "subclasses",
                "bases",
                "dependencies",
                "impact",
                "search",
                "hybrid",
            ],
        }


def build_intelligence(root: Path, *, incremental: bool = False) -> IntelligenceIndex:
    engine = IntelligenceEngine(root)
    return engine.build(incremental=incremental)
