"""Parse GitHub issue references and fetch issue bodies."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from aegis.github.client import GitHubClient, GitHubError

# https://github.com/owner/repo/issues/123
# owner/repo#123
# gh:owner/repo#123
_URL_RE = re.compile(
    r"https?://github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)/issues/(?P<number>\d+)",
    re.IGNORECASE,
)
_SHORT_RE = re.compile(
    r"^(?:gh:)?(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)#(?P<number>\d+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedIssueRef:
    owner: str
    repo: str
    number: int
    raw: str

    @property
    def url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}/issues/{self.number}"

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}#{self.number}"


def parse_issue_ref(text: str) -> ParsedIssueRef | None:
    """Return a ParsedIssueRef if *text* looks like a GitHub issue reference."""
    s = text.strip()
    m = _URL_RE.search(s)
    if m:
        return ParsedIssueRef(
            owner=m.group("owner"),
            repo=m.group("repo"),
            number=int(m.group("number")),
            raw=s,
        )
    m = _SHORT_RE.match(s)
    if m:
        return ParsedIssueRef(
            owner=m.group("owner"),
            repo=m.group("repo"),
            number=int(m.group("number")),
            raw=s,
        )
    return None


def looks_like_issue_ref(text: str) -> bool:
    return parse_issue_ref(text) is not None


def issue_to_text(issue: dict[str, Any], *, ref: ParsedIssueRef | None = None) -> str:
    """Normalize a GitHub issue JSON object into agent-readable text."""
    title = str(issue.get("title") or "").strip()
    body = str(issue.get("body") or "").strip()
    number = issue.get("number")
    labels = []
    for lab in issue.get("labels") or []:
        if isinstance(lab, dict) and lab.get("name"):
            labels.append(str(lab["name"]))
        elif isinstance(lab, str):
            labels.append(lab)
    parts = [
        f"# Issue {number}: {title}" if number else f"# {title}",
    ]
    if ref:
        parts.append(f"URL: {ref.url}")
    if labels:
        parts.append(f"Labels: {', '.join(labels)}")
    state = issue.get("state")
    if state:
        parts.append(f"State: {state}")
    parts.append("")
    parts.append(body or "(no description)")
    return "\n".join(parts)


def fetch_issue(
    ref: ParsedIssueRef | str,
    *,
    client: GitHubClient | None = None,
    token: str | None = None,
) -> tuple[ParsedIssueRef, dict[str, Any], str]:
    """
    Fetch issue metadata and a text body suitable for `aegis solve`.

    Returns (ref, raw_json, text).
    """
    if isinstance(ref, str):
        parsed = parse_issue_ref(ref)
        if not parsed:
            raise GitHubError(f"Not a GitHub issue reference: {ref!r}")
        ref = parsed
    gh = client or GitHubClient(token=token)
    data = gh.get_issue(ref.owner, ref.repo, ref.number)
    return ref, data, issue_to_text(data, ref=ref)
