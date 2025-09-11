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

    # Get user's language preferences
    from ...crud.crud_users import crud_users

    user = await crud_users.get(db=db, id=current_user["id"])
    if not user:
        raise NotFoundException("User not found")

    spoken_languages = []
    if hasattr(user, "spoken_languages") and user.spoken_languages:
        spoken_languages = [lang.strip() for lang in user.spoken_languages.split(",")]
    elif user.get("spoken_languages"):
        spoken_languages = [lang.strip() for lang in user["spoken_languages"].split(",")]

    # Build query with language filtering and workload balancing
    query = select(Task).where(Task.status == "pending")

    # If user has specified languages, filter by them
    if spoken_languages:
        query = query.where(Task.source_language.in_(spoken_languages))

    # Prioritize tasks by creation time (older tasks first) for fair distribution
    # Use FOR UPDATE SKIP LOCKED to atomically claim a task
    result = await db.execute(query.order_by(Task.created_at, Task.id).limit(1).with_for_update(skip_locked=True))
    task_row = result.scalar_one_or_none()

    if not task_row:
        # If no tasks found with specified languages, try without language filtering as fallback
        if spoken_languages:
            result = await db.execute(
                select(Task)
                .where(Task.status == "pending")
                .order_by(Task.created_at, Task.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            task_row = result.scalar_one_or_none()

        if not task_row:
            raise NotFoundException("No available tasks found")

    # Assign the task to the current user via CRUD to satisfy test expectations
    await crud_tasks.update(
        db=db,
        id=task_row.id,
        object=TaskUpdate(
            status="in_progress",
            assignee_id=current_user["id"],
        ),
    )

    # Fetch the updated task
    updated_task = await crud_tasks.get(db=db, id=task_row.id, schema_to_select=TaskRead)
    if updated_task is None:
        raise NotFoundException("Updated task not found")

    return cast(TaskRead, updated_task)


@router.patch(
    "/admin/{task_id}/assign/{user_id}", response_model=TaskRead, dependencies=[Depends(get_current_superuser)]
)
async def admin_assign_task(
    request: Request,
    task_id: int,
    user_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> TaskRead:
    """Admin endpoint to manually assign a specific task to a specific user.

    This allows admins to override the automatic language-based assignment
    and manually assign tasks for better workload distribution.
    """
    # Check if task exists and is available
    task = await crud_tasks.get(db=db, id=task_id)
    if not task:
        raise NotFoundException("Task not found")

    task_status = task.status if hasattr(task, "status") else task.get("status")
    if task_status != "pending":
        raise ForbiddenException("Task is not available for assignment")

    # Check if user exists
    from ...crud.crud_users import crud_users

    user_exists = await crud_users.exists(db=db, id=user_id)
    if not user_exists:
        raise NotFoundException("User not found")

    # Check if user already has a task in progress
    in_progress_task = await crud_tasks.get_multi(db=db, assignee_id=user_id, status="in_progress", limit=1)
    if in_progress_task and in_progress_task["data"]:
        raise ForbiddenException("User already has a task in progress")

    # Assign the task
    await crud_tasks.update(
        db=db,
        id=task_id,
        object=TaskUpdate(
            status="in_progress",
            assignee_id=user_id,
        ),
    )

    # Fetch the updated task
    updated_task = await crud_tasks.get(db=db, id=task_id, schema_to_select=TaskRead)
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


# Support both trailing and no-trailing slash for listing
@router.get("", response_model=PaginatedListResponse[TaskRead])
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
    # Exclude soft-deleted tasks from reads
    db_task = await crud_tasks.get(db=db, id=id, is_deleted=False, schema_to_select=TaskRead)
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

    updated_task = await crud_tasks.update(db=db, object=values, id=id, schema_to_select=TaskRead)
    if updated_task is None:
        # Fallback: fetch after update in case the CRUD layer returns None
        updated_task = await crud_tasks.get(db=db, id=id, schema_to_select=TaskRead)
        if updated_task is None:
            raise NotFoundException("Updated task not found")
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
