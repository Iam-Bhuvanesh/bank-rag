import asyncio
from typing import AsyncGenerator, Generator
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings
from app.models.base import Base
from app.main import app

# Create a test database engine (normally this points to a separate test DB)
# For local testing, we can append '_test' to the DB name or use a nested transaction.
TEST_DATABASE_URL = settings.async_database_url.replace(
    settings.POSTGRES_DB, f"{settings.POSTGRES_DB}_test"
)

# For safety, let's default to the standard URL if not configured, 
# but run all tests inside a transaction that rolls back.
@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def db_engine():
    # Use standard async engine
    engine = create_async_engine(settings.async_database_url, echo=False)
    
    # Create tables in the database if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    yield engine
    
    # Clean up tables after testing
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        
    await engine.dispose()

@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Fixture that provides an AsyncSession for testing.
    All operations are run inside a transaction that is rolled back at the end.
    """
    connection = await db_engine.connect()
    transaction = await connection.begin()
    
    # Create session factory bound to this connection
    SessionLocal = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    
    session = SessionLocal()
    yield session
    
    await session.close()
    await transaction.rollback()
    await connection.close()
