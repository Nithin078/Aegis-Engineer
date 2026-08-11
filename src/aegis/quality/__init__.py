"""Quality gate: secrets, tests, lint, markdown report, push gate."""

from aegis.quality.gate import run_quality_gate
from aegis.quality.models import CheckResult, CheckStatus, GateReport, Verdict

__all__ = [
    "CheckResult",
    "CheckStatus",
    "GateReport",
    "Verdict",
    "run_quality_gate",
]
