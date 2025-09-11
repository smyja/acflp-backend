from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_verify_token_wrong_type_returns_none(monkeypatch):
    import src.app.core.security as sec

    class Secret:
        def get_secret_value(self):
            return "secret"

    # Solid secret and no blacklist hit
    monkeypatch.setattr(sec, "SECRET_KEY", Secret())
    monkeypatch.setattr(sec, "crud_token_blacklist", type("B", (), {"exists": AsyncMock(return_value=False)}))

    token = await sec.create_refresh_token({"sub": "u"})
    out = await sec.verify_token(token, sec.TokenType.ACCESS, db=None)  # wrong expected type
    assert out is None


@pytest.mark.asyncio
async def test_verify_token_missing_sub_returns_none(monkeypatch):
    import src.app.core.security as sec

    class Secret:
        def get_secret_value(self):
            return "secret"

    monkeypatch.setattr(sec, "SECRET_KEY", Secret())
    monkeypatch.setattr(sec, "crud_token_blacklist", type("B", (), {"exists": AsyncMock(return_value=False)}))

    # token without sub claim
    token = await sec.create_access_token({})
    out = await sec.verify_token(token, sec.TokenType.ACCESS, db=None)
    assert out is None
