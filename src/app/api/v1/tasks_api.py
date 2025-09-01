from datetime import UTC, datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Request
from fastcrud.paginated import PaginatedListResponse, compute_offset, paginated_response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.dependencies import get_current_superuser, get_current_user
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import ForbiddenException, NotFoundException
from ...core.utils.cache import cache
from ...crud.crud_tasks import crud_tasks
from ...models.task import Task
from ...schemas.task import (
    TaskCreate,
    TaskCreateInternal,
    TaskRead,
    TaskTranslationCreate,
    TaskUpdate,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/next", response_model=TaskRead)
async def get_next_task(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> TaskRead:
    # Check if the user already has a task in progress
    in_progress_task = await crud_tasks.get_multi(db=db, assignee_id=current_user["id"], status="in_progress", limit=1)
    if in_progress_task and in_progress_task["data"]:
        raise ForbiddenException("You already have a task in progress")

    # Use FOR UPDATE SKIP LOCKED to atomically claim a task
    result = await db.execute(
        select(Task).where(Task.status == "pending").order_by(Task.id).limit(1).with_for_update(skip_locked=True)
    )
    task_row = result.scalar_one_or_none()

    if not task_row:
        raise NotFoundException("No available tasks found")

    # Assign the task to the current user atomically
    await crud_tasks.update(
        db=db,
        object=TaskUpdate(
            status="in_progress",
            assignee_id=current_user["id"],
        ),
        id=task_row.id,
    )

    # Fetch the updated task
    updated_task = await crud_tasks.get(db=db, id=task_row.id, schema_to_select=TaskRead)
    if updated_task is None:
        raise NotFoundException("Updated task not found")

    return cast(TaskRead, updated_task)


@router.post("/", response_model=TaskRead, status_code=201)
async def create_task(
    request: Request,
    task: TaskCreate,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> TaskRead:
    task_internal_dict = task.model_dump()
    task_internal_dict["created_by_user_id"] = current_user["id"]

    task_internal = TaskCreateInternal(**task_internal_dict)
    created_task = await crud_tasks.create(db=db, object=task_internal)

    # Handle union type from crud_tasks.create
    if created_task is None:
        raise NotFoundException("Failed to create task")

    # Extract task ID from created_task (could be dict or object)
    task_id = created_task.id if hasattr(created_task, "id") else created_task.get("id")
    if task_id is None:
        raise NotFoundException("Created task has no ID")

    task_read = await crud_tasks.get(db=db, id=task_id, schema_to_select=TaskRead)
    if task_read is None:
        raise NotFoundException("Created task not found")

    return cast(TaskRead, task_read)


@router.get("/", response_model=PaginatedListResponse[TaskRead])
async def get_my_tasks(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
    page: int = 1,
    items_per_page: int = 10,
) -> dict:
    tasks_data = await crud_tasks.get_multi(
        db=db,
        offset=compute_offset(page, items_per_page),
        limit=items_per_page,
        created_by_user_id=current_user["id"],
        is_deleted=False,
    )

    response: dict[str, Any] = paginated_response(crud_data=tasks_data, page=page, items_per_page=items_per_page)
    return response


@router.get("/assigned", response_model=PaginatedListResponse[TaskRead])
async def get_assigned_tasks(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
    page: int = 1,
    items_per_page: int = 10,
) -> dict:
    tasks_data = await crud_tasks.get_multi(
        db=db,
        offset=compute_offset(page, items_per_page),
        limit=items_per_page,
        assignee_id=current_user["id"],
        is_deleted=False,
    )

    response: dict[str, Any] = paginated_response(crud_data=tasks_data, page=page, items_per_page=items_per_page)
    return response


@router.get(
    "/all",
    response_model=PaginatedListResponse[TaskRead],
    dependencies=[Depends(get_current_superuser)],
)
async def get_all_tasks(
    request: Request,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    page: int = 1,
    items_per_page: int = 10,
) -> dict:
    tasks_data = await crud_tasks.get_multi(
        db=db,
        offset=compute_offset(page, items_per_page),
        limit=items_per_page,
        is_deleted=False,
    )

    response: dict[str, Any] = paginated_response(crud_data=tasks_data, page=page, items_per_page=items_per_page)
    return response


@router.get("/{id}", response_model=TaskRead)
@cache(key_prefix="task_{id}", resource_id_name="id")
async def get_task(
    request: Request,
    id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> TaskRead:
    db_task = await crud_tasks.get(db=db, id=id, schema_to_select=TaskRead)
    if db_task is None:
        raise NotFoundException("Task not found")

    # Handle union type for db_task
    created_by_user_id = (
        db_task.created_by_user_id if hasattr(db_task, "created_by_user_id") else db_task.get("created_by_user_id")
    )
    if not current_user.get("is_superuser") and created_by_user_id != current_user["id"]:
        raise ForbiddenException("You don't have permission to access this task")

    return cast(TaskRead, db_task)


@router.patch("/{id}", response_model=TaskRead)
async def update_task(
    request: Request,
    id: int,
    values: TaskUpdate,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> TaskRead:
    db_task = await crud_tasks.get(db=db, id=id)
    if db_task is None:
        raise NotFoundException("Task not found")

    # Handle union type for db_task
    created_by_user_id = (
        db_task.created_by_user_id if hasattr(db_task, "created_by_user_id") else db_task.get("created_by_user_id")
    )
    if not current_user.get("is_superuser") and created_by_user_id != current_user["id"]:
        raise ForbiddenException("You don't have permission to update this task")

    updated_task = await crud_tasks.update(db=db, object=values, id=id)
    # TODO: Invalidate cache for get_task and get_my_tasks
    return cast(TaskRead, updated_task)


@router.post("/{id}/translation", response_model=TaskRead)
async def create_translation(
    request: Request,
    id: int,
    translation: TaskTranslationCreate,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> TaskRead:
    db_task = await crud_tasks.get(db=db, id=id)
    if db_task is None:
        raise NotFoundException("Task not found")

    # Handle union type for db_task indexing
    task_status = db_task.status if hasattr(db_task, "status") else db_task.get("status")
    task_assignee_id = db_task.assignee_id if hasattr(db_task, "assignee_id") else db_task.get("assignee_id")
    if task_status != "in_progress" or task_assignee_id != current_user["id"]:
        raise ForbiddenException("This task is not available for translation")

    await crud_tasks.update(
        db=db,
        object=TaskUpdate(
            **{
                "translated_text": translation.translated_text,
                "status": "completed",
                "translated_by_user_id": current_user["id"],
                "translated_at": datetime.now(UTC),
            }
        ),
        id=id,
    )

    # Fetch the updated task
    updated_task = await crud_tasks.get(db=db, id=id, schema_to_select=TaskRead)
    if updated_task is None:
        raise NotFoundException("Updated task not found")

    return cast(TaskRead, updated_task)


@router.delete("/{id}", status_code=204)
async def delete_task(
    request: Request,
    id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> None:
    db_task = await crud_tasks.get(db=db, id=id)
    if db_task is None:
        raise NotFoundException("Task not found")

    # Handle union type for db_task
    created_by_user_id = (
        db_task.created_by_user_id if hasattr(db_task, "created_by_user_id") else db_task.get("created_by_user_id")
    )
    if not current_user.get("is_superuser") and created_by_user_id != current_user["id"]:
        raise ForbiddenException("You don't have permission to delete this task")

    await crud_tasks.delete(db=db, id=id)
    # TODO: Invalidate cache


# @router.delete(
#     "/db/{id}", status_code=204, dependencies=[Depends(get_current_superuser)]
# )
# async def delete_db_task(
#     request: Request,
#     id: int,
#     db: Annotated[AsyncSession, Depends(async_get_db)],
# ) -> None:
#     db_task = await crud_tasks.get(db=db, id=id)
#     if db_task is None:
#         raise NotFoundException("Task not found")
#
#     await crud_tasks.db_delete(db=db, id=id)
#     # TODO: Invalidate cache
