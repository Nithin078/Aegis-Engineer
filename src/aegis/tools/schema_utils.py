"""Simplify Pydantic JSON schemas for picky tool-calling APIs (e.g. Groq)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def sanitize_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a flat, OpenAI/Groq-friendly JSON Schema object.

    Strips ``$defs``/``definitions``, ``title``, ``anyOf`` null unions, and
    other features that cause providers to reject tool definitions or models
    to emit invalid function calls.
    """
    schema = deepcopy(schema)
    defs = schema.pop("$defs", None) or schema.pop("definitions", None) or {}
    cleaned = _clean_node(schema, defs)
    if not isinstance(cleaned, dict):
        return {"type": "object", "properties": {}}
    # Tool parameters must be type object
    cleaned.setdefault("type", "object")
    cleaned.setdefault("properties", {})
    if "additionalProperties" not in cleaned:
        cleaned["additionalProperties"] = False
    # Drop non-standard keys providers dislike
    for key in ("title", "description", "$schema", "$id", "examples", "default"):
        if key == "description":
            continue
        cleaned.pop(key, None)
    cleaned.pop("title", None)
    return cleaned


def _resolve_ref(node: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    ref = node.get("$ref")
    if not ref or not isinstance(ref, str):
        return node
    # "#/$defs/Name" or "#/definitions/Name"
    name = ref.rsplit("/", 1)[-1]
    target = defs.get(name)
    if not isinstance(target, dict):
        return {"type": "object"}
    merged = deepcopy(target)
    # local overrides besides $ref
    for k, v in node.items():
        if k != "$ref":
            merged[k] = v
    return _clean_node(merged, defs)  # type: ignore[return-value]


def _clean_node(node: Any, defs: dict[str, Any]) -> Any:
    if not isinstance(node, dict):
        return node

    if "$ref" in node:
        return _resolve_ref(node, defs)

    # Unwrap optional: anyOf: [{...}, {type: null}]
    if "anyOf" in node or "oneOf" in node:
        variants = node.get("anyOf") or node.get("oneOf") or []
        non_null = [v for v in variants if not (isinstance(v, dict) and v.get("type") == "null")]
        if len(non_null) == 1 and isinstance(non_null[0], dict):
            unwrapped = _clean_node(non_null[0], defs)
            if isinstance(unwrapped, dict):
                for meta in ("description", "default", "title"):
                    if meta in node and meta not in unwrapped:
                        unwrapped[meta] = node[meta]
                unwrapped.pop("title", None)
                return unwrapped
        # fallback: first non-null object-ish
        if non_null:
            return _clean_node(non_null[0], defs)

    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in {"title", "$defs", "definitions", "$schema", "examples"}:
            continue
        if key == "properties" and isinstance(value, dict):
            out[key] = {k: _clean_node(v, defs) for k, v in value.items()}
        elif key == "items":
            out[key] = _clean_node(value, defs)
        elif key == "required" and isinstance(value, list):
            out[key] = [x for x in value if isinstance(x, str)]
        else:
            out[key] = value

    # Ensure required only lists known properties
    props = out.get("properties")
    if isinstance(props, dict) and "required" in out:
        out["required"] = [r for r in out["required"] if r in props]

    return out
