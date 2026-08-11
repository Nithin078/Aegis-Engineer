"""Phase 9: GitHub issue parsing, client, PR helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from aegis.github.client import GitHubClient, GitHubError, resolve_github_token
from aegis.github.issues import (
    fetch_issue,
    issue_to_text,
    looks_like_issue_ref,
    parse_issue_ref,
)
from aegis.github.pr import build_pr_body, parse_github_remote_url


def test_parse_issue_url() -> None:
    ref = parse_issue_ref("https://github.com/octocat/Hello-World/issues/42")
    assert ref is not None
    assert ref.owner == "octocat"
    assert ref.repo == "Hello-World"
    assert ref.number == 42
    assert "42" in ref.url


def test_parse_issue_short() -> None:
    ref = parse_issue_ref("octocat/Hello-World#7")
    assert ref is not None
    assert ref.number == 7
    assert looks_like_issue_ref("gh:foo/bar#1")
    assert not looks_like_issue_ref("just a regular bug description")


def test_issue_to_text() -> None:
    text = issue_to_text(
        {
            "number": 1,
            "title": "Broken add",
            "body": "add returns wrong value",
            "labels": [{"name": "bug"}],
            "state": "open",
        },
        ref=parse_issue_ref("o/r#1"),
    )
    assert "Broken add" in text
    assert "bug" in text
    assert "add returns" in text


def test_parse_github_remote_url() -> None:
    assert parse_github_remote_url("git@github.com:acme/widget.git") == ("acme", "widget")
    assert parse_github_remote_url("https://github.com/acme/widget.git") == (
        "acme",
        "widget",
    )
    assert parse_github_remote_url("https://gitlab.com/x/y") is None


def test_build_pr_body() -> None:
    body = build_pr_body(
        issue_text="fix me",
        plan_summary="Change operator",
        issue_url="https://github.com/o/r/issues/1",
    )
    assert "Change operator" in body
    assert "Closes:" in body
    assert "Aegis" in body


def test_resolve_github_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("AEGIS_GITHUB_TOKEN", raising=False)
    assert resolve_github_token() is None
    monkeypatch.setenv("GH_TOKEN", "secret")
    assert resolve_github_token() == "secret"
    assert resolve_github_token("explicit") == "explicit"


def test_fetch_issue_mocked() -> None:
    client = MagicMock(spec=GitHubClient)
    client.get_issue.return_value = {
        "number": 99,
        "title": "Bug",
        "body": "details here",
        "labels": [],
        "state": "open",
    }
    ref, data, text = fetch_issue("https://github.com/acme/app/issues/99", client=client)
    assert ref.number == 99
    assert data["title"] == "Bug"
    assert "details here" in text
    client.get_issue.assert_called_once_with("acme", "app", 99)


def test_create_pr_requires_token() -> None:
    client = GitHubClient(token=None)
    with pytest.raises(GitHubError, match="token"):
        client.create_pull_request(
            "o", "r", title="t", body="b", head="branch", base="main"
        )


def test_client_request_error() -> None:
    client = GitHubClient(token="t")
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.text = "not found"
    mock_resp.content = b"not found"

    with patch("httpx.Client") as mock_cls:
        mock_cls.return_value.__enter__.return_value.request.return_value = mock_resp
        with pytest.raises(GitHubError) as ei:
            client.get("/repos/o/r")
        assert ei.value.status == 404
