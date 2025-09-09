"""Integration tests for user API endpoints (Postgres Testcontainers)."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_user(client: httpx.AsyncClient, username: str, email: str, password: str) -> dict:
    payload = {"name": "User", "username": username, "email": email, "password": password}
    resp = await client.post("/api/v1/users/", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _login(client: httpx.AsyncClient, username: str, password: str) -> str:
    resp = await client.post("/api/v1/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.database
async def test_create_and_get_user_flow(test_app_and_db_pg):
    app, SessionLocal = test_app_and_db_pg
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        # Create two users
        u1 = await _create_user(client, "alice", "alice@example.com", "password1!")
        u2 = await _create_user(client, "bob", "bob@example.com", "password2!")

        # Promote alice to superuser directly in DB
        async with SessionLocal() as session:
            await session.execute(text('UPDATE "user" SET is_superuser = true WHERE username = :u'), {"u": "alice"})
            await session.commit()

        admin_token = await _login(client, "alice", "password1!")

        # Superuser reads a single user
        resp = await client.get(
            f"/api/v1/user/{u2['username']}", headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "bob"

        # Superuser lists users (pagination shape validated by 200)
        resp = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.database
async def test_patch_user_self_update_and_delete_flow(test_app_and_db_pg):
    app, SessionLocal = test_app_and_db_pg
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        await _create_user(client, "charlie", "charlie@example.com", "password3!")
        token = await _login(client, "charlie", "password3!")

        # Self update name
        resp = await client.patch(
            "/api/v1/user/charlie",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Charles"},
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "User updated"

        # Delete self (blacklists token)
        resp = await client.delete("/api/v1/user/charlie", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["message"] == "User deleted"

        # Verify user not readable anymore by superuser
        # Promote a new admin
        await _create_user(client, "admin", "admin@example.com", "adminpass!")
        async with SessionLocal() as session:
            await session.execute(text('UPDATE "user" SET is_superuser = true WHERE username = :u'), {"u": "admin"})
            await session.commit()
        admin_token = await _login(client, "admin", "adminpass!")

        resp = await client.get("/api/v1/user/charlie", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 404

        # Verify one blacklist entry exists for the delete token
        from src.app.core.db.token_blacklist import TokenBlacklist

        async with SessionLocal() as session:
            result = await session.execute(select(TokenBlacklist))
            tokens = result.scalars().all()
            assert len(tokens) >= 1
