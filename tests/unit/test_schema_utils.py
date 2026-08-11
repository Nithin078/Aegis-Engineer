"""Tests for tool JSON schema sanitization."""

from __future__ import annotations

from pydantic import BaseModel, Field

from aegis.tools.read import ReadTool
from aegis.tools.schema_utils import sanitize_json_schema


class Sample(BaseModel):
    path: str = Field(description="file path")
    limit: int | None = Field(default=None, description="max lines")
    offset: int = Field(default=1, ge=1)


def test_sanitize_removes_anyof_null() -> None:
    raw = Sample.model_json_schema()
    clean = sanitize_json_schema(raw)
    assert clean["type"] == "object"
    assert "anyOf" not in str(clean)
    assert "limit" in clean["properties"]
    assert clean["properties"]["limit"].get("type") == "integer"
    assert "$defs" not in clean
    assert "title" not in clean


def test_read_tool_schema_is_groq_friendly() -> None:
    schema = ReadTool().to_llm_schema()
    assert schema["type"] == "function"
    params = schema["function"]["parameters"]
    assert params["type"] == "object"
    assert "path" in params["properties"]
    assert "anyOf" not in str(params)
    assert "$defs" not in params
