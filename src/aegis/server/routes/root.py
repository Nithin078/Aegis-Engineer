"""Root landing page for browser visits to the API base URL."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from aegis import __version__
from aegis.server.deps import get_state

_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Aegis Engineer API</title>
  <style>
    :root {{ color-scheme: dark light; font-family: system-ui, sans-serif; }}
    body {{ max-width: 42rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }}
    h1 {{ font-size: 1.5rem; margin-bottom: 0.25rem; }}
    .muted {{ color: #888; font-size: 0.9rem; }}
    code, pre {{ font-family: ui-monospace, monospace; font-size: 0.85rem; }}
    pre {{ background: #1e1e1e; color: #eee; padding: 0.75rem 1rem; border-radius: 8px;
           overflow-x: auto; }}
    a {{ color: #6cb6ff; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: 0.9rem; }}
    th, td {{ text-align: left; padding: 0.4rem 0.5rem; border-bottom: 1px solid #333; }}
    th {{ color: #aaa; font-weight: 600; }}
  </style>
</head>
<body>
  <h1>Aegis Engineer API</h1>
  <p class="muted">v{version} · workspace: <code>{workspace}</code></p>
  <p>This is the <strong>HTTP backend</strong> (REST + SSE), not the TUI yet.
     Use these endpoints or <code>aegis run</code> from the terminal.</p>

  <h2>Quick links</h2>
  <ul>
    <li><a href="/health"><code>GET /health</code></a></li>
    <li><a href="/provider"><code>GET /provider</code></a></li>
  </ul>

  <h2>Main routes</h2>
  <table>
    <tr><th>Method</th><th>Path</th><th>Description</th></tr>
    <tr><td>GET</td><td><code>/health</code></td><td>Liveness check</td></tr>
    <tr><td>POST</td><td><code>/session</code></td><td>Create session</td></tr>
    <tr><td>GET</td><td><code>/session/{{id}}</code></td><td>Session details</td></tr>
    <tr><td>GET</td><td><code>/session/{{id}}/messages</code></td><td>Message history</td></tr>
    <tr><td>POST</td><td><code>/session/{{id}}/chat</code></td><td>Chat (SSE stream)</td></tr>
    <tr><td>POST</td><td><code>/tool/execute</code></td><td>Debug tool run</td></tr>
    <tr><td>GET</td><td><code>/provider</code></td><td>Providers / models</td></tr>
    <tr><td>GET</td><td><code>/events?session_id=</code></td><td>Live event feed</td></tr>
  </table>

  <h2>Try chat (PowerShell)</h2>
  <pre>$base = "http://127.0.0.1:4096"
$s = Invoke-RestMethod -Method Post -Uri "$base/session" `
  -ContentType "application/json" -Body '{{"title":"demo"}}'
$s.id
# Stream chat (curl if available):
curl -N -X POST "$base/session/$($s.id)/chat" `
  -H "Content-Type: application/json" `
  -d '{{"prompt":"Summarize the README","stream":true}}'</pre>

  <p class="muted">Phase 5 will add a terminal UI client. For now, prefer CLI:
  <code>aegis run "…"</code></p>
</body>
</html>
"""


async def root(request: Request) -> HTMLResponse | JSONResponse:
    """Browser-friendly landing page; JSON if Accept prefers application/json."""
    state = get_state(request)
    accept = request.headers.get("accept", "")
    payload = {
        "name": "aegis-engineer",
        "version": __version__,
        "status": "ok",
        "workspace": str(state.workspace),
        "docs": {
            "health": "GET /health",
            "create_session": "POST /session",
            "chat_sse": "POST /session/{id}/chat",
            "providers": "GET /provider",
        },
        "hint": "Open /health or use aegis run from the terminal.",
    }
    if "application/json" in accept and "text/html" not in accept:
        return JSONResponse(payload)

    html = _HTML.format(version=__version__, workspace=state.workspace)
    return HTMLResponse(html)
