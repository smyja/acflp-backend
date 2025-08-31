import inspect
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Request
from fastcrud.paginated import PaginatedListResponse, compute_offset, paginated_response
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.dependencies import get_current_superuser, get_current_user
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import DuplicateValueException, ForbiddenException, NotFoundException
from ...core.security import blacklist_token, get_password_hash, oauth2_scheme
from ...crud.crud_users import crud_users
from ...schemas.user import UserCreate, UserCreateInternal, UserRead, UserUpdate

router = APIRouter(tags=["users"])


async def _await_maybe(value):
    return await value if inspect.isawaitable(value) else value


@router.post("/users/", response_model=UserRead, status_code=201)
async def write_user(
    request: Request, user: UserCreate, db: Annotated[AsyncSession, Depends(async_get_db)]
) -> UserRead:
    email_exists = await _await_maybe(crud_users.exists(db=db, email=user.email))
    if email_exists:
        raise DuplicateValueException("Email is already registered")

    username_exists = await _await_maybe(crud_users.exists(db=db, username=user.username))
    if username_exists:
        raise DuplicateValueException("Username not available")

    user_internal_dict = user.model_dump()
    user_internal_dict["hashed_password"] = get_password_hash(password=user_internal_dict["password"])
    del user_internal_dict["password"]

    user_internal = UserCreateInternal(**user_internal_dict)
    created_user = await _await_maybe(crud_users.create(db=db, object=user_internal))

    # Handle union type from crud_users.create
    if created_user is None:
        raise NotFoundException("Failed to create user")

    # Extract user ID from created_user (could be dict or object)
    if hasattr(created_user, "id"):
        user_id = getattr(created_user, "id", None)
    elif isinstance(created_user, dict):
        user_id = created_user.get("id")
    else:
        user_id = None
    if user_id is None:
        raise NotFoundException("Created user has no ID")

    user_read = await _await_maybe(crud_users.get(db=db, id=user_id, schema_to_select=UserRead))
    if user_read is None:
        raise NotFoundException("Created user not found")

    return cast(UserRead, user_read)


@router.get("/users", response_model=PaginatedListResponse[UserRead], dependencies=[Depends(get_current_superuser)])
async def read_users(
    request: Request, db: Annotated[AsyncSession, Depends(async_get_db)], page: int = 1, items_per_page: int = 10
) -> dict:
    users_data = await crud_users.get_multi(
        db=db,
        offset=compute_offset(page, items_per_page),
        limit=items_per_page,
        is_deleted=False,
    )

    response: dict[str, Any] = paginated_response(crud_data=users_data, page=page, items_per_page=items_per_page)
    return response


@router.get("/user/me/", response_model=UserRead)
async def read_users_me(request: Request, current_user: Annotated[dict, Depends(get_current_user)]) -> dict:
    return current_user


@router.get("/user/{username}", response_model=UserRead, dependencies=[Depends(get_current_superuser)])
async def read_user(request: Request, username: str, db: Annotated[AsyncSession, Depends(async_get_db)]) -> UserRead:
    db_user = await crud_users.get(db=db, username=username, is_deleted=False, schema_to_select=UserRead)
    if db_user is None:
        raise NotFoundException("User not found")

    return cast(UserRead, db_user)


@router.patch("/user/{username}")
async def patch_user(
    request: Request,
    values: UserUpdate,
    username: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, str]:
    db_user = await crud_users.get(db=db, username=username, schema_to_select=UserRead)
    if db_user is None:
        raise NotFoundException("User not found")

    db_user = cast(UserRead, db_user)
    if db_user.username != current_user["username"]:
        raise ForbiddenException()

    if values.username != db_user.username:
        existing_username = await crud_users.exists(db=db, username=values.username)
        if existing_username:
            raise DuplicateValueException("Username not available")

    if values.email != db_user.email:
        existing_email = await crud_users.exists(db=db, email=values.email)
        if existing_email:
            raise DuplicateValueException("Email is already registered")

    await crud_users.update(db=db, object=values, username=username)
    return {"message": "User updated"}


@router.delete("/user/{username}")
async def erase_user(
    request: Request,
    username: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
    token: str = Depends(oauth2_scheme),
) -> dict[str, str]:
    db_user = await crud_users.get(db=db, username=username, schema_to_select=UserRead)
    if not db_user:
        raise NotFoundException("User not found")

    if username != current_user["username"]:
        raise ForbiddenException()

    await crud_users.delete(db=db, username=username)
    await blacklist_token(token=token, db=db)
    return {"message": "User deleted"}


# @router.delete("/db_user/{username}", dependencies=[Depends(get_current_superuser)])
# async def erase_db_user(
#     request: Request,
#     username: str,
#     db: Annotated[AsyncSession, Depends(async_get_db)],
#     token: str = Depends(oauth2_scheme),
# ) -> dict[str, str]:
#     db_user = await crud_users.exists(db=db, username=username)
#     if not db_user:
#         raise NotFoundException("User not found")
#
#     await crud_users.db_delete(db=db, username=username)
#     await blacklist_token(token=token, db=db)
#     return {"message": "User deleted from the database"}
