"""Lightweight hybrid embeddings (no heavy ML deps).

Uses bag-of-words TF-IDF style vectors over symbol text for semantic-ish
search. Optional: if OPENAI_API_KEY is set, can use provider embeddings later.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from aegis.intelligence.models import CodeLocation, SymbolKind

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]+|[a-z]+|[A-Z][a-z]+")


def tokenize(text: str) -> list[str]:
    """Split identifiers into tokens (snake/camel aware-ish)."""
    raw = _TOKEN_RE.findall(text)
    tokens: list[str] = []
    for t in raw:
        # split snake
        parts = t.split("_")
        for p in parts:
            if not p:
                continue
            # split camel
            sub = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", p)
            if sub:
                tokens.extend(s.lower() for s in sub if s)
            else:
                tokens.append(p.lower())
    return tokens


def symbol_document(sym: CodeLocation) -> str:
    return " ".join(
        [
            sym.symbol_name,
            sym.qualname,
            sym.module,
            sym.file,
            sym.symbol_type.value,
        ]
    )


class TfidfIndex:
    """In-memory TF-IDF over symbol documents."""

    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []  # {id, tokens, meta}
        self.idf: dict[str, float] = {}
        self._built = False

    def add(self, doc_id: str, text: str, meta: dict[str, Any]) -> None:
        tokens = tokenize(text)
        self.docs.append({"id": doc_id, "tokens": tokens, "meta": meta})
        self._built = False

    def build(self) -> None:
        df: Counter[str] = Counter()
        for d in self.docs:
            for t in set(d["tokens"]):
                df[t] += 1
        n = max(len(self.docs), 1)
        self.idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
        self._built = True

    def _vector(self, tokens: list[str]) -> dict[str, float]:
        if not self._built:
            self.build()
        tf: Counter[str] = Counter(tokens)
        total = sum(tf.values()) or 1
        return {
            t: (cnt / total) * self.idf.get(t, 0.0)
            for t, cnt in tf.items()
            if t in self.idf
        }

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(a[t] * b[t] for t in a if t in b)
        na = math.sqrt(sum(v * v for v in a.values())) or 1.0
        nb = math.sqrt(sum(v * v for v in b.values())) or 1.0
        return dot / (na * nb)

    def search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        if not self.docs:
            return []
        if not self._built:
            self.build()
        qv = self._vector(tokenize(query))
        scored: list[tuple[float, dict[str, Any]]] = []
        for d in self.docs:
            dv = self._vector(d["tokens"])
            score = self._cosine(qv, dv)
            if score > 0:
                scored.append((score, d))
        scored.sort(key=lambda x: -x[0])
        out: list[dict[str, Any]] = []
        for score, d in scored[:limit]:
            item = {"score": round(score, 4), "id": d["id"], **d["meta"]}
            out.append(item)
        return out


def build_symbol_tfidf(symbols: list[CodeLocation]) -> TfidfIndex:
    idx = TfidfIndex()
    for s in symbols:
        if s.symbol_type is SymbolKind.MODULE:
            continue
        idx.add(
            s.qualname or s.symbol_name,
            symbol_document(s),
            {
                "qualname": s.qualname,
                "symbol_name": s.symbol_name,
                "symbol_type": s.symbol_type.value,
                "file": s.file,
                "line_start": s.line_start,
                "module": s.module,
            },
        )
    idx.build()
    return idx


def hybrid_search(
    query: str,
    *,
    tfidf: TfidfIndex,
    keyword_hits: list[dict[str, Any]],
    expand_callers: list[dict[str, Any]] | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Merge TF-IDF semantic scores with keyword hits and optional graph neighbors."""
    semantic = tfidf.search(query, limit=limit * 2)
    by_id: dict[str, dict[str, Any]] = {}

    for h in semantic:
        qn = h.get("qualname") or h.get("id") or ""
        by_id[qn] = {**h, "source": "semantic"}

    for h in keyword_hits:
        qn = h.get("qualname") or ""
        score = float(h.get("score") or 1.0) * 0.5  # keyword weight
        if qn in by_id:
            by_id[qn]["score"] = round(float(by_id[qn]["score"]) + score, 4)
            by_id[qn]["source"] = "hybrid"
        else:
            by_id[qn] = {**h, "score": round(score, 4), "source": "keyword"}

    # graph expansion: boost symbols that call/are related
    if expand_callers:
        for c in expand_callers:
            caller = c.get("caller") or ""
            if not caller:
                continue
            if caller in by_id:
                by_id[caller]["score"] = round(float(by_id[caller]["score"]) + 0.15, 4)
                by_id[caller]["source"] = "hybrid+graph"
            else:
                by_id[caller] = {
                    "qualname": caller,
                    "score": 0.15,
                    "source": "graph",
                    "file": c.get("file"),
                    "line_start": c.get("line"),
                }

    ranked = sorted(by_id.values(), key=lambda x: -float(x.get("score") or 0))
    return ranked[:limit]
