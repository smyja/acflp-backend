from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport


async def _create_user(client: httpx.AsyncClient, username: str, email: str, password: str) -> dict:
    payload = {"name": "User", "username": username, "email": email, "password": password}
    resp = await client.post("/api/v1/users/", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _login(client: httpx.AsyncClient, username: str, password: str) -> str:
    resp = await client.post("/api/v1/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _create_task(client: httpx.AsyncClient, token: str, **overrides) -> dict:
    body = {
        "title": overrides.get("title", "Title"),
        "text": overrides.get("text", "Body"),
        "source_language": overrides.get("source_language", "en"),
        "target_language": overrides.get("target_language", "es"),
        "task_type": overrides.get("task_type", "text_translation"),
    }
    resp = await client.post("/api/v1/tasks/", headers={"Authorization": f"Bearer {token}"}, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_task_forbidden_and_delete_forbidden(test_app_and_db_pg):
    app, _ = test_app_and_db_pg
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        # owner and viewer
        await _create_user(client, "own", "own@example.com", "pw1!")
        await _create_user(client, "view", "view@example.com", "pw2!")
        owner_token = await _login(client, "own", "pw1!")
        viewer_token = await _login(client, "view", "pw2!")

        task = await _create_task(client, owner_token)

        # viewer cannot read owner's task
        r = await client.get(f"/api/v1/tasks/{task['id']}", headers={"Authorization": f"Bearer {viewer_token}"})
        assert r.status_code == 403

        # viewer cannot delete owner's task
        r = await client.delete(f"/api/v1/tasks/{task['id']}", headers={"Authorization": f"Bearer {viewer_token}"})
        assert r.status_code == 403


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_next_task_already_in_progress_forbidden(test_app_and_db_pg):
    app, _ = test_app_and_db_pg
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        await _create_user(client, "ownerx", "ownerx@example.com", "pw1!")
        await _create_user(client, "workerx", "workerx@example.com", "pw2!")
        owner_token = await _login(client, "ownerx", "pw1!")
        worker_token = await _login(client, "workerx", "pw2!")

        # create a pending task
        _ = await _create_task(client, owner_token)

        # worker claims next
        r1 = await client.post("/api/v1/tasks/next", headers={"Authorization": f"Bearer {worker_token}"})
        assert r1.status_code == 200
        # worker tries to claim again without finishing -> forbidden
        r2 = await client.post("/api/v1/tasks/next", headers={"Authorization": f"Bearer {worker_token}"})
        assert r2.status_code == 403

