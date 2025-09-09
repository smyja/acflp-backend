"""Integration tests for Tasks API endpoints (Postgres Testcontainers)."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import text


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
        "title": overrides.get("title", "Translate this"),
        "text": overrides.get("text", "Hello world"),
        "source_language": overrides.get("source_language", "en"),
        "target_language": overrides.get("target_language", "es"),
        "task_type": overrides.get("task_type", "text_translation"),
    }
    resp = await client.post("/api/v1/tasks/", headers={"Authorization": f"Bearer {token}"}, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.database
async def test_create_list_get_update_delete_task_flow(test_app_and_db_pg):
    app, SessionLocal = test_app_and_db_pg
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        # Seed users
        await _create_user(client, "owner", "owner@example.com", "pw1!")
        await _create_user(client, "viewer", "viewer@example.com", "pw2!")

        owner_token = await _login(client, "owner", "pw1!")
        viewer_token = await _login(client, "viewer", "pw2!")

        # Create a task as owner
        task = await _create_task(client, owner_token)

        # Owner reads own tasks
        resp = await client.get("/api/v1/tasks", headers={"Authorization": f"Bearer {owner_token}"})
        assert resp.status_code == 200
        assert any(t["id"] == task["id"] for t in resp.json()["data"])  # type: ignore[index]

        # Viewer cannot update owner's task
        resp = await client.patch(
            f"/api/v1/tasks/{task['id']}",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"title": "Nope"},
        )
        assert resp.status_code == 403

        # Owner updates task
        resp = await client.patch(
            f"/api/v1/tasks/{task['id']}",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"title": "Updated"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated"

        # Promote owner to superuser and list all tasks
        async with SessionLocal() as session:
            await session.execute(text('UPDATE "user" SET is_superuser = true WHERE username = :u'), {"u": "owner"})
            await session.commit()
        resp = await client.get("/api/v1/tasks/all", headers={"Authorization": f"Bearer {owner_token}"})
        assert resp.status_code == 200

        # Delete task as owner
        resp = await client.delete(f"/api/v1/tasks/{task['id']}", headers={"Authorization": f"Bearer {owner_token}"})
        assert resp.status_code == 204

        # Ensure task is gone
        resp = await client.get(f"/api/v1/tasks/{task['id']}", headers={"Authorization": f"Bearer {owner_token}"})
        assert resp.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.database
async def test_next_and_translation_flow(test_app_and_db_pg):
    app, _ = test_app_and_db_pg
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        # Seed owner and worker
        await _create_user(client, "owner2", "owner2@example.com", "pw1!")
        await _create_user(client, "worker", "worker@example.com", "pw2!")

        owner_token = await _login(client, "owner2", "pw1!")
        worker_token = await _login(client, "worker", "pw2!")

        # Owner creates a pending task
        _ = await _create_task(client, owner_token, title="T1")

        # Worker claims next task
        resp = await client.post("/api/v1/tasks/next", headers={"Authorization": f"Bearer {worker_token}"})
        assert resp.status_code == 200
        claimed = resp.json()
        assert claimed["status"] == "in_progress"
        assert claimed["assignee_id"] is not None

        # Worker completes translation
        resp = await client.post(
            f"/api/v1/tasks/{claimed['id']}/translation",
            headers={"Authorization": f"Bearer {worker_token}"},
            json={"translated_text": "Hola mundo"},
        )
        assert resp.status_code == 200
        finished = resp.json()
        assert finished["status"] == "completed"
        assert finished["translated_text"] == "Hola mundo"

        # Worker sees assigned tasks include the completed task
        resp = await client.get("/api/v1/tasks/assigned", headers={"Authorization": f"Bearer {worker_token}"})
        assert resp.status_code == 200
        assert any(t["id"] == claimed["id"] for t in resp.json()["data"])  # type: ignore[index]

        # Claiming next again should be forbidden due to in-progress/completed state logic
        resp = await client.post("/api/v1/tasks/next", headers={"Authorization": f"Bearer {worker_token}"})
        assert resp.status_code in (403, 404)
