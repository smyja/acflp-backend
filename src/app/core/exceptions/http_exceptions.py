# ruff: noqa
from fastcrud.exceptions.http_exceptions import (
    CustomException,
    BadRequestException,
    NotFoundException,
    ForbiddenException,
    UnauthorizedException,
    UnprocessableEntityException,
    RateLimitException,
)
from fastapi import HTTPException


class DuplicateValueException(HTTPException):
    """Conflict error used across the app for duplicate values.

    Some upstream libraries may surface duplicates as 422. For our API,
    duplicates should map to HTTP 409 to match test expectations.
    """

    def __init__(self, detail: str = "Duplicate value") -> None:
        super().__init__(status_code=409, detail=detail)
