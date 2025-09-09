"""Integration tests for token verification and blacklist using Postgres."""

from __future__ import annotations

from datetime import timedelta

import pytest

from src.app.core.security import (
    TokenType,
    blacklist_token,
    create_access_token,
    create_refresh_token,
    verify_token,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_verify_token_valid_access_end_to_end(test_app_and_db_pg):
    _, SessionLocal = test_app_and_db_pg
    token = await create_access_token({"sub": "alice"})
    async with SessionLocal() as session:
        data = await verify_token(token, TokenType.ACCESS, session)
        assert data is not None
        assert data.username_or_email == "alice"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_verify_token_wrong_type_end_to_end(test_app_and_db_pg):
    _, SessionLocal = test_app_and_db_pg
    token = await create_refresh_token({"sub": "bob"})
    async with SessionLocal() as session:
        data = await verify_token(token, TokenType.ACCESS, session)
        assert data is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_verify_token_expired_end_to_end(test_app_and_db_pg):
    _, SessionLocal = test_app_and_db_pg
    token = await create_access_token({"sub": "carol"}, expires_delta=timedelta(seconds=-1))
    async with SessionLocal() as session:
        data = await verify_token(token, TokenType.ACCESS, session)
        assert data is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_blacklist_flow_end_to_end(test_app_and_db_pg):
    _, SessionLocal = test_app_and_db_pg
    token = await create_access_token({"sub": "dave"})
    async with SessionLocal() as session:
        await blacklist_token(token, session)
        data = await verify_token(token, TokenType.ACCESS, session)
        assert data is None

