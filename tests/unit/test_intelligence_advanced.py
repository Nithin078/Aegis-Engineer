"""Phase 7: class graph, deps, hybrid search."""

from __future__ import annotations

from pathlib import Path

from aegis.intelligence.class_graph import extract_classes, subclasses_of
from aegis.intelligence.dependencies import load_external_deps
from aegis.intelligence.embeddings import build_symbol_tfidf, hybrid_search, tokenize
from aegis.intelligence.engine import IntelligenceEngine, build_intelligence
from aegis.intelligence.models import CodeLocation, SymbolKind
from aegis.tools.registry import create_default_registry


def _oop_fixture(tmp: Path) -> Path:
    root = tmp / "oop"
    root.mkdir()
    (root / "models.py").write_text(
        '''
class Animal:
    def speak(self):
        return "..."

class Dog(Animal):
    def speak(self):
        return "woof"

class Puppy(Dog):
    pass
''',
        encoding="utf-8",
    )
    (root / "app.py").write_text(
        '''
from models import Dog

def run():
    d = Dog()
    return d.speak()
''',
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        '''
[project]
name = "oop"
dependencies = ["httpx>=0.27.0", "pydantic>=2.0"]
''',
        encoding="utf-8",
    )
    return root


def test_class_inheritance(tmp_path: Path) -> None:
    root = _oop_fixture(tmp_path)
    classes, edges = extract_classes(root)
    names = {c.name for c in classes}
    assert "Animal" in names and "Dog" in names and "Puppy" in names
    assert any(e.child.endswith("Dog") and "Animal" in e.parent for e in edges)
    subs = subclasses_of(edges, "Animal")
    assert any("Dog" in s for s in subs)
    assert any("Puppy" in s for s in subs)


def test_external_deps(tmp_path: Path) -> None:
    root = _oop_fixture(tmp_path)
    deps = load_external_deps(root)
    names = {d.name for d in deps}
    assert "httpx" in names
    assert "pydantic" in names


def test_tfidf_and_hybrid() -> None:
    symbols = [
        CodeLocation(
            file="a.py",
            line_start=1,
            line_end=2,
            symbol_name="authenticate_user",
            symbol_type=SymbolKind.FUNCTION,
            qualname="auth.authenticate_user",
            module="auth",
        ),
        CodeLocation(
            file="b.py",
            line_start=1,
            line_end=2,
            symbol_name="format_name",
            symbol_type=SymbolKind.FUNCTION,
            qualname="util.format_name",
            module="util",
        ),
    ]
    idx = build_symbol_tfidf(symbols)
    hits = idx.search("user authentication login")
    assert hits
    assert "authenticate" in (hits[0].get("qualname") or hits[0].get("id") or "")

    hybrid = hybrid_search(
        "authentication",
        tfidf=idx,
        keyword_hits=[{"qualname": "auth.authenticate_user", "score": 2}],
        limit=5,
    )
    assert hybrid


def test_tokenize():
    tokens = tokenize("authenticate_user")
    assert "authenticate" in tokens
    assert "user" in tokens


def test_engine_phase7(tmp_path: Path) -> None:
    root = _oop_fixture(tmp_path)
    index = build_intelligence(root)
    assert index.stats.inheritance_edges >= 2
    assert index.stats.external_deps >= 2

    eng = IntelligenceEngine(root)
    subs = eng.subclasses("Animal")
    assert any("Dog" in s for s in subs)

    deps = eng.dependencies()
    assert deps.get("packages")

    hits = eng.hybrid_search("animal dog speak")
    assert hits

    g = eng.graph_summary("class")
    assert g.get("edges", 0) >= 2

    g2 = eng.graph_summary("dependency")
    assert g2.get("packages")

    q = eng.query("subclasses of Animal")
    assert q["type"] == "subclasses"


def test_tools_registered() -> None:
    reg = create_default_registry()
    assert reg.get("graph_query")
    assert reg.get("codesearch")
