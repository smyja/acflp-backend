from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.responses import RedirectResponse


@pytest.mark.asyncio
async def test_get_google_user_info_blocked_in_production(monkeypatch):
    from src.app.api.v1 import oauth as mod

    class Env:
        value = "production"

    # Force production environment
    monkeypatch.setattr(mod, "settings", type("S", (), {"ENVIRONMENT": Env()}))

    with pytest.raises(HTTPException) as exc:
        await mod.get_google_user_info(object(), db=None)  # type: ignore[arg-type]
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_google_callback_generic_error_redirects(monkeypatch):
    from src.app.api.v1 import oauth as mod

    dummy = type("D", (), {})
    resp = dummy()

    # Make google_sso raise to trigger error redirect path
    class DummySSO:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def verify_and_process(self, request):  # noqa: ANN001
            raise Exception("boom")

    monkeypatch.setattr(mod, "google_sso", DummySSO())

    out = await mod.google_callback(object(), resp, db=None)  # type: ignore[arg-type]
    assert isinstance(out, RedirectResponse)
    assert "/auth/error" in str(out.headers.get("location"))
