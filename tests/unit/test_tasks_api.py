"""Unit tests for tasks_api focusing on unique branch coverage.

These complement end-to-end tests in tests/test_tasks.py and
tests/integration/test_tasks_more.py by exercising edge branches
that are awkward to trigger via full integration.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import Request

from src.app.api.v1.tasks_api import (
    get_next_task,
    create_task as create_task_api,
)
from src.app.core.exceptions.http_exceptions import NotFoundException
from src.app.schemas.task import TaskCreate


@pytest.mark.asyncio
async def test_get_next_task_no_available_tasks(mock_db, current_user_dict):
    request = Mock(spec=Request)

    # No task in progress and none available to claim
    from src.app.api.v1 import tasks_api as mod

    mod.crud_tasks.get_multi = AsyncMock(return_value={"data": []})
    mock_result = Mock()
    mock_result.scalar_one_or_none = Mock(return_value=None)
    mock_db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(NotFoundException, match="No available tasks found"):
        await get_next_task(request, current_user_dict, mock_db)


@pytest.mark.asyncio
async def test_create_task_not_found_after_creation(mock_db, current_user_dict, sample_task_data):
    request = Mock(spec=Request)
    task_create = TaskCreate(**sample_task_data)

    from src.app.api.v1 import tasks_api as mod
    mod.crud_tasks.create = AsyncMock(return_value=Mock(id=1))
    mod.crud_tasks.get = AsyncMock(return_value=None)

    with pytest.raises(NotFoundException, match="Created task not found"):
        await create_task_api(request, task_create, current_user_dict, mock_db)
