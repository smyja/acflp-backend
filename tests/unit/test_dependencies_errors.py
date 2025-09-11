from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.app.api import dependencies as deps


class DummyRequest:
    def __init__(self, auth: str | None):
        self.headers = {}
        if auth is not None:
            self.headers["Authorization"] = auth


@pytest.mark.asyncio
async def test_get_optional_user_http_exception_non_401(monkeypatch):
    # Simulate verify_token raising a 500 HTTPException; function should swallow and return None
    async def boom(*args, **kwargs):  # noqa: ANN001, ARG001
        raise HTTPException(status_code=500, detail="err")

    monkeypatch.setattr(deps, "verify_token", boom)
    out = await deps.get_optional_user(DummyRequest("Bearer abc"), db=None)  # type: ignore[arg-type]
    assert out is None


@pytest.mark.asyncio
async def test_get_optional_user_unexpected_exception(monkeypatch):
    async def boom(*args, **kwargs):  # noqa: ANN001, ARG001
        raise ValueError("bad")

    monkeypatch.setattr(deps, "verify_token", boom)
    out = await deps.get_optional_user(DummyRequest("Bearer abc"), db=None)  # type: ignore[arg-type]
    assert out is None
