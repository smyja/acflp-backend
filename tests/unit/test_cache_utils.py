from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from unittest.mock import AsyncMock

from src.app.core.utils import cache as cache_mod
from src.app.core.exceptions.cache_exceptions import (
    CacheIdentificationInferenceError,
    InvalidRequestError,
)


class DummyRequest:
    def __init__(self, method: str):
        self.method = method


@pytest.mark.asyncio
async def test_cache_get_miss_stores_and_returns(monkeypatch):
    # Ensure cache client exists from conftest; override get to miss
    assert cache_mod.client is not None
    monkeypatch.setattr(cache_mod.client, "get", AsyncMock(return_value=None))  # type: ignore[attr-defined]

    calls: dict[str, int] = {"count": 0}

    @cache_mod.cache(key_prefix="item", resource_id_name="id", expiration=60)
    async def endpoint(request, id: int):  # noqa: ANN001
        calls["count"] += 1
        return {"id": id, "value": 7}

    out = await endpoint(DummyRequest("GET"), id=42)
    assert out == {"id": 42, "value": 7}
    assert calls["count"] == 1  # computed


@pytest.mark.asyncio
async def test_cache_get_hit_returns_without_calling_func(monkeypatch):
    assert cache_mod.client is not None

    key = "item:5"
    cached_payload = json.dumps({"id": 5, "value": 99}).encode()
    monkeypatch.setattr(cache_mod.client, "get", AsyncMock(return_value=cached_payload))  # type: ignore[attr-defined]

    calls: dict[str, int] = {"count": 0}

    @cache_mod.cache(key_prefix="item", resource_id_name="id")
    async def endpoint(request, id: int):  # noqa: ANN001
        calls["count"] += 1
        return {"id": id, "value": 0}

    out = await endpoint(DummyRequest("GET"), id=5)
    assert out == {"id": 5, "value": 99}
    assert calls["count"] == 0  # skipped underlying call


@pytest.mark.asyncio
async def test_cache_invalidation_on_non_get_with_extra_and_pattern(monkeypatch):
    assert cache_mod.client is not None

    deletes: list[tuple[Any, ...]] = []

    async def fake_delete(*keys):  # noqa: ANN001
        deletes.append(keys)
        return True

    scans = [(-1, [b"a"]), (0, [b"k1", b"k2"])]

    async def fake_scan(cursor, match=None, count=None):  # noqa: ANN001
        # Return last element each time; when 0, loop will end after deleting keys
        return scans.pop() if scans else (0, [])

    monkeypatch.setattr(cache_mod.client, "delete", fake_delete)
    monkeypatch.setattr(cache_mod.client, "scan", fake_scan)

    @cache_mod.cache(
        key_prefix="item_data",
        resource_id_name="item_id",
        to_invalidate_extra={"user_items": "{user_id}"},
        pattern_to_invalidate_extra=["user_{user_id}_items"],
    )
    async def endpoint(request, item_id: int, user_id: int):  # noqa: ANN001
        return {"ok": True}

    # PATCH triggers invalidation paths
    out = await endpoint(DummyRequest("PATCH"), item_id=99, user_id=77)
    assert out == {"ok": True}
    # Base key deletion and extra key deletion executed
    flat_deleted = [k for call in deletes for k in call]
    assert b"user_items:77" in flat_deleted or "user_items:77" in flat_deleted


@pytest.mark.asyncio
async def test_cache_invalid_request_error_on_get_with_invalidation():
    @cache_mod.cache(key_prefix="x", to_invalidate_extra={"y": "{id}"})
    async def endpoint(request, id: int):  # noqa: ANN001
        return {}

    with pytest.raises(InvalidRequestError):
        await endpoint(DummyRequest("GET"), id=1)


def test_infer_resource_id_failure_when_int_and_no_id_key():
    with pytest.raises(CacheIdentificationInferenceError):
        cache_mod._infer_resource_id({"task": 1}, int)  # type: ignore[attr-defined]
