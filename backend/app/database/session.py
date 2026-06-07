import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.core.config import settings

logger = logging.getLogger(__name__)

# Create the asynchronous database engine.
# In a production scenario, we configure connection pool sizing and connection timeouts here.
engine = create_async_engine(
    settings.async_database_url,
    echo=False,  # Set to True for verbose SQL query logging during development
    future=True,
    pool_pre_ping=True,  # Proactively checks connection health before utilizing from the pool
    pool_size=20,        # Maximum number of persistent connections to keep open
    max_overflow=10      # Number of additional connections allowed when the pool is exhausted
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False, # Prevents objects from expiring to avoid detached instance errors in async flow
    autocommit=False,
    autoflush=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency injection for database sessions.
    Provides a transactional scope around the request execution.
    Automatically handles committing, rolling back on exceptions, and closing the session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()
