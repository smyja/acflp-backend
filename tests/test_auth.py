"""Integration tests for auth endpoints with Postgres Testcontainers.

These tests exercise the actual FastAPI routes and security code with a
real Postgres database (via Testcontainers) and zero business-logic mocking.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_user(client: httpx.AsyncClient, username: str, email: str, password: str) -> dict[str, Any]:
    payload = {
        "name": "Test User",
        "username": username,
        "email": email,
        "password": password,
    }
    resp = await client.post("/api/v1/users/", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.auth
@pytest.mark.database
async def test_login_refresh_logout_flow(test_app_and_db_pg):
    app, SessionLocal = test_app_and_db_pg

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        # Arrange: create a user through the real endpoint
        await _create_user(client, username="testuser", email="test@example.com", password="testpass123")

        # Act: login with JSON credentials
        login_resp = await client.post("/api/v1/login", json={"username": "testuser", "password": "testpass123"})
        assert login_resp.status_code == 200, login_resp.text
        body = login_resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

        # Assert: refresh token cookie is set and secure/httponly
        set_cookie = login_resp.headers.get("set-cookie", "")
        assert "refresh_token=" in set_cookie
        # Cookie flags may appear in any order; check presence
        assert re.search(r"(?i)httponly", set_cookie)
        assert re.search(r"(?i)secure", set_cookie)

        access_token = body["access_token"]

        # Act: refresh using cookie jar (client keeps cookies)
        refresh_resp = await client.post("/api/v1/refresh")
        assert refresh_resp.status_code == 200, refresh_resp.text
        refreshed = refresh_resp.json()
        assert "access_token" in refreshed
        assert refreshed["token_type"] == "bearer"

        # Act: logout using Authorization header and cookie
        logout_resp = await client.post(
            "/api/v1/logout", headers={"Authorization": f"Bearer {access_token}"}
        )
        assert logout_resp.status_code == 200, logout_resp.text
        assert logout_resp.json()["message"] == "Logged out successfully"

        # Assert: tokens were blacklisted (2 entries)
        async with SessionLocal() as session:
            count = await _count_blacklisted(session)
            assert count == 2


async def _count_blacklisted(session: AsyncSession) -> int:
    from src.app.core.db.token_blacklist import TokenBlacklist

    result = await session.execute(select(TokenBlacklist))
    return len(result.scalars().all())


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.auth
async def test_login_wrong_password_returns_401(test_app_and_db_pg):
    app, _ = test_app_and_db_pg
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        await _create_user(client, username="alice", email="alice@example.com", password="correct-horse")

        resp = await client.post("/api/v1/login", json={"username": "alice", "password": "wrong-battery"})
        assert resp.status_code == 401
        assert "Wrong username, email or password" in resp.text


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.auth
async def test_refresh_missing_cookie_returns_401(test_app_and_db_pg):
    app, _ = test_app_and_db_pg
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        resp = await client.post("/api/v1/refresh")
        assert resp.status_code == 401
        assert "Refresh token missing" in resp.text
