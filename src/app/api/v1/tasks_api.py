from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Request
from fastcrud.paginated import PaginatedListResponse, compute_offset, paginated_response
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.dependencies import get_current_superuser, get_current_user
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import ForbiddenException, NotFoundException
from ...core.utils.cache import cache
from ...crud.crud_tasks import crud_tasks
from ...schemas.task import TaskCreate, TaskCreateInternal, TaskRead, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


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

    task_read = await crud_tasks.get(
        db=db, id=created_task.id, schema_to_select=TaskRead
    )
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

    response: dict[str, Any] = paginated_response(
        crud_data=tasks_data, page=page, items_per_page=items_per_page
    )
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

    response: dict[str, Any] = paginated_response(
        crud_data=tasks_data, page=page, items_per_page=items_per_page
    )
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

    if (
        not current_user.get("is_superuser")
        and db_task.created_by_user_id != current_user["id"]
    ):
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

    if (
        not current_user.get("is_superuser")
        and db_task.created_by_user_id != current_user["id"]
    ):
        raise ForbiddenException("You don't have permission to update this task")

    updated_task = await crud_tasks.update(db=db, object=values, id=id)
    # TODO: Invalidate cache for get_task and get_my_tasks
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

    if (
        not current_user.get("is_superuser")
        and db_task.created_by_user_id != current_user["id"]
    ):
        raise ForbiddenException("You don't have permission to delete this task")

    await crud_tasks.delete(db=db, id=id)
    # TODO: Invalidate cache


@router.delete(
    "/db/{id}", status_code=204, dependencies=[Depends(get_current_superuser)]
)
async def delete_db_task(
    request: Request,
    id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> None:
    db_task = await crud_tasks.get(db=db, id=id)
    if db_task is None:
        raise NotFoundException("Task not found")

    await crud_tasks.db_delete(db=db, id=id)
    # TODO: Invalidate cache
