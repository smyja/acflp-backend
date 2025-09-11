from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.app.api import dependencies as deps


class DummyRequest:
    def __init__(self, auth: str | None):
        self.headers = {}
        if auth is not None:
            self.headers["Authorization"] = auth


@pytest.mark.asyncio
async def test_get_optional_user_no_header():
    req = DummyRequest(None)
    out = await deps.get_optional_user(req, db=None)  # type: ignore[arg-type]
    assert out is None


@pytest.mark.asyncio
async def test_get_optional_user_malformed_header():
    req = DummyRequest("Token abc")  # not Bearer
    out = await deps.get_optional_user(req, db=None)  # type: ignore[arg-type]
    assert out is None


@pytest.mark.asyncio
async def test_get_optional_user_valid(monkeypatch):
    # Patch verify_token to return a token data-like object
    class TD:
        username_or_email = "user1"

    monkeypatch.setattr(deps, "verify_token", AsyncMock(return_value=TD()))

    # Patch crud_users.get used by get_current_user
    import src.app.api.dependencies as d2

    monkeypatch.setattr(
        d2, "crud_users", type("C", (), {"get": AsyncMock(return_value={"id": 1, "username": "user1"})})
    )

    req = DummyRequest("Bearer abc")
    out = await deps.get_optional_user(req, db=None)  # type: ignore[arg-type]
    assert out is not None and out["username"] == "user1"
