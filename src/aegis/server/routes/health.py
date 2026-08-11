"""Health check."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse

from aegis import __version__


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "version": __version__})
