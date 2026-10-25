"""Per-request agent profile: ``X-Eval-Profile`` header or ``?profile=`` query (default: the active one).

Pure ASGI so the profile stays set for the whole request, streaming responses (SSE) included, and is
inherited by background experiment tasks started during the request."""

from __future__ import annotations

import json
from urllib.parse import parse_qs

from eval_harness.profiles import ProfileNotFound, use_profile

HEADER = b"x-eval-profile"


class ProfileMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        name = dict(scope.get("headers") or []).get(HEADER, b"").decode() or None
        if not name:
            qs = parse_qs(scope.get("query_string", b"").decode())
            name = (qs.get("profile") or [None])[0]
        try:
            ctx = use_profile(name)
            ctx.__enter__()
        except ProfileNotFound as e:
            body = json.dumps({"detail": str(e)}).encode()
            await send({"type": "http.response.start", "status": 400,
                        "headers": [(b"content-type", b"application/json")]})
            await send({"type": "http.response.body", "body": body})
            return
        try:
            await self.app(scope, receive, send)
        finally:
            ctx.__exit__(None, None, None)
