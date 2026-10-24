import time
from collections import defaultdict

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import get_settings

# Paths that stay public (health + API docs for reviewers).
_PUBLIC_PREFIXES = (
    "/api/v1/health",
    "/api/v1/ready",
    "/api/v1/demo-info",
    "/docs",
    "/redoc",
    "/openapi.json",
)


def _is_public(path: str) -> bool:
    return path == "/" or any(path.startswith(p) for p in _PUBLIC_PREFIXES)


class _RateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self.limit = limit_per_minute
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str) -> bool:
        now = time.time()
        window = now - 60
        self._hits[key] = [t for t in self._hits[key] if t > window]
        if len(self._hits[key]) >= self.limit:
            return False
        self._hits[key].append(now)
        return True


_limiter = _RateLimiter(120)


async def demo_security_middleware(request: Request, call_next):
    settings = get_settings()
    path = request.url.path
    _limiter.limit = settings.rate_limit_per_minute or 120

    if settings.rate_limit_per_minute > 0 and not _is_public(path):
        client = request.client.host if request.client else "unknown"
        if not _limiter.allow(client):
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests; try again in a minute",
                        "retryable": True,
                        "details": None,
                    }
                },
            )

    if settings.demo_api_key and not _is_public(path):
        token = request.headers.get("X-Demo-Token") or request.headers.get("Authorization", "")
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        if token != settings.demo_api_key:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "DEMO_AUTH_REQUIRED",
                        "message": "Send X-Demo-Token or Authorization: Bearer <token>",
                        "retryable": False,
                        "details": None,
                    }
                },
            )

    return await call_next(request)
