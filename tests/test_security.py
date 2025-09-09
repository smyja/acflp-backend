"""Focused unit tests for security utilities (minimal mocking).

Integration coverage for token verification and blacklist lives in
tests/integration/test_security_integration.py to avoid heavy mocks.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from jose import jwt
import pytest

from src.app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)


class TestPasswordHashing:
    @pytest.mark.asyncio
    async def test_hash_and_verify_roundtrip(self):
        password = "test_password_123"
        hashed = get_password_hash(password)
        assert hashed != password
        assert hashed.startswith("$2b$")
        assert await verify_password(password, hashed) is True

    @pytest.mark.asyncio
    async def test_hashing_uses_random_salt(self):
        password = "same_password"
        h1 = get_password_hash(password)
        h2 = get_password_hash(password)
        assert h1 != h2
        assert await verify_password(password, h1)
        assert await verify_password(password, h2)

    @pytest.mark.asyncio
    async def test_password_hash_handles_unicode(self):
        password = "пароль123🔒"
        hashed = get_password_hash(password)
        assert await verify_password(password, hashed)


class TestTokenCreation:
    @pytest.mark.asyncio
    async def test_access_token_contains_expected_claims(self, monkeypatch):
        class Secret:
            def get_secret_value(self):
                return "test_secret_key"

        monkeypatch.setattr("src.app.core.security.SECRET_KEY", Secret())

        token = await create_access_token({"sub": "testuser"})
        payload = jwt.decode(token, "test_secret_key", algorithms=["HS256"], options={"verify_signature": False})
        assert payload["sub"] == "testuser"
        assert payload["token_type"] == TokenType.ACCESS.value
        assert isinstance(payload.get("iat"), int)
        assert isinstance(payload.get("exp"), int)

    @pytest.mark.asyncio
    async def test_access_token_custom_expiry(self, monkeypatch):
        class Secret:
            def get_secret_value(self):
                return "test_secret_key"

        monkeypatch.setattr("src.app.core.security.SECRET_KEY", Secret())

        expires = timedelta(hours=2)
        token = await create_access_token({"sub": "u"}, expires)
        payload = jwt.decode(token, "test_secret_key", algorithms=["HS256"], options={"verify_signature": False})
        exp = datetime.fromtimestamp(payload["exp"], UTC)
        now = datetime.now(UTC)
        assert abs((exp - (now + expires)).total_seconds()) < 60

    @pytest.mark.asyncio
    async def test_refresh_token_contains_expected_claims(self, monkeypatch):
        class Secret:
            def get_secret_value(self):
                return "test_secret_key"

        monkeypatch.setattr("src.app.core.security.SECRET_KEY", Secret())

        token = await create_refresh_token({"sub": "testuser"})
        payload = jwt.decode(token, "test_secret_key", algorithms=["HS256"], options={"verify_signature": False})
        assert payload["sub"] == "testuser"
        assert payload["token_type"] == TokenType.REFRESH.value
        assert isinstance(payload.get("exp"), int)

    @pytest.mark.asyncio
    async def test_create_access_token_empty_data(self, monkeypatch):
        class Secret:
            def get_secret_value(self):
                return "test_secret_key"

        monkeypatch.setattr("src.app.core.security.SECRET_KEY", Secret())
        token = await create_access_token({})
        assert isinstance(token, str) and token

