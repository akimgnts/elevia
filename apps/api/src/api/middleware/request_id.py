"""
request_id.py — Middleware that stamps every request with a short UUID.

Adds:
  - request.state.request_id  (accessible in route handlers)
  - X-Request-Id response header

Short ID format: first 8 chars of uuid4 hex — enough for correlation in logs.
"""
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = uuid.uuid4().hex[:8]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response
