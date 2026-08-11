"""External package dependency graph from project manifests."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

# Simple requirement line: name[extra]==1.2 / name>=1 / name
_REQ_RE = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9_.+\-]*)"
    r"(?:\[[^\]]*\])?"
    r"\s*([><=!~]{1,2}\s*[^;#\s]+)?"
)


class ExternalDep(BaseModel):
    name: str
    spec: str = ""  # version constraint if any
    source: str = ""  # file path


class DependencyIndex(BaseModel):
    dependencies: list[ExternalDep] = Field(default_factory=list)
    # project modules that import external package name
    importers: dict[str, list[str]] = Field(default_factory=dict)

    def package_names(self) -> list[str]:
        return sorted({d.name.lower().replace("-", "_") for d in self.dependencies})


def parse_requirements_txt(path: Path) -> list[ExternalDep]:
    deps: list[ExternalDep] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return deps
    rel = path.name
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        m = _REQ_RE.match(line)
        if not m:
            continue
        name = m.group(1)
        spec = (m.group(2) or "").strip()
        deps.append(ExternalDep(name=name, spec=spec, source=rel))
    return deps


def parse_pyproject_deps(path: Path) -> list[ExternalDep]:
    deps: list[ExternalDep] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return deps
    # Minimal TOML-ish parse for dependencies = [ "x>=1", ... ]
    # Avoid tomllib dependency on older edge cases — Python 3.12 has tomllib
    try:
        import tomllib

        data = tomllib.loads(text)
    except Exception:
        return _parse_pyproject_regex(text, path.name)

    project = data.get("project") or {}
    for item in project.get("dependencies") or []:
        if isinstance(item, str):
            m = _REQ_RE.match(item)
            if m:
                deps.append(
                    ExternalDep(
                        name=m.group(1),
                        spec=(m.group(2) or "").strip(),
                        source="pyproject.toml",
                    )
                )
    optional = project.get("optional-dependencies") or {}
    if isinstance(optional, dict):
        for _group, items in optional.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, str):
                    m = _REQ_RE.match(item)
                    if m:
                        deps.append(
                            ExternalDep(
                                name=m.group(1),
                                spec=(m.group(2) or "").strip(),
                                source="pyproject.toml[optional]",
                            )
                        )
    return deps


def _parse_pyproject_regex(text: str, source: str) -> list[ExternalDep]:
    deps: list[ExternalDep] = []
    in_deps = False
    for line in text.splitlines():
        if re.match(r"^\s*dependencies\s*=\s*\[", line):
            in_deps = True
        if in_deps:
            for m in re.finditer(r'["\']([^"\']+)["\']', line):
                raw = m.group(1)
                rm = _REQ_RE.match(raw)
                if rm:
                    deps.append(
                        ExternalDep(
                            name=rm.group(1),
                            spec=(rm.group(2) or "").strip(),
                            source=source,
                        )
                    )
            if "]" in line:
                in_deps = False
    return deps


def load_external_deps(root: Path) -> list[ExternalDep]:
    root = root.resolve()
    deps: list[ExternalDep] = []
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        deps.extend(parse_pyproject_deps(pyproject))
    for name in ("requirements.txt", "requirements-dev.txt", "requirements/dev.txt"):
        p = root / name
        if p.is_file():
            deps.extend(parse_requirements_txt(p))
    # dedupe by name+spec
    seen: set[str] = set()
    unique: list[ExternalDep] = []
    for d in deps:
        key = f"{d.name}|{d.spec}|{d.source}"
        if key not in seen:
            seen.add(key)
            unique.append(d)
    return unique


def map_external_importers(
    imports: list,  # ImportEdge-like with target_module, source_module
    external_names: set[str],
) -> dict[str, list[str]]:
    """Map normalized package name -> list of project modules that import it."""
    importers: dict[str, list[str]] = {}
    for edge in imports:
        target = getattr(edge, "target_module", "") or ""
        source = getattr(edge, "source_module", "") or ""
        top = target.split(".")[0].lower().replace("-", "_")
        # match against known deps (normalize hyphens)
        for ext in external_names:
            ext_n = ext.lower().replace("-", "_")
            if top == ext_n or target.lower().replace("-", "_").startswith(ext_n + "."):
                importers.setdefault(ext, []).append(source)
    # unique sort
    return {k: sorted(set(v)) for k, v in importers.items()}
