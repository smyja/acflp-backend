from __future__ import annotations

import pytest
from fastapi import HTTPException


def _dummy_google_sso_ok(email: str):
    class DummySSO:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def verify_and_process(self, request):  # noqa: ANN001
            class Info:
                def __init__(self, email):
                    self.email = email
                    self.display_name = "D"
                    self.first_name = "F"

            return Info(email)

    return DummySSO()


@pytest.mark.asyncio
async def test_get_google_user_info_success(monkeypatch):
    from src.app.api.v1 import oauth as mod

    # Non-production
    class Env:
        value = "local"

    monkeypatch.setattr(mod, "settings", type("S", (), {"ENVIRONMENT": Env()}))
    monkeypatch.setattr(mod, "google_sso", _dummy_google_sso_ok("ok@example.com"))

    out = await mod.get_google_user_info(object(), db=None)  # type: ignore[arg-type]
    assert out["email"] == "ok@example.com"
    assert out["provider"] == "google"


@pytest.mark.asyncio
async def test__create_oauth_user_generates_unique_username(monkeypatch):
    from src.app.api.v1 import oauth as mod

    # Stub crud calls to simulate username collision then success
    calls = {"get": [], "create": []}

    async def fake_get(db=None, username=None, is_deleted=False):  # noqa: ANN001
        calls["get"].append(username)
        # First check returns truthy (collision), second returns falsy (available)
        return True if len(calls["get"]) == 1 else None

    async def fake_create(db=None, object=None):  # noqa: ANN001
        calls["create"].append(object)
        return object

    monkeypatch.setattr(mod, "crud_users", type("C", (), {"get": fake_get, "create": fake_create}))

    class Info:
        # email base becomes 'a', too short -> default to 'user', then 'user1' due to collision
        email = "a-@example.com"
        display_name = "XX"  # ensure min length for name
        first_name = "YY"

    # Patch password hashing to avoid bcrypt cost
    monkeypatch.setattr(mod, "get_password_hash", lambda _: "hashed")

    await mod._create_oauth_user(db=None, user_info=Info())  # type: ignore[arg-type]
    assert calls["get"][0] == "user" and calls["get"][1] == "user1"
    assert calls["create"], "User create should be called"
