"""Class inheritance relationships from Python AST."""

from __future__ import annotations

import ast
from pathlib import Path

from aegis.intelligence.models import ClassInfo, InheritanceEdge
from aegis.intelligence.python_ast import iter_python_files, module_name_for


def extract_classes(root: Path) -> tuple[list[ClassInfo], list[InheritanceEdge]]:
    root = root.resolve()
    classes: list[ClassInfo] = []
    edges: list[InheritanceEdge] = []

    for path in iter_python_files(root):
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError):
            continue
        rel = path.relative_to(root).as_posix()
        module = module_name_for(path, root)

        class Visitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.class_stack: list[str] = []

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                if self.class_stack:
                    qn = f"{self.class_stack[-1]}.{node.name}"
                else:
                    qn = f"{module}.{node.name}" if module else node.name
                bases: list[str] = []
                for base in node.bases:
                    bname = _base_to_str(base)
                    if bname:
                        bases.append(bname)
                        edges.append(
                            InheritanceEdge(
                                child=qn,
                                parent=bname,
                                file=rel,
                                line=node.lineno,
                            )
                        )
                classes.append(
                    ClassInfo(
                        qualname=qn,
                        name=node.name,
                        module=module,
                        file=rel,
                        line=node.lineno,
                        bases=bases,
                    )
                )
                self.class_stack.append(qn)
                for child in node.body:
                    self.visit(child)
                self.class_stack.pop()

        Visitor().visit(tree)

    by_name: dict[str, list[str]] = {}
    for c in classes:
        by_name.setdefault(c.name, []).append(c.qualname)
        by_name.setdefault(c.qualname, []).append(c.qualname)

    resolved_edges: list[InheritanceEdge] = []
    for e in edges:
        parent = e.parent
        if parent in by_name:
            opts = by_name[parent]
            if len(opts) == 1:
                resolved_edges.append(
                    e.model_copy(update={"parent": opts[0], "resolved": True})
                )
            else:
                child_mod = e.child.rsplit(".", 1)[0]
                same = [o for o in opts if o.startswith(child_mod)]
                if len(same) == 1:
                    resolved_edges.append(
                        e.model_copy(update={"parent": same[0], "resolved": True})
                    )
                else:
                    resolved_edges.append(e)
        else:
            short = parent.split(".")[-1]
            if short in by_name and len(by_name[short]) == 1:
                resolved_edges.append(
                    e.model_copy(update={"parent": by_name[short][0], "resolved": True})
                )
            else:
                resolved_edges.append(e)

    return classes, resolved_edges


def _base_to_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _base_to_str(node.value)
        if base:
            return f"{base}.{node.attr}"
        return node.attr
    if isinstance(node, ast.Subscript):
        return _base_to_str(node.value)
    return None


def subclasses_of(edges: list[InheritanceEdge], name: str) -> list[str]:
    children: dict[str, list[str]] = {}
    for e in edges:
        children.setdefault(e.parent, []).append(e.child)
        children.setdefault(e.parent.split(".")[-1], []).append(e.child)

    found: set[str] = set()
    stack = [name, name.split(".")[-1]]
    while stack:
        cur = stack.pop()
        for ch in children.get(cur, []):
            if ch not in found:
                found.add(ch)
                stack.append(ch)
    return sorted(found)


def bases_of(edges: list[InheritanceEdge], name: str) -> list[str]:
    parents: set[str] = set()
    for e in edges:
        if (
            e.child == name
            or e.child.endswith("." + name)
            or e.child.split(".")[-1] == name
        ):
            parents.add(e.parent)
    return sorted(parents)
