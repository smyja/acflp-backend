from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from src.app.api.v1.tasks import create_task, get_task


class TestBackgroundTasksUnit:
    @pytest.mark.asyncio
    async def test_create_task_queue_unavailable(self, monkeypatch):
        from src.app.core.utils import queue

        monkeypatch.setattr(queue, "pool", None)
        with pytest.raises(Exception) as exc:
            await create_task("hello")
        assert "Queue is not available" in str(exc.value)

    @pytest.mark.asyncio
    async def test_create_task_success_path(self, monkeypatch):
        from src.app.core.utils import queue

        mock_pool = Mock()
        mock_pool.enqueue_job = AsyncMock(return_value=Mock(job_id="123"))
        monkeypatch.setattr(queue, "pool", mock_pool)

        result = await create_task("hello")
        assert result == {"id": "123"}

    @pytest.mark.asyncio
    async def test_get_task_queue_unavailable(self, monkeypatch):
        from src.app.core.utils import queue

        monkeypatch.setattr(queue, "pool", None)
        with pytest.raises(Exception) as exc:
            await get_task("abc")
        assert "Queue is not available" in str(exc.value)
