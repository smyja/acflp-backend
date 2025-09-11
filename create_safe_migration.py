#!/usr/bin/env python3
"""
Production-Safe Migration Script
Adds spoken_languages column to user table without data loss
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from app.core.db.database import async_engine
from sqlalchemy import text


async def check_column_exists():
    """Check if spoken_languages column already exists"""
    async with async_engine.connect() as conn:
        result = await conn.execute(
            text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'user' 
            AND column_name = 'spoken_languages'
        """)
        )
        return result.first() is not None


async def add_spoken_languages_column():
    """Safely add spoken_languages column to user table"""
    print("🔍 Checking if spoken_languages column exists...")

    column_exists = await check_column_exists()

    if column_exists:
        print("✅ spoken_languages column already exists. No migration needed.")
        return

    print("📝 Adding spoken_languages column to user table...")

    async with async_engine.connect() as conn:
        # Start transaction
        trans = await conn.begin()

        try:
            # Add the column with default NULL
            await conn.execute(
                text("""
                ALTER TABLE "user" 
                ADD COLUMN spoken_languages VARCHAR DEFAULT NULL
            """)
            )

            # Optional: Set default spoken_languages for existing users
            # This is safe because it doesn't break existing functionality
            await conn.execute(
                text("""
                UPDATE "user" 
                SET spoken_languages = 'en' 
                WHERE spoken_languages IS NULL 
                AND email IS NOT NULL
            """)
            )

            # Commit transaction
            await trans.commit()
            print("✅ Successfully added spoken_languages column")

        except Exception as e:
            # Rollback on error
            await trans.rollback()
            print(f"❌ Error adding column: {e}")
            raise


async def verify_migration():
    """Verify the migration was successful"""
    print("🔍 Verifying migration...")

    async with async_engine.connect() as conn:
        # Check column exists
        result = await conn.execute(
            text("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'user' 
            AND column_name = 'spoken_languages'
        """)
        )

        column_info = result.first()
        if column_info:
            print(f"✅ Column exists: {column_info[0]} ({column_info[1]}, nullable: {column_info[2]})")
        else:
            print("❌ Column not found")
            return False

        # Check data
        result = await conn.execute(
            text("""
            SELECT COUNT(*) as total_users,
                   COUNT(spoken_languages) as users_with_languages
            FROM "user"
        """)
        )

        stats = result.first()
        print(f"📊 Users: {stats[0]} total, {stats[1]} with spoken_languages set")

        return True


async def main():
    """Main migration function"""
    print("🚀 Starting Production-Safe Migration")
    print("=" * 50)

    try:
        await add_spoken_languages_column()
        success = await verify_migration()

        if success:
            print("\n🎉 Migration completed successfully!")
            print("\n📋 Next Steps:")
            print("1. Deploy application code with spoken_languages support")
            print("2. Test API endpoints")
            print("3. Monitor application performance")
            print("4. Gradually enable new features")
        else:
            print("\n❌ Migration verification failed")
            return 1

    except Exception as e:
        print(f"\n💥 Migration failed: {e}")
        print("\n🔄 Rollback may be needed. Check database state.")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
