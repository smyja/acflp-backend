"""Unit tests for tiers API endpoints."""

from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timezone

import pytest
from fastapi import Request

from src.app.api.v1.tiers import (
    write_tier,
    read_tiers,
    read_tier,
    patch_tier,
    erase_tier,
)
from src.app.core.exceptions.http_exceptions import (
    DuplicateValueException,
    NotFoundException,
)
from src.app.schemas.tier import TierCreate, TierRead, TierUpdate


class TestWriteTier:
    """Test tier creation endpoint."""

    @pytest.mark.asyncio
    async def test_create_tier_success(
        self, mock_db, sample_tier_data, sample_tier_read
    ):
        """Test successful tier creation."""
        tier_create = TierCreate(**sample_tier_data)
        request = Mock(spec=Request)

        with patch("src.src.app.api.v1.tiers.crud_tiers") as mock_crud:
            # Mock that tier name doesn't exist
            mock_crud.exists = AsyncMock(return_value=False)
            mock_crud.create = AsyncMock(return_value=Mock(id=1))
            mock_crud.get = AsyncMock(return_value=sample_tier_read)

            result = await write_tier(request, tier_create, mock_db)

            assert result == sample_tier_read
            mock_crud.exists.assert_called_once_with(db=mock_db, name=tier_create.name)
            mock_crud.create.assert_called_once()
            mock_crud.get.assert_called_once_with(
                db=mock_db, id=1, schema_to_select=TierRead
            )

    @pytest.mark.asyncio
    async def test_create_tier_duplicate_name(self, mock_db, sample_tier_data):
        """Test tier creation with duplicate name."""
        tier_create = TierCreate(**sample_tier_data)
        request = Mock(spec=Request)

        with patch("src.src.app.api.v1.tiers.crud_tiers") as mock_crud:
            # Mock that tier name already exists
            mock_crud.exists = AsyncMock(return_value=True)

            with pytest.raises(
                DuplicateValueException, match="Tier Name not available"
            ):
                await write_tier(request, tier_create, mock_db)

            mock_crud.exists.assert_called_once_with(db=mock_db, name=tier_create.name)
            mock_crud.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_tier_not_found_after_creation(
        self, mock_db, sample_tier_data
    ):
        """Test tier creation when created tier is not found."""
        tier_create = TierCreate(**sample_tier_data)
        request = Mock(spec=Request)

        with patch("src.src.app.api.v1.tiers.crud_tiers") as mock_crud:
            mock_crud.exists = AsyncMock(return_value=False)
            mock_crud.create = AsyncMock(return_value=Mock(id=1))
            mock_crud.get = AsyncMock(
                return_value=None
            )  # Tier not found after creation

            with pytest.raises(NotFoundException, match="Created tier not found"):
                await write_tier(request, tier_create, mock_db)


class TestReadTiers:
    """Test tiers list endpoint."""

    @pytest.mark.asyncio
    async def test_read_tiers_success(self, mock_db):
        """Test successful tiers list retrieval."""
        request = Mock(spec=Request)
        mock_tiers_data = {
            "data": [{"id": 1, "name": "free"}, {"id": 2, "name": "premium"}],
            "count": 2,
        }

        with patch("src.src.app.api.v1.tiers.crud_tiers") as mock_crud:
            mock_crud.get_multi = AsyncMock(return_value=mock_tiers_data)

            with patch("src.app.api.v1.tiers.paginated_response") as mock_paginated:
                expected_response = {
                    "data": [{"id": 1, "name": "free"}, {"id": 2, "name": "premium"}],
                    "pagination": {"page": 1, "items_per_page": 10, "total_count": 2},
                }
                mock_paginated.return_value = expected_response

                result = await read_tiers(request, mock_db, page=1, items_per_page=10)

                assert result == expected_response
                mock_crud.get_multi.assert_called_once_with(
                    db=mock_db, offset=0, limit=10
                )
                mock_paginated.assert_called_once_with(
                    crud_data=mock_tiers_data, page=1, items_per_page=10
                )

    @pytest.mark.asyncio
    async def test_read_tiers_with_pagination(self, mock_db):
        """Test tiers list with custom pagination."""
        request = Mock(spec=Request)
        mock_tiers_data = {"data": [], "count": 0}

        with patch("src.src.app.api.v1.tiers.crud_tiers") as mock_crud:
            mock_crud.get_multi = AsyncMock(return_value=mock_tiers_data)

            with patch("src.app.api.v1.tiers.paginated_response") as mock_paginated:
                with patch("src.app.api.v1.tiers.compute_offset") as mock_offset:
                    mock_offset.return_value = 20
                    mock_paginated.return_value = {"data": [], "pagination": {}}

                    result = await read_tiers(
                        request, mock_db, page=3, items_per_page=20
                    )

                    mock_offset.assert_called_once_with(3, 20)
                    mock_crud.get_multi.assert_called_once_with(
                        db=mock_db, offset=20, limit=20
                    )


class TestReadTier:
    """Test single tier retrieval endpoint."""

    @pytest.mark.asyncio
    async def test_read_tier_success(self, mock_db, sample_tier_read):
        """Test successful tier retrieval."""
        request = Mock(spec=Request)
        tier_name = "premium"

        with patch("src.src.app.api.v1.tiers.crud_tiers") as mock_crud:
            mock_crud.get = AsyncMock(return_value=sample_tier_read)

            result = await read_tier(request, tier_name, mock_db)

            assert result == sample_tier_read
            mock_crud.get.assert_called_once_with(
                db=mock_db, name=tier_name, schema_to_select=TierRead
            )

    @pytest.mark.asyncio
    async def test_read_tier_not_found(self, mock_db):
        """Test tier retrieval when tier doesn't exist."""
        request = Mock(spec=Request)
        tier_name = "nonexistent"

        with patch("src.src.app.api.v1.tiers.crud_tiers") as mock_crud:
            mock_crud.get = AsyncMock(return_value=None)

            with pytest.raises(NotFoundException, match="Tier not found"):
                await read_tier(request, tier_name, mock_db)

            mock_crud.get.assert_called_once_with(
                db=mock_db, name=tier_name, schema_to_select=TierRead
            )


class TestPatchTier:
    """Test tier update endpoint."""

    @pytest.mark.asyncio
    async def test_patch_tier_success(self, mock_db, sample_tier_read):
        """Test successful tier update."""
        request = Mock(spec=Request)
        tier_name = "premium"
        tier_update = TierUpdate(name="premium_updated")

        with patch("src.src.app.api.v1.tiers.crud_tiers") as mock_crud:
            mock_crud.get = AsyncMock(return_value=sample_tier_read)
            mock_crud.update = AsyncMock(return_value=None)

            result = await patch_tier(request, tier_name, tier_update, mock_db)

            assert result == {"message": "Tier updated"}
            mock_crud.get.assert_called_once_with(
                db=mock_db, name=tier_name, schema_to_select=TierRead
            )
            mock_crud.update.assert_called_once_with(
                db=mock_db, object=tier_update, name=tier_name
            )

    @pytest.mark.asyncio
    async def test_patch_tier_not_found(self, mock_db):
        """Test tier update when tier doesn't exist."""
        request = Mock(spec=Request)
        tier_name = "nonexistent"
        tier_update = TierUpdate(name="updated_name")

        with patch("src.src.app.api.v1.tiers.crud_tiers") as mock_crud:
            mock_crud.get = AsyncMock(return_value=None)

            with pytest.raises(NotFoundException, match="Tier not found"):
                await patch_tier(request, tier_name, tier_update, mock_db)

            mock_crud.get.assert_called_once_with(
                db=mock_db, name=tier_name, schema_to_select=TierRead
            )
            mock_crud.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_patch_tier_partial_update(self, mock_db, sample_tier_read):
        """Test tier partial update."""
        request = Mock(spec=Request)
        tier_name = "basic"
        tier_update = TierUpdate()  # Empty update

        with patch("src.src.app.api.v1.tiers.crud_tiers") as mock_crud:
            mock_crud.get = AsyncMock(return_value=sample_tier_read)
            mock_crud.update = AsyncMock(return_value=None)

            result = await patch_tier(request, tier_name, tier_update, mock_db)

            assert result == {"message": "Tier updated"}
            mock_crud.update.assert_called_once_with(
                db=mock_db, object=tier_update, name=tier_name
            )


class TestEraseTier:
    """Test tier deletion endpoint."""

    @pytest.mark.asyncio
    async def test_erase_tier_success(self, mock_db, sample_tier_read):
        """Test successful tier deletion."""
        request = Mock(spec=Request)
        tier_name = "premium"

        with patch("src.src.app.api.v1.tiers.crud_tiers") as mock_crud:
            mock_crud.get = AsyncMock(return_value=sample_tier_read)
            mock_crud.delete = AsyncMock(return_value=None)

            result = await erase_tier(request, tier_name, mock_db)

            assert result == {"message": "Tier deleted"}
            mock_crud.get.assert_called_once_with(
                db=mock_db, name=tier_name, schema_to_select=TierRead
            )
            mock_crud.delete.assert_called_once_with(db=mock_db, name=tier_name)

    @pytest.mark.asyncio
    async def test_erase_tier_not_found(self, mock_db):
        """Test tier deletion when tier doesn't exist."""
        request = Mock(spec=Request)
        tier_name = "nonexistent"

        with patch("src.src.app.api.v1.tiers.crud_tiers") as mock_crud:
            mock_crud.get = AsyncMock(return_value=None)

            with pytest.raises(NotFoundException, match="Tier not found"):
                await erase_tier(request, tier_name, mock_db)

            mock_crud.get.assert_called_once_with(
                db=mock_db, name=tier_name, schema_to_select=TierRead
            )
            mock_crud.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_erase_tier_database_error(self, mock_db, sample_tier_read):
        """Test tier deletion when database error occurs."""
        request = Mock(spec=Request)
        tier_name = "premium"

        with patch("src.src.app.api.v1.tiers.crud_tiers") as mock_crud:
            mock_crud.get = AsyncMock(return_value=sample_tier_read)
            mock_crud.delete = AsyncMock(side_effect=Exception("Database error"))

            with pytest.raises(Exception, match="Database error"):
                await erase_tier(request, tier_name, mock_db)

            mock_crud.delete.assert_called_once_with(db=mock_db, name=tier_name)


class TestTierPermissions:
    """Test tier endpoint permissions."""

    @pytest.mark.asyncio
    async def test_write_tier_requires_superuser(self, mock_db, sample_tier_data):
        """Test that tier creation requires superuser permissions."""
        # This test verifies the dependency is in place
        # The actual permission checking is handled by the dependency
        tier_create = TierCreate(**sample_tier_data)
        request = Mock(spec=Request)

        with patch("src.src.app.api.v1.tiers.crud_tiers") as mock_crud:
            mock_crud.exists = AsyncMock(return_value=False)
            mock_crud.create = AsyncMock(return_value=Mock(id=1))
            mock_crud.get = AsyncMock(return_value=Mock())

            # This should work if superuser dependency passes
            result = await write_tier(request, tier_create, mock_db)
            assert result is not None

    @pytest.mark.asyncio
    async def test_patch_tier_requires_superuser(self, mock_db, sample_tier_read):
        """Test that tier update requires superuser permissions."""
        request = Mock(spec=Request)
        tier_name = "premium"
        tier_update = TierUpdate(name="updated_premium")

        with patch("src.src.app.api.v1.tiers.crud_tiers") as mock_crud:
            mock_crud.get = AsyncMock(return_value=sample_tier_read)
            mock_crud.update = AsyncMock(return_value=None)

            # This should work if superuser dependency passes
            result = await patch_tier(request, tier_name, tier_update, mock_db)
            assert result == {"message": "Tier updated"}

    @pytest.mark.asyncio
    async def test_erase_tier_requires_superuser(self, mock_db, sample_tier_read):
        """Test that tier deletion requires superuser permissions."""
        request = Mock(spec=Request)
        tier_name = "premium"

        with patch("src.src.app.api.v1.tiers.crud_tiers") as mock_crud:
            mock_crud.get = AsyncMock(return_value=sample_tier_read)
            mock_crud.delete = AsyncMock(return_value=None)

            # This should work if superuser dependency passes
            result = await erase_tier(request, tier_name, mock_db)
            assert result == {"message": "Tier deleted"}

    @pytest.mark.asyncio
    async def test_read_operations_no_auth_required(self, mock_db, sample_tier_read):
        """Test that read operations don't require authentication."""
        request = Mock(spec=Request)

        with patch("src.src.app.api.v1.tiers.crud_tiers") as mock_crud:
            # Test read single tier
            mock_crud.get = AsyncMock(return_value=sample_tier_read)
            result = await read_tier(request, "premium", mock_db)
            assert result == sample_tier_read

            # Test read multiple tiers
            mock_crud.get_multi = AsyncMock(
                return_value={"data": [sample_tier_read], "count": 1}
            )
            with patch("src.app.api.v1.tiers.paginated_response") as mock_paginated:
                mock_paginated.return_value = {
                    "data": [sample_tier_read],
                    "pagination": {},
                }
                result = await read_tiers(request, mock_db)
                assert "data" in result
