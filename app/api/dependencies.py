"""
API dependencies for Product Intelligence Platform.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db


async def get_database() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session.
    """
    async for session in get_db():
        yield session
