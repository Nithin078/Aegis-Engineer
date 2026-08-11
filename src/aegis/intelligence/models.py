"""Data models for repository intelligence."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SymbolKind(StrEnum):
    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    CLASS = "class"
    METHOD = "method"
    MODULE = "module"


class Confidence(StrEnum):
    HIGH = "high"  # resolved via imports / defs / self
    MEDIUM = "medium"  # attribute chain / constructor guess
    LOW = "low"  # bare name match only


class CodeLocation(BaseModel):
    file: str
    line_start: int
    line_end: int
    symbol_name: str
    symbol_type: SymbolKind
    qualname: str = ""
    module: str = ""


class ImportEdge(BaseModel):
    source_module: str
    target_module: str
    names: list[str] = Field(default_factory=list)
    is_relative: bool = False
    file: str = ""
    line: int = 0
    # local_name -> imported symbol path (e.g. fn -> util.format_name)
    bindings: dict[str, str] = Field(default_factory=dict)


class CallEdge(BaseModel):
    caller: str  # qualname of enclosing function/method
    callee: str  # resolved qualname when possible
    raw_callee: str = ""  # as written in source
    file: str
    line: int
    confidence: Confidence = Confidence.LOW
    resolved: bool = False


class InheritanceEdge(BaseModel):
    child: str
    parent: str
    file: str = ""
    line: int = 0
    resolved: bool = False


class ClassInfo(BaseModel):
    qualname: str
    name: str
    module: str = ""
    file: str = ""
    line: int = 0
    bases: list[str] = Field(default_factory=list)


class ExternalDep(BaseModel):
    name: str
    spec: str = ""
    source: str = ""


class IntelligenceStats(BaseModel):
    files: int = 0
    symbols: int = 0
    functions: int = 0
    classes: int = 0
    import_edges: int = 0
    call_edges: int = 0
    resolved_calls: int = 0
    inheritance_edges: int = 0
    external_deps: int = 0
    modules: int = 0
    cycles: int = 0
    build_ms: float = 0.0
    built_at: datetime | None = None
    root: str = ""


class IntelligenceIndex(BaseModel):
    """Serializable intelligence snapshot."""

    version: int = 3
    root: str
    built_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    file_hashes: dict[str, str] = Field(default_factory=dict)
    symbols: list[CodeLocation] = Field(default_factory=list)
    imports: list[ImportEdge] = Field(default_factory=list)
    calls: list[CallEdge] = Field(default_factory=list)
    # local name bindings per module: module -> {local: qualname}
    module_bindings: dict[str, dict[str, str]] = Field(default_factory=dict)
    inheritance: list[InheritanceEdge] = Field(default_factory=list)
    class_infos: list[ClassInfo] = Field(default_factory=list)
    external_deps: list[ExternalDep] = Field(default_factory=list)
    # package -> project modules that import it
    external_importers: dict[str, list[str]] = Field(default_factory=dict)
    stats: IntelligenceStats = Field(default_factory=IntelligenceStats)

    def to_summary(self) -> dict[str, Any]:
        return self.stats.model_dump(mode="json")
