"""Lightweight benchmark harness (SWE-bench later)."""

from aegis.benchmark.runner import BenchmarkResult, run_benchmarks
from aegis.benchmark.tasks import BUILTIN_TASKS

__all__ = ["BUILTIN_TASKS", "BenchmarkResult", "run_benchmarks"]
