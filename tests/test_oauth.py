"""Integration-style tests for OAuth endpoints using Postgres Testcontainers.

Mocks are limited to the external Google SSO client; DB and token flows are real.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.responses import RedirectResponse
from httpx import ASGITransport


def _dummy_google_sso(email: str):
    class DummySSO:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get_login_redirect(self):
            return RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth")

        async def verify_and_process(self, request):
            class Info:
                def __init__(self, email: str):
                    self.email = email
                    self.display_name = "OAuth User"
                    self.first_name = "OAuth"

            return Info(email)

    return DummySSO()


async def _create_user(client: httpx.AsyncClient, username: str, email: str, password: str) -> dict:
    payload = {"name": "User", "username": username, "email": email, "password": password}
    resp = await client.post("/api/v1/users/", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.auth
async def test_google_login_redirect(test_app_and_db_pg, monkeypatch):
    app, _ = test_app_and_db_pg
    from src.app.api.v1 import oauth as oauth_mod

    monkeypatch.setattr(oauth_mod, "google_sso", _dummy_google_sso("any@example.com"))

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        resp = await client.get("/api/v1/auth/google/login")
        assert resp.status_code in (302, 307)
        assert str(resp.headers.get("location")).startswith("https://accounts.google.com/")


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.auth
async def test_google_callback_creates_user_and_sets_tokens(test_app_and_db_pg, monkeypatch):
    app, _ = test_app_and_db_pg
    from src.app.api.v1 import oauth as oauth_mod
    monkeypatch.setattr(oauth_mod, "google_sso", _dummy_google_sso("newuser@example.com"))

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        resp = await client.get("/api/v1/auth/google/callback")
        assert resp.status_code in (302, 307)
        assert "auth/callback?token=" in str(resp.headers.get("location"))
        set_cookie = resp.headers.get("set-cookie", "")
        assert "refresh_token=" in set_cookie


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.auth
async def test_google_callback_existing_user(test_app_and_db_pg, monkeypatch):
    app, _ = test_app_and_db_pg
    from src.app.api.v1 import oauth as oauth_mod
    monkeypatch.setattr(oauth_mod, "google_sso", _dummy_google_sso("existing@example.com"))

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        await _create_user(client, "existing", "existing@example.com", "pw!")
        resp = await client.get("/api/v1/auth/google/callback")
        assert resp.status_code in (302, 307)
        assert "auth/callback?token=" in str(resp.headers.get("location"))

