import json
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

from api.routers.auth import _token_store, get_user_from_token

_LOGIN_PATH = "/v2/auth/login"
_PUBLIC_PREFIXES = ("/v2/docs", "/docs", "/redoc", "/openapi.json")


async def get_current_user(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):]
        return get_user_from_token(token)
    return None


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        if request.method == "POST" and request.url.path == _LOGIN_PATH:
            return await call_next(request)

        if any(request.url.path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):]
            if token in _token_store:
                return await call_next(request)

        return Response(
            content=json.dumps({"detail": "Not authenticated"}),
            status_code=401,
            media_type="application/json",
        )
