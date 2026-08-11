"""JSON-backed memory store (repo-local + global)."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from aegis.memory.models import MemoryEntry, MemoryKind, MemoryQueryResult


def repo_id_for(workspace: Path | str) -> str:
    """Stable short id for a workspace path."""
    root = str(Path(workspace).resolve()).lower().replace("\\", "/")
    digest = hashlib.sha256(root.encode("utf-8")).hexdigest()[:12]
    name = Path(workspace).resolve().name
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", name)[:32] or "repo"
    return f"{safe}-{digest}"


def global_memory_dir() -> Path:
    return Path.home() / ".config" / "aegis" / "memory"


def repo_memory_dir(workspace: Path | str, store_dir: str = ".aegis/memory") -> Path:
    return Path(workspace).resolve() / store_dir


class MemoryStore:
    """
    Persist memory entries as JSON lines.

    - Repo: `<workspace>/.aegis/memory/entries.jsonl`
    - Global: `~/.config/aegis/memory/global.jsonl`
    """

    def __init__(
        self,
        workspace: Path | str | None = None,
        *,
        store_dir: str = ".aegis/memory",
        global_enabled: bool = True,
        max_entries_per_repo: int = 1000,
    ) -> None:
        self.workspace = Path(workspace).resolve() if workspace else None
        self.store_dir = store_dir
        self.global_enabled = global_enabled
        self.max_entries_per_repo = max_entries_per_repo
        self.repo_id = repo_id_for(self.workspace) if self.workspace else ""

    def _repo_path(self) -> Path | None:
        if not self.workspace:
            return None
        return repo_memory_dir(self.workspace, self.store_dir) / "entries.jsonl"

    def _global_path(self) -> Path:
        return global_memory_dir() / "global.jsonl"

    def add(self, entry: MemoryEntry) -> MemoryEntry:
        if not entry.repo_id and self.repo_id:
            entry.repo_id = self.repo_id
        if entry.scope == "global":
            path = self._global_path()
        else:
            path = self._repo_path()
            if path is None:
                raise ValueError("Repo-scoped memory requires a workspace")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(entry.model_dump_json() + "\n")
        self._trim_if_needed(path)
        return entry

    def _trim_if_needed(self, path: Path) -> None:
        if not path.is_file():
            return
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) <= self.max_entries_per_repo:
            return
        keep = lines[-self.max_entries_per_repo :]
        path.write_text("\n".join(keep) + "\n", encoding="utf-8")

    def _load_file(self, path: Path) -> list[MemoryEntry]:
        if not path.is_file():
            return []
        out: list[MemoryEntry] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                out.append(MemoryEntry.model_validate(data))
            except (json.JSONDecodeError, ValueError):
                continue
        return out

    def list_entries(
        self,
        *,
        kind: MemoryKind | str | None = None,
        scope: str | None = None,
        include_global: bool = True,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        entries: list[MemoryEntry] = []
        if scope != "global":
            rp = self._repo_path()
            if rp:
                entries.extend(self._load_file(rp))
        if include_global and self.global_enabled and scope != "repo":
            entries.extend(self._load_file(self._global_path()))
        if kind is not None:
            k = MemoryKind(kind) if isinstance(kind, str) else kind
            entries = [e for e in entries if e.kind == k]
        # newest first
        entries.sort(key=lambda e: e.created_at, reverse=True)
        return entries[:limit]

    def get(self, entry_id: str) -> MemoryEntry | None:
        for e in self.list_entries(limit=10_000, include_global=True):
            if e.id == entry_id:
                return e
        return None

    def forget(
        self,
        *,
        entry_id: str | None = None,
        kind: MemoryKind | str | None = None,
        all_repo: bool = False,
        all_global: bool = False,
    ) -> int:
        """Remove matching entries. Returns count removed."""
        removed = 0
        if all_repo or entry_id or kind:
            rp = self._repo_path()
            if rp and rp.is_file():
                removed += self._filter_file(
                    rp, entry_id=entry_id, kind=kind, wipe=all_repo and not entry_id and not kind
                )
        if all_global or (entry_id and self.global_enabled):
            gp = self._global_path()
            if gp.is_file():
                removed += self._filter_file(
                    gp,
                    entry_id=entry_id,
                    kind=kind,
                    wipe=all_global and not entry_id and not kind,
                )
        return removed

    def _filter_file(
        self,
        path: Path,
        *,
        entry_id: str | None,
        kind: MemoryKind | str | None,
        wipe: bool,
    ) -> int:
        if wipe:
            n = len(self._load_file(path))
            path.write_text("", encoding="utf-8")
            return n
        entries = self._load_file(path)
        keep: list[MemoryEntry] = []
        removed = 0
        k = MemoryKind(kind) if isinstance(kind, str) and kind else kind
        for e in entries:
            drop = False
            if entry_id and e.id == entry_id:
                drop = True
            if k is not None and e.kind == k and not entry_id:
                drop = True
            if drop:
                removed += 1
            else:
                keep.append(e)
        path.write_text(
            "\n".join(e.model_dump_json() for e in keep) + ("\n" if keep else ""),
            encoding="utf-8",
        )
        return removed

    def query(
        self,
        text: str,
        *,
        limit: int = 5,
        kinds: list[MemoryKind] | None = None,
        include_global: bool = True,
    ) -> MemoryQueryResult:
        """Keyword-overlap retrieval of similar memories."""
        tokens = _tokenize(text)
        candidates = self.list_entries(
            include_global=include_global, limit=self.max_entries_per_repo
        )
        if kinds:
            kind_set = set(kinds)
            candidates = [e for e in candidates if e.kind in kind_set]
        scored: list[MemoryEntry] = []
        for e in candidates:
            blob = " ".join(
                [
                    e.title,
                    e.summary,
                    e.issue_text,
                    e.classification,
                    " ".join(e.files),
                    " ".join(e.tags),
                ]
            )
            etoks = _tokenize(blob)
            if not etoks or not tokens:
                score = 0.0
            else:
                overlap = len(tokens & etoks)
                score = overlap / max(len(tokens), 1)
                # boost same classification keywords
                if e.kind == MemoryKind.SOLVED:
                    score += 0.05
                if e.kind == MemoryKind.FAILURE:
                    score += 0.02
            if score > 0:
                e2 = e.model_copy(update={"score": round(score, 4)})
                scored.append(e2)
        scored.sort(key=lambda x: x.score or 0.0, reverse=True)
        return MemoryQueryResult(
            entries=scored[:limit],
            query=text[:500],
            repo_id=self.repo_id,
        )

    def export_all(self) -> dict[str, Any]:
        return {
            "repo_id": self.repo_id,
            "workspace": str(self.workspace) if self.workspace else None,
            "entries": [e.model_dump(mode="json") for e in self.list_entries(limit=50_000)],
        }

    def import_entries(self, data: dict[str, Any] | list[Any]) -> int:
        raw = data.get("entries") if isinstance(data, dict) else data
        if not isinstance(raw, list):
            raise ValueError("Import data must be a list or {entries: [...]}")
        count = 0
        for item in raw:
            if not isinstance(item, dict):
                continue
            entry = MemoryEntry.model_validate(item)
            # re-id collisions: keep original id if unique, else new
            if self.get(entry.id):
                new_id = f"mem_{hashlib.md5(entry.id.encode()).hexdigest()[:12]}"
                entry = entry.model_copy(update={"id": new_id})
            self.add(entry)
            count += 1
        return count

    def record_solved(
        self,
        *,
        issue_text: str,
        summary: str,
        classification: str = "",
        files: list[str] | None = None,
        plan_summary: str = "",
        code_summary: str = "",
        tags: list[str] | None = None,
        also_global: bool = False,
    ) -> MemoryEntry:
        entry = MemoryEntry(
            kind=MemoryKind.SOLVED,
            scope="repo",
            repo_id=self.repo_id,
            title=summary[:120] or "Solved issue",
            summary=summary[:500],
            issue_text=issue_text[:4000],
            classification=classification,
            files=list(files or [])[:50],
            tags=list(tags or []),
            payload={
                "plan_summary": plan_summary[:1000],
                "code_summary": code_summary[:2000],
            },
        )
        self.add(entry)
        if also_global and self.global_enabled:
            g = entry.model_copy(
                deep=True,
                update={
                    "id": f"mem_{hashlib.sha1(entry.id.encode()).hexdigest()[:12]}",
                    "scope": "global",
                    "kind": MemoryKind.GLOBAL,
                    "title": f"[pattern] {entry.title}",
                },
            )
            self.add(g)
        return entry

    def record_failure(
        self,
        *,
        issue_text: str,
        approach: str,
        reason: str,
        files: list[str] | None = None,
        classification: str = "",
    ) -> MemoryEntry:
        entry = MemoryEntry(
            kind=MemoryKind.FAILURE,
            scope="repo",
            repo_id=self.repo_id,
            title=(reason or approach)[:120],
            summary=f"Failed: {reason}"[:500],
            issue_text=issue_text[:4000],
            classification=classification,
            files=list(files or [])[:50],
            tags=["failure"],
            payload={"approach": approach[:2000], "reason": reason[:2000]},
        )
        return self.add(entry)

    def format_for_prompt(self, result: MemoryQueryResult, *, max_chars: int = 2500) -> str:
        if not result.entries:
            return "(no relevant memory)"
        lines: list[str] = []
        for e in result.entries:
            lines.append(
                f"- [{e.kind.value}] score={e.score} {e.title}: {e.summary}"
                f" files={','.join(e.files[:5])}"
            )
            if e.kind == MemoryKind.FAILURE and e.payload.get("reason"):
                lines.append(f"  avoid: {e.payload.get('approach', '')[:200]}")
        text = "\n".join(lines)
        return text[:max_chars]


_STOP = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "for",
    "on",
    "is",
    "it",
    "this",
    "that",
    "with",
    "be",
    "as",
    "by",
    "from",
    "at",
    "are",
    "was",
    "were",
    "should",
    "would",
    "could",
    "fix",
    "bug",
}


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", text.lower())
    return {w for w in words if w not in _STOP}
