"""Code execution: local process, Docker sandbox, quality pipeline."""

from aegis.execution.docker import docker_available, run_in_sandbox
from aegis.execution.models import CommandResult, PipelineResult, SandboxResult
from aegis.execution.pipeline import run_quality_pipeline
from aegis.execution.process import run_command

__all__ = [
    "CommandResult",
    "PipelineResult",
    "SandboxResult",
    "docker_available",
    "run_command",
    "run_in_sandbox",
    "run_quality_pipeline",
]
