"""Unit tests for task endpoints and background job functionality."""

from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timezone

import pytest
from fastapi import Request, HTTPException
from arq.jobs import Job as ArqJob

from app.api.v1.tasks import create_task, get_task
from app.api.v1.tasks_api import (
    get_next_task, create_task as create_task_api, get_my_tasks, 
    get_assigned_tasks, get_all_tasks, get_task as get_task_api,
    update_task, create_translation, delete_task
)
from app.core.exceptions.http_exceptions import ForbiddenException, NotFoundException
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate, TaskTranslationCreate
from app.schemas.job import Job


class TestBackgroundTasks:
    """Test background task endpoints (tasks.py)."""

    @pytest.mark.asyncio
    async def test_create_background_task_success(self):
        """Test successful background task creation."""
        message = "Test background task message"
        mock_job = Mock()
        mock_job.job_id = "test_job_id_123"
        
        with patch("app.api.v1.tasks.queue") as mock_queue:
            mock_queue.pool = Mock()
            mock_queue.pool.enqueue_job = AsyncMock(return_value=mock_job)
            
            result = await create_task(message)
            
            assert result == {"id": "test_job_id_123"}
            mock_queue.pool.enqueue_job.assert_called_once_with("sample_background_task", message)

    @pytest.mark.asyncio
    async def test_create_background_task_queue_unavailable(self):
        """Test background task creation when queue is unavailable."""
        message = "Test message"
        
        with patch("app.api.v1.tasks.queue") as mock_queue:
            mock_queue.pool = None
            
            with pytest.raises(HTTPException) as exc_info:
                await create_task(message)
            
            assert exc_info.value.status_code == 503
            assert exc_info.value.detail == "Queue is not available"

    @pytest.mark.asyncio
    async def test_create_background_task_failed(self):
        """Test background task creation failure."""
        message = "Test message"
        
        with patch("app.api.v1.tasks.queue") as mock_queue:
            mock_queue.pool = Mock()
            mock_queue.pool.enqueue_job = AsyncMock(return_value=None)
            
            with pytest.raises(HTTPException) as exc_info:
                await create_task(message)
            
            assert exc_info.value.status_code == 500
            assert exc_info.value.detail == "Failed to create task"

    @pytest.mark.asyncio
    async def test_get_background_task_success(self):
        """Test successful background task retrieval."""
        task_id = "test_job_id_123"
        mock_job_info = Mock()
        mock_job_info.__dict__ = {
            "job_id": task_id,
            "status": "complete",
            "result": "Task completed successfully"
        }
        
        with patch("app.api.v1.tasks.queue") as mock_queue:
            mock_queue.pool = Mock()
            
            with patch("app.api.v1.tasks.ArqJob") as mock_arq_job:
                mock_job_instance = Mock()
                mock_job_instance.info = AsyncMock(return_value=mock_job_info)
                mock_arq_job.return_value = mock_job_instance
                
                result = await get_task(task_id)
                
                assert result == mock_job_info.__dict__
                mock_arq_job.assert_called_once_with(task_id, mock_queue.pool)
                mock_job_instance.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_background_task_queue_unavailable(self):
        """Test background task retrieval when queue is unavailable."""
        task_id = "test_job_id_123"
        
        with patch("app.api.v1.tasks.queue") as mock_queue:
            mock_queue.pool = None
            
            with pytest.raises(HTTPException) as exc_info:
                await get_task(task_id)
            
            assert exc_info.value.status_code == 503
            assert exc_info.value.detail == "Queue is not available"

    @pytest.mark.asyncio
    async def test_get_background_task_not_found(self):
        """Test background task retrieval when task is not found."""
        task_id = "nonexistent_job_id"
        
        with patch("app.api.v1.tasks.queue") as mock_queue:
            mock_queue.pool = Mock()
            
            with patch("app.api.v1.tasks.ArqJob") as mock_arq_job:
                mock_job_instance = Mock()
                mock_job_instance.info = AsyncMock(return_value=None)
                mock_arq_job.return_value = mock_job_instance
                
                result = await get_task(task_id)
                
                assert result is None


class TestGetNextTask:
    """Test get next task endpoint."""

    @pytest.mark.asyncio
    async def test_get_next_task_success(self, mock_db, current_user_dict, sample_task_read):
        """Test successful next task retrieval."""
        request = Mock(spec=Request)
        
        with patch("app.api.v1.tasks_api.crud_tasks") as mock_crud:
            # No task in progress
            mock_crud.get_multi = AsyncMock(return_value={"data": []})
            mock_crud.update = AsyncMock(return_value=None)
            mock_crud.get = AsyncMock(return_value=sample_task_read)
            
            # Mock the database execute method
            mock_result = Mock()
            mock_task_row = Mock()
            mock_task_row.id = 1
            mock_result.scalar_one_or_none = Mock(return_value=mock_task_row)
            mock_db.execute = AsyncMock(return_value=mock_result)
            
            result = await get_next_task(request, current_user_dict, mock_db)
            
            assert result == sample_task_read
            mock_crud.update.assert_called_once()
            mock_crud.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_next_task_already_in_progress(self, mock_db, current_user_dict):
        """Test get next task when user already has task in progress."""
        request = Mock(spec=Request)
        
        with patch("app.api.v1.tasks_api.crud_tasks") as mock_crud:
            # User has task in progress
            mock_crud.get_multi = AsyncMock(return_value={"data": [{"id": 1, "status": "in_progress"}]})
            
            with pytest.raises(ForbiddenException, match="You already have a task in progress"):
                await get_next_task(request, current_user_dict, mock_db)

    @pytest.mark.asyncio
    async def test_get_next_task_no_available_tasks(self, mock_db, current_user_dict):
        """Test get next task when no tasks are available."""
        request = Mock(spec=Request)
        
        with patch("app.api.v1.tasks_api.crud_tasks") as mock_crud:
            mock_crud.get_multi = AsyncMock(return_value={"data": []})
            
            # Mock the database execute method to return no tasks
            mock_result = Mock()
            mock_result.scalar_one_or_none = Mock(return_value=None)
            mock_db.execute = AsyncMock(return_value=mock_result)
            
            with pytest.raises(NotFoundException, match="No available tasks found"):
                await get_next_task(request, current_user_dict, mock_db)


class TestCreateTaskAPI:
    """Test task creation API endpoint."""

    @pytest.mark.asyncio
    async def test_create_task_success(self, mock_db, current_user_dict, sample_task_data, sample_task_read):
        """Test successful task creation."""
        request = Mock(spec=Request)
        task_create = TaskCreate(**sample_task_data)
        
        with patch("app.api.v1.tasks_api.crud_tasks") as mock_crud:
            mock_crud.create = AsyncMock(return_value=Mock(id=1))
            mock_crud.get = AsyncMock(return_value=sample_task_read)
            
            result = await create_task_api(request, task_create, current_user_dict, mock_db)
            
            assert result == sample_task_read
            mock_crud.create.assert_called_once()
            mock_crud.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_task_not_found_after_creation(self, mock_db, current_user_dict, sample_task_data):
        """Test task creation when created task is not found."""
        request = Mock(spec=Request)
        task_create = TaskCreate(**sample_task_data)
        
        with patch("app.api.v1.tasks_api.crud_tasks") as mock_crud:
            mock_crud.create = AsyncMock(return_value=Mock(id=1))
            mock_crud.get = AsyncMock(return_value=None)
            
            with pytest.raises(NotFoundException, match="Created task not found"):
                await create_task_api(request, task_create, current_user_dict, mock_db)


class TestGetMyTasks:
    """Test get my tasks endpoint."""

    @pytest.mark.asyncio
    async def test_get_my_tasks_success(self, mock_db, current_user_dict):
        """Test successful my tasks retrieval."""
        request = Mock(spec=Request)
        mock_tasks_data = {"data": [{"id": 1, "title": "My Task"}], "count": 1}
        
        with patch("app.api.v1.tasks_api.crud_tasks") as mock_crud:
            mock_crud.get_multi = AsyncMock(return_value=mock_tasks_data)
            
            with patch("app.api.v1.tasks_api.paginated_response") as mock_paginated:
                expected_response = {"data": [{"id": 1, "title": "My Task"}], "pagination": {}}
                mock_paginated.return_value = expected_response
                
                result = await get_my_tasks(request, current_user_dict, mock_db)
                
                assert result == expected_response
                mock_crud.get_multi.assert_called_once()
                mock_paginated.assert_called_once()


class TestGetAssignedTasks:
    """Test get assigned tasks endpoint."""

    @pytest.mark.asyncio
    async def test_get_assigned_tasks_success(self, mock_db, current_user_dict):
        """Test successful assigned tasks retrieval."""
        request = Mock(spec=Request)
        mock_tasks_data = {"data": [{"id": 1, "title": "Assigned Task"}], "count": 1}
        
        with patch("app.api.v1.tasks_api.crud_tasks") as mock_crud:
            mock_crud.get_multi = AsyncMock(return_value=mock_tasks_data)
            
            with patch("app.api.v1.tasks_api.paginated_response") as mock_paginated:
                expected_response = {"data": [{"id": 1, "title": "Assigned Task"}], "pagination": {}}
                mock_paginated.return_value = expected_response
                
                result = await get_assigned_tasks(request, current_user_dict, mock_db)
                
                assert result == expected_response


class TestGetAllTasks:
    """Test get all tasks endpoint (superuser only)."""

    @pytest.mark.asyncio
    async def test_get_all_tasks_success(self, mock_db):
        """Test successful all tasks retrieval."""
        request = Mock(spec=Request)
        mock_tasks_data = {"data": [{"id": 1}, {"id": 2}], "count": 2}
        
        with patch("app.api.v1.tasks_api.crud_tasks") as mock_crud:
            mock_crud.get_multi = AsyncMock(return_value=mock_tasks_data)
            
            with patch("app.api.v1.tasks_api.paginated_response") as mock_paginated:
                expected_response = {"data": [{"id": 1}, {"id": 2}], "pagination": {}}
                mock_paginated.return_value = expected_response
                
                result = await get_all_tasks(request, mock_db)
                
                assert result == expected_response


class TestGetTaskAPI:
    """Test get single task API endpoint."""

    @pytest.mark.asyncio
    async def test_get_task_success_owner(self, mock_db, current_user_dict, sample_task_read):
        """Test successful task retrieval by owner."""
        request = Mock(spec=Request)
        task_id = 1
        sample_task_read.created_by_user_id = current_user_dict["id"]
        
        with patch("app.api.v1.tasks_api.crud_tasks") as mock_crud:
            mock_crud.get = AsyncMock(return_value=sample_task_read)
            
            result = await get_task_api(request, id=task_id, current_user=current_user_dict, db=mock_db)
            
            assert result == sample_task_read

    @pytest.mark.asyncio
    async def test_get_task_success_superuser(self, mock_db, superuser_dict, sample_task_read):
        """Test successful task retrieval by superuser."""
        request = Mock(spec=Request)
        task_id = 1
        sample_task_read.created_by_user_id = 999  # Different user
        
        with patch("app.api.v1.tasks_api.crud_tasks") as mock_crud:
            mock_crud.get = AsyncMock(return_value=sample_task_read)
            
            result = await get_task_api(request, id=task_id, current_user=superuser_dict, db=mock_db)
            
            assert result == sample_task_read

    @pytest.mark.asyncio
    async def test_get_task_forbidden(self, mock_db, current_user_dict, sample_task_read):
        """Test task retrieval forbidden for non-owner."""
        request = Mock(spec=Request)
        task_id = 1
        sample_task_read.created_by_user_id = 999  # Different user
        current_user_dict["is_superuser"] = False
        
        with patch("app.api.v1.tasks_api.crud_tasks") as mock_crud:
            mock_crud.get = AsyncMock(return_value=sample_task_read)
            
            with pytest.raises(ForbiddenException):
                await get_task_api(request, id=task_id, current_user=current_user_dict, db=mock_db)

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, mock_db, current_user_dict):
        """Test task retrieval when task doesn't exist."""
        request = Mock(spec=Request)
        task_id = 999
        
        with patch("app.api.v1.tasks_api.crud_tasks") as mock_crud:
            mock_crud.get = AsyncMock(return_value=None)
            
            with pytest.raises(NotFoundException, match="Task not found"):
                await get_task_api(request, id=task_id, current_user=current_user_dict, db=mock_db)


class TestUpdateTask:
    """Test task update endpoint."""

    @pytest.mark.asyncio
    async def test_update_task_success(self, mock_db, current_user_dict, sample_task_read):
        """Test successful task update."""
        request = Mock(spec=Request)
        task_id = 1
        task_update = TaskUpdate(title="Updated Task Title")
        sample_task_read.created_by_user_id = current_user_dict["id"]
        
        # Create a mock task object with the correct attribute
        mock_task = Mock()
        mock_task.created_by_user_id = current_user_dict["id"]
        
        with patch("app.api.v1.tasks_api.crud_tasks") as mock_crud:
            mock_crud.get = AsyncMock(return_value=mock_task)
            mock_crud.update = AsyncMock(return_value=sample_task_read)
            
            result = await update_task(request, task_id, task_update, current_user_dict, mock_db)
            
            assert result == sample_task_read
            mock_crud.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_task_forbidden(self, mock_db, current_user_dict):
        """Test task update forbidden for non-owner."""
        request = Mock(spec=Request)
        task_id = 1
        task_update = TaskUpdate(title="Updated Task Title")
        current_user_dict["is_superuser"] = False
        
        # Create a mock task object with different owner
        mock_task = Mock()
        mock_task.created_by_user_id = 999
        
        with patch("app.api.v1.tasks_api.crud_tasks") as mock_crud:
            mock_crud.get = AsyncMock(return_value=mock_task)
            
            with pytest.raises(ForbiddenException):
                await update_task(request, task_id, task_update, current_user_dict, mock_db)


class TestCreateTranslation:
    """Test create translation endpoint."""

    @pytest.mark.asyncio
    async def test_create_translation_success(self, mock_db, current_user_dict, sample_task_read):
        """Test successful translation creation."""
        request = Mock(spec=Request)
        task_id = 1
        translation = TaskTranslationCreate(translated_text="Translated content")
        
        with patch("app.api.v1.tasks_api.crud_tasks") as mock_crud:
            mock_crud.get = AsyncMock(side_effect=[
                {"status": "in_progress", "assignee_id": current_user_dict["id"]},
                sample_task_read
            ])
            mock_crud.update = AsyncMock(return_value=None)
            
            result = await create_translation(request, task_id, translation, current_user_dict, mock_db)
            
            assert result == sample_task_read
            mock_crud.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_translation_forbidden_wrong_assignee(self, mock_db, current_user_dict):
        """Test translation creation forbidden for wrong assignee."""
        request = Mock(spec=Request)
        task_id = 1
        translation = TaskTranslationCreate(translated_text="Translated content")
        
        with patch("app.api.v1.tasks_api.crud_tasks") as mock_crud:
            mock_crud.get = AsyncMock(return_value={"status": "in_progress", "assignee_id": 999})
            
            with pytest.raises(ForbiddenException):
                await create_translation(request, task_id, translation, current_user_dict, mock_db)

    @pytest.mark.asyncio
    async def test_create_translation_forbidden_wrong_status(self, mock_db, current_user_dict):
        """Test translation creation forbidden for wrong status."""
        request = Mock(spec=Request)
        task_id = 1
        translation = TaskTranslationCreate(translated_text="Translated content")
        
        with patch("app.api.v1.tasks_api.crud_tasks") as mock_crud:
            mock_crud.get = AsyncMock(return_value={"status": "pending", "assignee_id": current_user_dict["id"]})
            
            with pytest.raises(ForbiddenException):
                await create_translation(request, task_id, translation, current_user_dict, mock_db)


class TestDeleteTask:
    """Test task deletion endpoint."""

    @pytest.mark.asyncio
    async def test_delete_task_success(self, mock_db, current_user_dict):
        """Test successful task deletion."""
        request = Mock(spec=Request)
        task_id = 1
        
        # Create a mock task object with the correct attribute
        mock_task = Mock()
        mock_task.created_by_user_id = current_user_dict["id"]
        
        with patch("app.api.v1.tasks_api.crud_tasks") as mock_crud:
            mock_crud.get = AsyncMock(return_value=mock_task)
            mock_crud.delete = AsyncMock(return_value=None)
            
            result = await delete_task(request, task_id, current_user_dict, mock_db)
            
            assert result is None
            mock_crud.delete.assert_called_once_with(db=mock_db, id=task_id)

    @pytest.mark.asyncio
    async def test_delete_task_forbidden(self, mock_db, current_user_dict):
        """Test task deletion forbidden for non-owner."""
        request = Mock(spec=Request)
        task_id = 1
        current_user_dict["is_superuser"] = False
        
        # Create a mock task object with different owner
        mock_task = Mock()
        mock_task.created_by_user_id = 999
        
        with patch("app.api.v1.tasks_api.crud_tasks") as mock_crud:
            mock_crud.get = AsyncMock(return_value=mock_task)
            
            with pytest.raises(ForbiddenException):
                await delete_task(request, task_id, current_user_dict, mock_db)

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self, mock_db, current_user_dict):
        """Test task deletion when task doesn't exist."""
        request = Mock(spec=Request)
        task_id = 999
        
        with patch("app.api.v1.tasks_api.crud_tasks") as mock_crud:
            mock_crud.get = AsyncMock(return_value=None)
            
            with pytest.raises(NotFoundException, match="Task not found"):
                await delete_task(request, task_id, current_user_dict, mock_db)