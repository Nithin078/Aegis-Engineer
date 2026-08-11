"""Parse Python files with import/alias-aware call extraction."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from aegis.intelligence.models import (
    CallEdge,
    CodeLocation,
    Confidence,
    ImportEdge,
    SymbolKind,
)

_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".aegis",
    "dist",
    "build",
    ".tox",
    "htmlcov",
}


def iter_python_files(root: Path) -> list[Path]:
    root = root.resolve()
    files: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return files


def file_hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def module_name_for(path: Path, root: Path) -> str:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return path.stem
    parts = list(rel.with_suffix("").parts)
    if parts and parts[0] == "src" and len(parts) > 1:
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else path.stem


def resolve_relative_module(module: str, level: int, target: str | None) -> str:
    """Resolve ``from ..x import y`` style module path."""
    if level <= 0:
        return target or ""
    parts = module.split(".") if module else []
    # level=1 means current package; level=2 go up one, etc.
    keep = len(parts) - level
    if keep < 0:
        keep = 0
    base_parts = parts[:keep]
    if target:
        return ".".join([*base_parts, target]) if base_parts else target
    return ".".join(base_parts)


def parse_python_file(
    path: Path,
    root: Path,
) -> tuple[list[CodeLocation], list[ImportEdge], list[CallEdge], dict[str, str]]:
    """Extract symbols, imports, calls, and local name→qualname bindings."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError):
        return [], [], [], {}

    rel = path.resolve().relative_to(root.resolve()).as_posix()
    module = module_name_for(path, root)
    symbols: list[CodeLocation] = []
    imports: list[ImportEdge] = []
    calls: list[CallEdge] = []

    # local_name -> fully qualified symbol path
    bindings: dict[str, str] = {}

    symbols.append(
        CodeLocation(
            file=rel,
            line_start=1,
            line_end=max(1, len(source.splitlines())),
            symbol_name=module or path.stem,
            symbol_type=SymbolKind.MODULE,
            qualname=module or path.stem,
            module=module,
        )
    )

    # Collect imports + bindings first (module scope)
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                # import util as u -> u maps to util (module)
                # import util.sub -> util maps to util
                target = alias.name
                bindings[local] = target
                imports.append(
                    ImportEdge(
                        source_module=module,
                        target_module=alias.name,
                        names=[local],
                        file=rel,
                        line=node.lineno,
                        bindings={local: target},
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            base = resolve_relative_module(module, node.level, node.module)
            edge_bindings: dict[str, str] = {}
            names: list[str] = []
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                # from util import format_name as fn -> fn = util.format_name
                target = f"{base}.{alias.name}" if base else alias.name
                bindings[local] = target
                edge_bindings[local] = target
                names.append(local)
            imports.append(
                ImportEdge(
                    source_module=module,
                    target_module=base or ".",
                    names=names,
                    is_relative=bool(node.level),
                    file=rel,
                    line=node.lineno,
                    bindings=edge_bindings,
                )
            )

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            # stack of (kind, name) where kind is 'module'|'class'|'function'
            self.stack: list[tuple[str, str]] = [("module", module)]
            # local type inference: var -> Class qualname
            self.types: dict[str, str] = {}
            # per-function local bindings (copy of module + params)
            self.local_bindings: dict[str, str] = dict(bindings)

        def _scope_qual(self) -> str:
            parts = [n for k, n in self.stack if k != "module" or n]
            # Always start with module
            if self.stack and self.stack[0][0] == "module":
                base = self.stack[0][1]
                rest = [n for k, n in self.stack[1:]]
                return ".".join([base, *rest]) if rest else base
            return ".".join(parts)

        def _enclosing_callable(self) -> str:
            parts: list[str] = []
            for kind, name in self.stack:
                if kind == "module":
                    parts = [name] if name else []
                elif kind == "class":
                    parts.append(name)
                elif kind in {"function", "method"}:
                    parts.append(name)
                    return ".".join(parts)
            return module or ""

        def _current_class(self) -> str | None:
            for kind, name in reversed(self.stack):
                if kind == "class":
                    mod = self.stack[0][1] if self.stack else module
                    # class qualname: module.Class
                    class_parts = [mod] if mod else []
                    for k, n in self.stack:
                        if k == "class":
                            class_parts.append(n)
                        if k == "class" and n == name:
                            break
                    return ".".join(p for p in class_parts if p)
            return None

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            qn = f"{module}.{node.name}" if module else node.name
            # nested class
            parent_cls = self._current_class()
            if parent_cls:
                qn = f"{parent_cls}.{node.name}"
            symbols.append(
                CodeLocation(
                    file=rel,
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", None) or node.lineno,
                    symbol_name=node.name,
                    symbol_type=SymbolKind.CLASS,
                    qualname=qn,
                    module=module,
                )
            )
            # class name binds to itself in module scope
            if len([k for k, _ in self.stack if k == "class"]) == 0:
                bindings[node.name] = qn
                self.local_bindings[node.name] = qn

            self.stack.append(("class", node.name))
            for child in node.body:
                self.visit(child)
            self.stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._visit_function(node, async_fn=False)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._visit_function(node, async_fn=True)

        def _visit_function(
            self,
            node: ast.FunctionDef | ast.AsyncFunctionDef,
            *,
            async_fn: bool,
        ) -> None:
            in_class = self._current_class() is not None
            kind = SymbolKind.METHOD if in_class else (
                SymbolKind.ASYNC_FUNCTION if async_fn else SymbolKind.FUNCTION
            )
            if in_class:
                qn = f"{self._current_class()}.{node.name}"
            else:
                qn = f"{module}.{node.name}" if module else node.name

            symbols.append(
                CodeLocation(
                    file=rel,
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", None) or node.lineno,
                    symbol_name=node.name,
                    symbol_type=kind,
                    qualname=qn,
                    module=module,
                )
            )
            # module-level function binding
            if not in_class and len([k for k, _ in self.stack if k in {"function", "method"}]) == 0:
                bindings[node.name] = qn

            frame = "method" if in_class else "function"
            self.stack.append((frame, node.name))
            saved_types = dict(self.types)
            saved_locals = dict(self.local_bindings)
            self.local_bindings = dict(bindings)
            # self / cls param type
            if in_class and node.args.args:
                first = node.args.args[0].arg
                cls = self._current_class()
                if cls:
                    self.local_bindings[first] = cls
                    self.types[first] = cls

            for child in node.body:
                self.visit(child)

            self.types = saved_types
            self.local_bindings = saved_locals
            self.stack.pop()

        def visit_Assign(self, node: ast.Assign) -> None:
            self._track_assignment(node.targets, node.value)
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            if node.value is not None:
                self._track_assignment([node.target], node.value)
            self.generic_visit(node)

        def _track_assignment(self, targets: list[ast.AST], value: ast.AST) -> None:
            # x = Foo() or x = Foo
            class_name: str | None = None
            if isinstance(value, ast.Call):
                class_name = self._resolve_name_expr(value.func)
            elif isinstance(value, (ast.Name, ast.Attribute)):
                class_name = self._resolve_name_expr(value)
            if not class_name:
                return
            for t in targets:
                if isinstance(t, ast.Name):
                    self.types[t.id] = class_name
                    # don't overwrite import bindings for call resolution of modules
                    if t.id not in bindings:
                        self.local_bindings[t.id] = class_name

        def visit_Call(self, node: ast.Call) -> None:
            # Only record calls inside functions/methods
            if not any(k in {"function", "method"} for k, _ in self.stack):
                self.generic_visit(node)
                return
            caller = self._enclosing_callable()
            raw = _expr_to_str(node.func) or ""
            resolved, conf = self._resolve_call(node.func)
            calls.append(
                CallEdge(
                    caller=caller,
                    callee=resolved or raw,
                    raw_callee=raw,
                    file=rel,
                    line=node.lineno,
                    confidence=conf,
                    resolved=bool(resolved and conf != Confidence.LOW),
                )
            )
            self.generic_visit(node)

        def _resolve_name_expr(self, expr: ast.AST) -> str | None:
            """Resolve Name/Attribute to a qualname using bindings + types."""
            if isinstance(expr, ast.Name):
                name = expr.id
                if name in self.local_bindings:
                    return self.local_bindings[name]
                if name in self.types:
                    return self.types[name]
                if name in bindings:
                    return bindings[name]
                # same-module bare name: module.name
                if module:
                    return f"{module}.{name}"
                return name
            if isinstance(expr, ast.Attribute):
                base = self._resolve_name_expr(expr.value)
                if base:
                    return f"{base}.{expr.attr}"
                return expr.attr
            return None

        def _resolve_call(self, func: ast.AST) -> tuple[str | None, Confidence]:
            if isinstance(func, ast.Name):
                name = func.id
                if name in self.local_bindings:
                    return self.local_bindings[name], Confidence.HIGH
                if name in bindings:
                    return bindings[name], Confidence.HIGH
                # local def in same module
                if module:
                    return f"{module}.{name}", Confidence.MEDIUM
                return name, Confidence.LOW

            if isinstance(func, ast.Attribute):
                # self.method / cls.method
                if isinstance(func.value, ast.Name):
                    base_name = func.value.id
                    attr = func.attr
                    if base_name in self.types:
                        return f"{self.types[base_name]}.{attr}", Confidence.HIGH
                    if base_name in self.local_bindings:
                        bound = self.local_bindings[base_name]
                        # module alias: util.format_name
                        return f"{bound}.{attr}", Confidence.HIGH
                    if base_name in bindings:
                        return f"{bindings[base_name]}.{attr}", Confidence.HIGH
                    # self without type (shouldn't happen if we set self)
                    cls = self._current_class()
                    if base_name in {"self", "cls"} and cls:
                        return f"{cls}.{attr}", Confidence.HIGH
                    return f"{base_name}.{attr}", Confidence.LOW

                # deeper: obj.chain.method
                resolved = self._resolve_name_expr(func)
                if resolved:
                    conf = (
                        Confidence.MEDIUM
                        if "." in resolved
                        else Confidence.LOW
                    )
                    return resolved, conf
                raw = _expr_to_str(func)
                return raw, Confidence.LOW

            return _expr_to_str(func), Confidence.LOW

    Visitor().visit(tree)
    return symbols, imports, calls, bindings


def _expr_to_str(expr: ast.AST) -> str | None:
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        base = _expr_to_str(expr.value)
        if base:
            return f"{base}.{expr.attr}"
        return expr.attr
    return None
