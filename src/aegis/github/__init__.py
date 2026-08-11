"""GitHub integration: issues, PRs, clone helpers."""

from aegis.github.client import GitHubClient, GitHubError
from aegis.github.issues import ParsedIssueRef, fetch_issue, parse_issue_ref
from aegis.github.pr import CreatePRResult, create_pull_request

__all__ = [
    "CreatePRResult",
    "GitHubClient",
    "GitHubError",
    "ParsedIssueRef",
    "create_pull_request",
    "fetch_issue",
    "parse_issue_ref",
]
