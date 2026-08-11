"""Minimal GitHub REST API client (httpx)."""

from __future__ import annotations

import os
from typing import Any

import httpx


class GitHubError(RuntimeError):
    """GitHub API or configuration error."""

    def __init__(self, message: str, *, status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body


def resolve_github_token(explicit: str | None = None) -> str | None:
    """Resolve token from explicit value or common env vars."""
    if explicit:
        return explicit.strip() or None
    for key in ("GITHUB_TOKEN", "GH_TOKEN", "AEGIS_GITHUB_TOKEN"):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return None


class GitHubClient:
    """Thin wrapper around GitHub REST API v3."""

    def __init__(
        self,
        token: str | None = None,
        *,
        base_url: str = "https://api.github.com",
        timeout: float = 30.0,
    ) -> None:
        self.token = resolve_github_token(token)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "aegis-engineer",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout, headers=self._headers()) as client:
                resp = client.request(method, url, json=json_body, params=params)
        except httpx.HTTPError as exc:
            raise GitHubError(f"HTTP error: {exc}") from exc

        if resp.status_code >= 400:
            raise GitHubError(
                f"GitHub API {method} {path} → {resp.status_code}",
                status=resp.status_code,
                body=resp.text[:2000],
            )
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, json_body: dict[str, Any], **kwargs: Any) -> Any:
        return self.request("POST", path, json_body=json_body, **kwargs)

    def get_issue(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        data = self.get(f"/repos/{owner}/{repo}/issues/{number}")
        if not isinstance(data, dict):
            raise GitHubError("Unexpected issue response")
        return data

    def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        data = self.get(f"/repos/{owner}/{repo}")
        if not isinstance(data, dict):
            raise GitHubError("Unexpected repo response")
        return data

    def create_pull_request(
        self,
        owner: str,
        repo: str,
        *,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        draft: bool = False,
    ) -> dict[str, Any]:
        if not self.token:
            raise GitHubError(
                "GitHub token required to create PRs "
                "(set GITHUB_TOKEN or GH_TOKEN)"
            )
        data = self.post(
            f"/repos/{owner}/{repo}/pulls",
            {
                "title": title,
                "body": body,
                "head": head,
                "base": base,
                "draft": draft,
            },
        )
        if not isinstance(data, dict):
            raise GitHubError("Unexpected PR response")
        return data

    def whoami(self) -> dict[str, Any] | None:
        if not self.token:
            return None
        data = self.get("/user")
        return data if isinstance(data, dict) else None
