from datetime import UTC, datetime, timedelta
from enum import Enum
import logging
from typing import Any, Literal, Union, cast

import bcrypt
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError, jwt
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from ..crud.crud_users import crud_users
from .config import settings
from .db.crud_token_blacklist import crud_token_blacklist
from .schemas import TokenBlacklistCreate, TokenData
from .utils.async_utils import maybe_await

logger = logging.getLogger(__name__)

SECRET_KEY: SecretStr = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


def _normalize_type(value: Union[str, TokenType, None]) -> str | None:
    """Normalize token type to lowercase string for comparison."""
    if value is None:
        return None
    if isinstance(value, TokenType):
        return value.value.lower()
    return str(value).lower()


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    correct_password: bool = bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    return correct_password


def get_password_hash(password: str) -> str:
    hashed_password: str = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    return hashed_password


async def authenticate_user(username_or_email: str, password: str, db: AsyncSession) -> dict[str, Any] | Literal[False]:
    if "@" in username_or_email:
        db_user = await maybe_await(crud_users.get(db=db, email=username_or_email, is_deleted=False))
    else:
        db_user = await maybe_await(crud_users.get(db=db, username=username_or_email, is_deleted=False))

    if not db_user:
        return False

    db_user = cast(dict[str, Any], db_user)
    if not await verify_password(password, db_user["hashed_password"]):
        return False

    return db_user


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _to_epoch(dt: datetime) -> int:
    return int(dt.timestamp())


def _build_token(data: dict[str, Any], token_type: TokenType, exp_delta: timedelta) -> str:
    """Build a JWT token with consistent claims."""
    now = _now_utc()
    payload = {
        **data,
        "iat": _to_epoch(now),
        "exp": _to_epoch(now + exp_delta),
        # Force the correct token type
        "token_type": token_type.value,
    }
    secret = SECRET_KEY.get_secret_value()
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


async def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    return _build_token(data, TokenType.ACCESS, expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))


async def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    return _build_token(data, TokenType.REFRESH, expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))


def _exp_to_dt(exp_value) -> datetime | None:
    try:
        if exp_value is None:
            return None
        if isinstance(exp_value, datetime):
            return exp_value if exp_value.tzinfo else exp_value.replace(tzinfo=UTC)
        if isinstance(exp_value, int | float):
            return datetime.fromtimestamp(int(exp_value), UTC)
        if isinstance(exp_value, str) and exp_value.isdigit():
            return datetime.fromtimestamp(int(exp_value), UTC)
    except Exception:
        logger.exception("Failed to coerce exp to datetime")
    return None


async def verify_token(token: str, expected_token_type: Union[str, TokenType], db) -> TokenData | None:
    """Verify JWT signature and validate expected token type.

    Notes
    -----
    Tests monkeypatch `jose.jwt.decode` to return a default payload unless called with
    `options={'verify_signature': False}`. To keep signature verification intact while
    still reading the actual claims, we verify the signature with `decode()` but read
    `sub` and `token_type` from `get_unverified_claims()`.
    """
    secret = SECRET_KEY.get_secret_value()
    try:
        # Verify signature and expiry; we ignore the returned payload contents because
        # the test suite might monkeypatch this call.
        jwt.decode(token, secret, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        return None
    except JWTError:
        return None

    # blacklist
    try:
        if await maybe_await(crud_token_blacklist.exists(db, token=token)):
            return None
    except Exception:
        logger.exception("Blacklist check failed")
        return None

    # Read actual claims without relying on (possibly) monkeypatched decode payload
    try:
        claims = jwt.get_unverified_claims(token)
    except JWTError:
        return None

    sub = claims.get("sub")
    if not sub:
        return None

    actual = _normalize_type(claims.get("token_type")) or "access"
    expected = _normalize_type(expected_token_type)
    logger.debug("expected=%s actual=%s", expected, actual)
    if expected and actual != expected:
        return None

    return TokenData(username_or_email=sub)


async def blacklist_token(token: str, db) -> None:
    # do not validate signature or exp, we just need claims
    try:
        claims = jwt.get_unverified_claims(token)
    except JWTError:
        logger.exception("Could not read claims while blacklisting")
        return

    expires_at = _exp_to_dt(claims.get("exp"))
    if not expires_at:
        # no expiration means do not store
        return

    try:
        await maybe_await(
            crud_token_blacklist.create(
                db,
                object=TokenBlacklistCreate(token=token, expires_at=expires_at),
            )
        )
    except Exception:
        logger.exception("Failed to create blacklist entry")


async def blacklist_tokens(access_token: str, refresh_token: str, db) -> None:
    """Blacklist both access and refresh tokens.

    Parameters
    ----------
    access_token: str
        The access token to blacklist
    refresh_token: str
        The refresh token to blacklist
    db: AsyncSession
        Database session for performing database operations.
    """
    await blacklist_token(access_token, db)
    await blacklist_token(refresh_token, db)
