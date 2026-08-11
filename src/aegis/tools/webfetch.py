"""Fetch and scrape web pages (HTTP/HTTPS) into readable text."""

from __future__ import annotations

import ipaddress
import re
import socket
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

from pydantic import BaseModel, Field

from aegis.tools.base import ToolContext, ToolDefinition, ToolResult

# Default size cap so agent context stays usable
_DEFAULT_MAX_CHARS = 50_000
_DEFAULT_TIMEOUT = 20.0

_BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "metadata",
    }
)


class _HTMLTextExtractor(HTMLParser):
    """Strip scripts/styles and extract visible text + title + links."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []
        self.title_parts: list[str] = []
        self._in_title = False
        self.links: list[tuple[str, str]] = []  # (href, text)
        self._link_href: str | None = None
        self._link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t in {"script", "style", "noscript", "svg", "template"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if t == "title":
            self._in_title = True
        if t in {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section"}:
            self._parts.append("\n")
        if t == "a":
            href = ""
            for k, v in attrs:
                if k.lower() == "href" and v:
                    href = v
                    break
            self._link_href = href
            self._link_text = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in {"script", "style", "noscript", "svg", "template"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if t == "title":
            self._in_title = False
        if t == "a" and self._link_href is not None:
            text = " ".join("".join(self._link_text).split())
            self.links.append((self._link_href, text))
            self._link_href = None
            self._link_text = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
        if self._link_href is not None:
            self._link_text.append(data)
        self._parts.append(data)

    def text(self) -> str:
        raw = "".join(self._parts)
        # collapse whitespace but keep paragraph breaks
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()

    def title(self) -> str:
        return " ".join("".join(self.title_parts).split()).strip()


def _host_is_blocked(hostname: str) -> bool:
    host = hostname.lower().strip(".")
    if not host:
        return True
    if host in _BLOCKED_HOSTS or host.endswith(".localhost"):
        return True
    # literal IPs
    try:
        ip = ipaddress.ip_address(host)
        return bool(
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        )
    except ValueError:
        pass
    # resolve DNS and check all addresses
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False  # let HTTP client fail later
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
            ):
                return True
        except ValueError:
            continue
    return False


def _validate_url(url: str) -> str | None:
    """Return error message if URL is not allowed, else None."""
    try:
        parsed = urlparse(url)
    except Exception:  # noqa: BLE001
        return "Invalid URL"
    if parsed.scheme not in {"http", "https"}:
        return "Only http and https URLs are allowed"
    if not parsed.hostname:
        return "URL must include a hostname"
    if _host_is_blocked(parsed.hostname):
        return "Refusing to fetch private/local/metadata hosts (SSRF protection)"
    return None


def html_to_text(html: str, *, base_url: str = "") -> dict[str, Any]:
    parser = _HTMLTextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001
        # fall back to crude strip
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return {"title": "", "text": text, "links": []}

    links: list[dict[str, str]] = []
    for href, text in parser.links[:100]:
        abs_url = urljoin(base_url, href) if base_url else href
        if abs_url.startswith(("http://", "https://", "/")):
            links.append({"href": abs_url, "text": text[:200]})
    return {
        "title": parser.title(),
        "text": parser.text(),
        "links": links,
    }


class WebFetchParams(BaseModel):
    url: str = Field(description="HTTP or HTTPS URL to fetch")
    max_chars: int = Field(
        default=_DEFAULT_MAX_CHARS,
        ge=500,
        le=200_000,
        description="Maximum characters of extracted text to return",
    )
    include_links: bool = Field(
        default=False,
        description="If true, append extracted hyperlinks from HTML pages",
    )
    raw: bool = Field(
        default=False,
        description="If true, return raw body (truncated) instead of HTML→text",
    )


class WebFetchTool(ToolDefinition):
    name = "webfetch"
    description = (
        "Fetch a public web page over HTTP/HTTPS and return readable text "
        "(HTML is scraped to plain text). Use for docs, issues, and references. "
        "Does not access private/local network addresses."
    )
    parameters = WebFetchParams
    permissions = ["network"]

    async def execute(self, params: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(params, WebFetchParams)
        url = params.url.strip()
        err = _validate_url(url)
        if err:
            return ToolResult(
                output=err,
                title="blocked",
                error=True,
                metadata={"error_type": "blocked_url", "url": url},
            )

        timeout = min(float(ctx.timeout or _DEFAULT_TIMEOUT), 60.0)
        try:
            import httpx
        except ImportError:
            return ToolResult(
                output="httpx is required for webfetch",
                title="missing dependency",
                error=True,
                metadata={"error_type": "dependency"},
            )

        headers = {
            "User-Agent": "AegisEngineer/0.1 (+https://github.com/Nithin078/Aegis-Engineer)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "text/plain,application/json;q=0.8,*/*;q=0.5",
        }
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                max_redirects=5,
                headers=headers,
            ) as client:
                resp = await client.get(url)
        except httpx.TimeoutException:
            return ToolResult(
                output=f"Request timed out after {timeout}s: {url}",
                title="timeout",
                error=True,
                metadata={"error_type": "timeout", "url": url},
            )
        except httpx.HTTPError as exc:
            return ToolResult(
                output=f"HTTP error fetching {url}: {exc}",
                title="http error",
                error=True,
                metadata={"error_type": "http_error", "url": url},
            )

        final_url = str(resp.url)
        # Re-check host after redirects
        redir_err = _validate_url(final_url)
        if redir_err:
            return ToolResult(
                output=f"Redirect blocked: {redir_err} ({final_url})",
                title="blocked redirect",
                error=True,
                metadata={"error_type": "blocked_redirect", "url": final_url},
            )

        content_type = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
        body = resp.text if resp.encoding else resp.content.decode("utf-8", errors="replace")

        if params.raw or content_type in {
            "application/json",
            "text/plain",
            "text/markdown",
            "application/xml",
            "text/xml",
            "text/csv",
        }:
            text = body
            title = ""
            links: list[dict[str, str]] = []
        elif "html" in content_type or body.lstrip().lower().startswith(
            ("<!doctype", "<html")
        ):
            scraped = html_to_text(body, base_url=final_url)
            title = str(scraped.get("title") or "")
            text = str(scraped.get("text") or "")
            links = list(scraped.get("links") or [])  # type: ignore[arg-type]
        else:
            text = body
            title = ""
            links = []

        truncated = False
        if len(text) > params.max_chars:
            text = text[: params.max_chars] + "\n\n…[truncated]"
            truncated = True

        lines = [
            f"URL: {final_url}",
            f"Status: {resp.status_code}",
            f"Content-Type: {content_type or 'unknown'}",
        ]
        if title:
            lines.append(f"Title: {title}")
        lines.append("")
        lines.append(text)
        if params.include_links and links:
            lines.append("")
            lines.append("## Links")
            for item in links[:40]:
                href = item.get("href", "")
                label = item.get("text") or href
                lines.append(f"- [{label}]({href})")

        ok = 200 <= resp.status_code < 400
        return ToolResult(
            output="\n".join(lines),
            title=title or f"HTTP {resp.status_code}",
            error=not ok,
            metadata={
                "url": final_url,
                "status_code": resp.status_code,
                "content_type": content_type,
                "truncated": truncated,
                "link_count": len(links),
            },
        )


