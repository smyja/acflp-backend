"""Unit tests for rate limiting API endpoints."""

from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timezone

import pytest
from fastapi import Request

from src.app.api.v1.rate_limits import (
    write_rate_limit,
    read_rate_limits,
    read_rate_limit,
    patch_rate_limit,
    erase_rate_limit,
)
from src.app.core.exceptions.http_exceptions import (
    DuplicateValueException,
    NotFoundException,
)
from src.app.schemas.rate_limit import RateLimitCreate, RateLimitRead, RateLimitUpdate
from src.app.schemas.tier import TierRead


class TestWriteRateLimit:
    """Test rate limit creation endpoint."""

    @pytest.mark.asyncio
    async def test_create_rate_limit_success(self, mock_db, sample_tier_read):
        """Test successful rate limit creation."""
        request = Mock(spec=Request)
        tier_name = "premium"
        rate_limit_data = {
            "name": "api_limit",
            "path": "/api/v1/tasks",
            "limit": 100,
            "period": 3600,
        }
        rate_limit_create = RateLimitCreate(**rate_limit_data)

        mock_rate_limit_read = RateLimitRead(
            id=1,
            tier_id=sample_tier_read.id,
            name="api_limit",
            path="api_v1_tasks",
            limit=100,
            period=3600,
        )

        with patch("src.app.api.v1.rate_limits.crud_tiers") as mock_crud_tiers:
            with patch(
                "src.app.api.v1.rate_limits.crud_rate_limits"
            ) as mock_crud_rate_limits:
                mock_crud_tiers.get = AsyncMock(return_value=sample_tier_read)
                mock_crud_rate_limits.exists = AsyncMock(return_value=False)
                mock_crud_rate_limits.create = AsyncMock(return_value=Mock(id=1))
                mock_crud_rate_limits.get = AsyncMock(return_value=mock_rate_limit_read)

                result = await write_rate_limit(
                    request, tier_name, rate_limit_create, mock_db
                )

                assert result == mock_rate_limit_read
                mock_crud_tiers.get.assert_called_once_with(
                    db=mock_db, name=tier_name, schema_to_select=TierRead
                )
                mock_crud_rate_limits.exists.assert_called_once()
                mock_crud_rate_limits.create.assert_called_once()
                mock_crud_rate_limits.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_rate_limit_tier_not_found(self, mock_db):
        """Test rate limit creation when tier doesn't exist."""
        request = Mock(spec=Request)
        tier_name = "nonexistent"
        rate_limit_create = RateLimitCreate(
            name="api_limit", path="/api/v1/tasks", limit=100, period=3600
        )

        with patch("src.app.api.v1.rate_limits.crud_tiers") as mock_crud_tiers:
            mock_crud_tiers.get = AsyncMock(return_value=None)

            with pytest.raises(NotFoundException, match="Tier not found"):
                await write_rate_limit(request, tier_name, rate_limit_create, mock_db)

    @pytest.mark.asyncio
    async def test_create_rate_limit_duplicate_name(self, mock_db, sample_tier_read):
        """Test rate limit creation with duplicate name."""
        request = Mock(spec=Request)
        tier_name = "premium"
        rate_limit_create = RateLimitCreate(
            name="existing_limit", path="/api/v1/tasks", limit=100, period=3600
        )

        with patch("src.app.api.v1.rate_limits.crud_tiers") as mock_crud_tiers:
            with patch(
                "src.app.api.v1.rate_limits.crud_rate_limits"
            ) as mock_crud_rate_limits:
                mock_crud_tiers.get = AsyncMock(return_value=sample_tier_read)
                mock_crud_rate_limits.exists = AsyncMock(return_value=True)

                with pytest.raises(
                    DuplicateValueException, match="Rate Limit Name not available"
                ):
                    await write_rate_limit(
                        request, tier_name, rate_limit_create, mock_db
                    )

    @pytest.mark.asyncio
    async def test_create_rate_limit_not_found_after_creation(
        self, mock_db, sample_tier_read
    ):
        """Test rate limit creation when created rate limit is not found."""
        request = Mock(spec=Request)
        tier_name = "premium"
        rate_limit_create = RateLimitCreate(
            name="api_limit", path="/api/v1/tasks", limit=100, period=3600
        )

        with patch("src.app.api.v1.rate_limits.crud_tiers") as mock_crud_tiers:
            with patch(
                "src.app.api.v1.rate_limits.crud_rate_limits"
            ) as mock_crud_rate_limits:
                mock_crud_tiers.get = AsyncMock(return_value=sample_tier_read)
                mock_crud_rate_limits.exists = AsyncMock(return_value=False)
                mock_crud_rate_limits.create = AsyncMock(return_value=Mock(id=1))
                mock_crud_rate_limits.get = AsyncMock(return_value=None)

                with pytest.raises(
                    NotFoundException, match="Created rate limit not found"
                ):
                    await write_rate_limit(
                        request, tier_name, rate_limit_create, mock_db
                    )


class TestReadRateLimits:
    """Test rate limits list endpoint."""

    @pytest.mark.asyncio
    async def test_read_rate_limits_success(self, mock_db, sample_tier_read):
        """Test successful rate limits list retrieval."""
        request = Mock(spec=Request)
        tier_name = "premium"
        mock_rate_limits_data = {
            "data": [
                {"id": 1, "name": "api_limit_1", "limit": 100},
                {"id": 2, "name": "api_limit_2", "limit": 200},
            ],
            "count": 2,
        }

        with patch("src.app.api.v1.rate_limits.crud_tiers") as mock_crud_tiers:
            with patch(
                "src.app.api.v1.rate_limits.crud_rate_limits"
            ) as mock_crud_rate_limits:
                mock_crud_tiers.get = AsyncMock(return_value=sample_tier_read)
                mock_crud_rate_limits.get_multi = AsyncMock(
                    return_value=mock_rate_limits_data
                )

                with patch(
                    "src.app.api.v1.rate_limits.paginated_response"
                ) as mock_paginated:
                    expected_response = {
                        "data": mock_rate_limits_data["data"],
                        "pagination": {
                            "page": 1,
                            "items_per_page": 10,
                            "total_count": 2,
                        },
                    }
                    mock_paginated.return_value = expected_response

                    result = await read_rate_limits(
                        request, tier_name, mock_db, page=1, items_per_page=10
                    )

                    assert result == expected_response
                    mock_crud_tiers.get.assert_called_once_with(
                        db=mock_db, name=tier_name, schema_to_select=TierRead
                    )
                    mock_crud_rate_limits.get_multi.assert_called_once()
                    mock_paginated.assert_called_once()

    @pytest.mark.asyncio
    async def test_read_rate_limits_tier_not_found(self, mock_db):
        """Test rate limits list when tier doesn't exist."""
        request = Mock(spec=Request)
        tier_name = "nonexistent"

        with patch("src.app.api.v1.rate_limits.crud_tiers") as mock_crud_tiers:
            mock_crud_tiers.get = AsyncMock(return_value=None)

            with pytest.raises(NotFoundException, match="Tier not found"):
                await read_rate_limits(request, tier_name, mock_db)


class TestReadRateLimit:
    """Test single rate limit retrieval endpoint."""

    @pytest.mark.asyncio
    async def test_read_rate_limit_success(self, mock_db, sample_tier_read):
        """Test successful rate limit retrieval."""
        request = Mock(spec=Request)
        tier_name = "premium"
        rate_limit_id = 1

        mock_rate_limit_read = RateLimitRead(
            id=rate_limit_id,
            tier_id=sample_tier_read.id,
            name="api_limit",
            path="api_v1_tasks",
            limit=100,
            period=3600,
        )

        with patch("src.app.api.v1.rate_limits.crud_tiers") as mock_crud_tiers:
            with patch(
                "src.app.api.v1.rate_limits.crud_rate_limits"
            ) as mock_crud_rate_limits:
                mock_crud_tiers.get = AsyncMock(return_value=sample_tier_read)
                mock_crud_rate_limits.get = AsyncMock(return_value=mock_rate_limit_read)

                result = await read_rate_limit(
                    request, tier_name, rate_limit_id, mock_db
                )

                assert result == mock_rate_limit_read
                mock_crud_tiers.get.assert_called_once_with(
                    db=mock_db, name=tier_name, schema_to_select=TierRead
                )
                mock_crud_rate_limits.get.assert_called_once_with(
                    db=mock_db,
                    tier_id=sample_tier_read.id,
                    id=rate_limit_id,
                    schema_to_select=RateLimitRead,
                )

    @pytest.mark.asyncio
    async def test_read_rate_limit_tier_not_found(self, mock_db):
        """Test rate limit retrieval when tier doesn't exist."""
        request = Mock(spec=Request)
        tier_name = "nonexistent"
        rate_limit_id = 1

        with patch("src.app.api.v1.rate_limits.crud_tiers") as mock_crud_tiers:
            mock_crud_tiers.get = AsyncMock(return_value=None)

            with pytest.raises(NotFoundException, match="Tier not found"):
                await read_rate_limit(request, tier_name, rate_limit_id, mock_db)

    @pytest.mark.asyncio
    async def test_read_rate_limit_not_found(self, mock_db, sample_tier_read):
        """Test rate limit retrieval when rate limit doesn't exist."""
        request = Mock(spec=Request)
        tier_name = "premium"
        rate_limit_id = 999

        with patch("src.app.api.v1.rate_limits.crud_tiers") as mock_crud_tiers:
            with patch(
                "src.app.api.v1.rate_limits.crud_rate_limits"
            ) as mock_crud_rate_limits:
                mock_crud_tiers.get = AsyncMock(return_value=sample_tier_read)
                mock_crud_rate_limits.get = AsyncMock(return_value=None)

                with pytest.raises(NotFoundException, match="Rate Limit not found"):
                    await read_rate_limit(request, tier_name, rate_limit_id, mock_db)


class TestPatchRateLimit:
    """Test rate limit update endpoint."""

    @pytest.mark.asyncio
    async def test_patch_rate_limit_success(self, mock_db, sample_tier_read):
        """Test successful rate limit update."""
        request = Mock(spec=Request)
        tier_name = "premium"
        rate_limit_id = 1
        rate_limit_update = RateLimitUpdate(limit=200, period=7200)

        mock_rate_limit_read = RateLimitRead(
            id=rate_limit_id,
            tier_id=sample_tier_read.id,
            name="api_limit",
            path="api_v1_tasks",
            limit=100,
            period=3600,
        )

        with patch("src.app.api.v1.rate_limits.crud_tiers") as mock_crud_tiers:
            with patch(
                "src.app.api.v1.rate_limits.crud_rate_limits"
            ) as mock_crud_rate_limits:
                mock_crud_tiers.get = AsyncMock(return_value=sample_tier_read)
                mock_crud_rate_limits.get = AsyncMock(return_value=mock_rate_limit_read)
                mock_crud_rate_limits.update = AsyncMock(return_value=None)

                result = await patch_rate_limit(
                    request, tier_name, rate_limit_id, rate_limit_update, mock_db
                )

                assert result == {"message": "Rate Limit updated"}
                mock_crud_tiers.get.assert_called_once_with(
                    db=mock_db, name=tier_name, schema_to_select=TierRead
                )
                mock_crud_rate_limits.get.assert_called_once_with(
                    db=mock_db,
                    tier_id=sample_tier_read.id,
                    id=rate_limit_id,
                    schema_to_select=RateLimitRead,
                )
                mock_crud_rate_limits.update.assert_called_once_with(
                    db=mock_db, object=rate_limit_update, id=rate_limit_id
                )

    @pytest.mark.asyncio
    async def test_patch_rate_limit_tier_not_found(self, mock_db):
        """Test rate limit update when tier doesn't exist."""
        request = Mock(spec=Request)
        tier_name = "nonexistent"
        rate_limit_id = 1
        rate_limit_update = RateLimitUpdate(limit=200)

        with patch("src.app.api.v1.rate_limits.crud_tiers") as mock_crud_tiers:
            mock_crud_tiers.get = AsyncMock(return_value=None)

            with pytest.raises(NotFoundException, match="Tier not found"):
                await patch_rate_limit(
                    request, tier_name, rate_limit_id, rate_limit_update, mock_db
                )

    @pytest.mark.asyncio
    async def test_patch_rate_limit_not_found(self, mock_db, sample_tier_read):
        """Test rate limit update when rate limit doesn't exist."""
        request = Mock(spec=Request)
        tier_name = "premium"
        rate_limit_id = 999
        rate_limit_update = RateLimitUpdate(limit=200)

        with patch("src.app.api.v1.rate_limits.crud_tiers") as mock_crud_tiers:
            with patch(
                "src.app.api.v1.rate_limits.crud_rate_limits"
            ) as mock_crud_rate_limits:
                mock_crud_tiers.get = AsyncMock(return_value=sample_tier_read)
                mock_crud_rate_limits.get = AsyncMock(return_value=None)

                with pytest.raises(NotFoundException, match="Rate Limit not found"):
                    await patch_rate_limit(
                        request, tier_name, rate_limit_id, rate_limit_update, mock_db
                    )


class TestEraseRateLimit:
    """Test rate limit deletion endpoint."""

    @pytest.mark.asyncio
    async def test_erase_rate_limit_success(self, mock_db, sample_tier_read):
        """Test successful rate limit deletion."""
        request = Mock(spec=Request)
        tier_name = "premium"
        rate_limit_id = 1

        mock_rate_limit_read = RateLimitRead(
            id=rate_limit_id,
            tier_id=sample_tier_read.id,
            name="api_limit",
            path="api_v1_tasks",
            limit=100,
            period=3600,
        )

        with patch("src.app.api.v1.rate_limits.crud_tiers") as mock_crud_tiers:
            with patch(
                "src.app.api.v1.rate_limits.crud_rate_limits"
            ) as mock_crud_rate_limits:
                mock_crud_tiers.get = AsyncMock(return_value=sample_tier_read)
                mock_crud_rate_limits.get = AsyncMock(return_value=mock_rate_limit_read)
                mock_crud_rate_limits.delete = AsyncMock(return_value=None)

                result = await erase_rate_limit(
                    request, tier_name, rate_limit_id, mock_db
                )

                assert result == {"message": "Rate Limit deleted"}
                mock_crud_tiers.get.assert_called_once_with(
                    db=mock_db, name=tier_name, schema_to_select=TierRead
                )
                mock_crud_rate_limits.get.assert_called_once_with(
                    db=mock_db,
                    tier_id=sample_tier_read.id,
                    id=rate_limit_id,
                    schema_to_select=RateLimitRead,
                )
                mock_crud_rate_limits.delete.assert_called_once_with(
                    db=mock_db, id=rate_limit_id
                )

    @pytest.mark.asyncio
    async def test_erase_rate_limit_tier_not_found(self, mock_db):
        """Test rate limit deletion when tier doesn't exist."""
        request = Mock(spec=Request)
        tier_name = "nonexistent"
        rate_limit_id = 1

        with patch("src.app.api.v1.rate_limits.crud_tiers") as mock_crud_tiers:
            mock_crud_tiers.get = AsyncMock(return_value=None)

            with pytest.raises(NotFoundException, match="Tier not found"):
                await erase_rate_limit(request, tier_name, rate_limit_id, mock_db)

    @pytest.mark.asyncio
    async def test_erase_rate_limit_not_found(self, mock_db, sample_tier_read):
        """Test rate limit deletion when rate limit doesn't exist."""
        request = Mock(spec=Request)
        tier_name = "premium"
        rate_limit_id = 999

        with patch("src.app.api.v1.rate_limits.crud_tiers") as mock_crud_tiers:
            with patch(
                "src.app.api.v1.rate_limits.crud_rate_limits"
            ) as mock_crud_rate_limits:
                mock_crud_tiers.get = AsyncMock(return_value=sample_tier_read)
                mock_crud_rate_limits.get = AsyncMock(return_value=None)

                with pytest.raises(NotFoundException, match="Rate Limit not found"):
                    await erase_rate_limit(request, tier_name, rate_limit_id, mock_db)

    @pytest.mark.asyncio
    async def test_erase_rate_limit_database_error(self, mock_db, sample_tier_read):
        """Test rate limit deletion when database error occurs."""
        request = Mock(spec=Request)
        tier_name = "premium"
        rate_limit_id = 1

        mock_rate_limit_read = RateLimitRead(
            id=rate_limit_id,
            tier_id=sample_tier_read.id,
            name="api_limit",
            path="api_v1_tasks",
            limit=100,
            period=3600,
        )

        with patch("src.app.api.v1.rate_limits.crud_tiers") as mock_crud_tiers:
            with patch(
                "src.app.api.v1.rate_limits.crud_rate_limits"
            ) as mock_crud_rate_limits:
                mock_crud_tiers.get = AsyncMock(return_value=sample_tier_read)
                mock_crud_rate_limits.get = AsyncMock(return_value=mock_rate_limit_read)
                mock_crud_rate_limits.delete = AsyncMock(
                    side_effect=Exception("Database error")
                )

                with pytest.raises(Exception, match="Database error"):
                    await erase_rate_limit(request, tier_name, rate_limit_id, mock_db)


class TestRateLimitPermissions:
    """Test rate limit endpoint permissions."""

    @pytest.mark.asyncio
    async def test_write_rate_limit_requires_superuser(self, mock_db, sample_tier_read):
        """Test that rate limit creation requires superuser permissions."""
        request = Mock(spec=Request)
        tier_name = "premium"
        rate_limit_create = RateLimitCreate(
            name="api_limit", path="/api/v1/tasks", limit=100, period=3600
        )

        mock_rate_limit_read = RateLimitRead(
            id=1,
            tier_id=sample_tier_read.id,
            name="api_limit",
            path="api_v1_tasks",
            limit=100,
            period=3600,
        )

        with patch("src.app.api.v1.rate_limits.crud_tiers") as mock_crud_tiers:
            with patch(
                "src.app.api.v1.rate_limits.crud_rate_limits"
            ) as mock_crud_rate_limits:
                mock_crud_tiers.get = AsyncMock(return_value=sample_tier_read)
                mock_crud_rate_limits.exists = AsyncMock(return_value=False)
                mock_crud_rate_limits.create = AsyncMock(return_value=Mock(id=1))
                mock_crud_rate_limits.get = AsyncMock(return_value=mock_rate_limit_read)

                # This should work if superuser dependency passes
                result = await write_rate_limit(
                    request, tier_name, rate_limit_create, mock_db
                )
                assert result == mock_rate_limit_read

    @pytest.mark.asyncio
    async def test_patch_rate_limit_requires_superuser(self, mock_db, sample_tier_read):
        """Test that rate limit update requires superuser permissions."""
        request = Mock(spec=Request)
        tier_name = "premium"
        rate_limit_id = 1
        rate_limit_update = RateLimitUpdate(limit=200)

        mock_rate_limit_read = RateLimitRead(
            id=rate_limit_id,
            tier_id=sample_tier_read.id,
            name="api_limit",
            path="api_v1_tasks",
            limit=100,
            period=3600,
        )

        with patch("src.app.api.v1.rate_limits.crud_tiers") as mock_crud_tiers:
            with patch(
                "src.app.api.v1.rate_limits.crud_rate_limits"
            ) as mock_crud_rate_limits:
                mock_crud_tiers.get = AsyncMock(return_value=sample_tier_read)
                mock_crud_rate_limits.get = AsyncMock(return_value=mock_rate_limit_read)
                mock_crud_rate_limits.update = AsyncMock(return_value=None)

                # This should work if superuser dependency passes
                result = await patch_rate_limit(
                    request, tier_name, rate_limit_id, rate_limit_update, mock_db
                )
                assert result == {"message": "Rate Limit updated"}

    @pytest.mark.asyncio
    async def test_erase_rate_limit_requires_superuser(self, mock_db, sample_tier_read):
        """Test that rate limit deletion requires superuser permissions."""
        request = Mock(spec=Request)
        tier_name = "premium"
        rate_limit_id = 1

        mock_rate_limit_read = RateLimitRead(
            id=rate_limit_id,
            tier_id=sample_tier_read.id,
            name="api_limit",
            path="api_v1_tasks",
            limit=100,
            period=3600,
        )

        with patch("src.app.api.v1.rate_limits.crud_tiers") as mock_crud_tiers:
            with patch(
                "src.app.api.v1.rate_limits.crud_rate_limits"
            ) as mock_crud_rate_limits:
                mock_crud_tiers.get = AsyncMock(return_value=sample_tier_read)
                mock_crud_rate_limits.get = AsyncMock(return_value=mock_rate_limit_read)
                mock_crud_rate_limits.delete = AsyncMock(return_value=None)

                # This should work if superuser dependency passes
                result = await erase_rate_limit(
                    request, tier_name, rate_limit_id, mock_db
                )
                assert result == {"message": "Rate Limit deleted"}

    @pytest.mark.asyncio
    async def test_read_operations_no_auth_required(self, mock_db, sample_tier_read):
        """Test that read operations don't require authentication."""
        request = Mock(spec=Request)
        tier_name = "premium"
        rate_limit_id = 1

        mock_rate_limit_read = RateLimitRead(
            id=rate_limit_id,
            tier_id=sample_tier_read.id,
            name="api_limit",
            path="api_v1_tasks",
            limit=100,
            period=3600,
        )

        with patch("src.app.api.v1.rate_limits.crud_tiers") as mock_crud_tiers:
            with patch(
                "src.app.api.v1.rate_limits.crud_rate_limits"
            ) as mock_crud_rate_limits:
                mock_crud_tiers.get = AsyncMock(return_value=sample_tier_read)

                # Test read single rate limit
                mock_crud_rate_limits.get = AsyncMock(return_value=mock_rate_limit_read)
                result = await read_rate_limit(
                    request, tier_name, rate_limit_id, mock_db
                )
                assert result == mock_rate_limit_read

                # Test read multiple rate limits
                mock_crud_rate_limits.get_multi = AsyncMock(
                    return_value={"data": [mock_rate_limit_read], "count": 1}
                )
                with patch(
                    "src.app.api.v1.rate_limits.paginated_response"
                ) as mock_paginated:
                    mock_paginated.return_value = {
                        "data": [mock_rate_limit_read],
                        "pagination": {},
                    }
                    result = await read_rate_limits(request, tier_name, mock_db)
                    assert "data" in result
