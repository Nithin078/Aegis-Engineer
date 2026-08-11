"""Built-in benchmark task definitions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BenchmarkTask:
    id: str
    name: str
    description: str
    issue: str

    def materialize(self, root: Path) -> Path:
        """Create a fixture workspace for this task. Subclasses override."""
        raise NotImplementedError


@dataclass(frozen=True)
class AddBugTask(BenchmarkTask):
    """Classic buggy add() fixture — tests can fix with mock provider."""

    id: str = "add_bug"
    name: str = "Fix add() subtraction bug"
    description: str = "calc/math_ops.add returns a-b; test expects a+b"
    issue: str = "Fix add in calc/math_ops.py so add(2,3)==5"

    def materialize(self, root: Path) -> Path:
        ws = root / self.id
        (ws / "calc").mkdir(parents=True)
        (ws / "tests").mkdir()
        (ws / "calc" / "__init__.py").write_text("", encoding="utf-8")
        (ws / "calc" / "math_ops.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a - b  # bug\n",
            encoding="utf-8",
        )
        (ws / "tests" / "test_math.py").write_text(
            "from calc.math_ops import add\n\n\n"
            "def test_add():\n    assert add(2, 3) == 5\n",
            encoding="utf-8",
        )
        return ws


BUILTIN_TASKS: dict[str, BenchmarkTask] = {
    "add_bug": AddBugTask(),
}
