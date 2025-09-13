import typing as t
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from ..core.logging_config import REQUEST_ID_CTX


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assigns/propagates X-Request-ID and injects into log records.

    - If incoming request has `X-Request-ID`, reuse it; otherwise generate a UUID4.
    - Adds the header to the response.
    - Attaches `request_id` to the request state so log records can include it.
    """

    header_name = "X-Request-ID"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = request.headers.get(self.header_name) or str(uuid.uuid4())
        # Attach to request state for route handlers and logging filters
        request.state.request_id = rid

        # Set context var so logs within this request include the request_id
        token = REQUEST_ID_CTX.set(rid)
        try:
            response: Response = await call_next(request)
        finally:
            # Restore previous context
            REQUEST_ID_CTX.reset(token)

        response.headers[self.header_name] = rid
        return response


def log_extra(request: Request, **kwargs: t.Any) -> dict[str, t.Any]:
    """Helper to build logging `extra` with request context.

    Usage:
        logger.info("message", extra=log_extra(request, path=request.url.path))
    """
    extra: dict[str, t.Any] = {"request_id": getattr(request.state, "request_id", None)}
    extra.update(kwargs)
    return extra
