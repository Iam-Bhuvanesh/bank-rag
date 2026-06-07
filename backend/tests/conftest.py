import asyncio
from typing import AsyncGenerator, Generator
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings
from app.models.base import Base

# Derive the test database URL from settings
TEST_DATABASE_URL = settings.async_database_url.replace(
    settings.POSTGRES_DB, f"{settings.POSTGRES_DB}_test"
)

# Template/default database URL to perform admin commands like CREATE DATABASE
ADMIN_DATABASE_URL = settings.async_database_url.replace(
    settings.POSTGRES_DB, "postgres"
)

async def create_test_db_if_not_exists():
    """
    Connects to the default 'postgres' database and creates the test database if it doesn't exist.
    """
    # Create engine for admin commands (isolation_level="AUTOCOMMIT" is required for CREATE DATABASE)
    engine = create_async_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    test_db_name = f"{settings.POSTGRES_DB}_test"
    
    async with engine.connect() as conn:
        # Check if database exists
        result = await conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
            {"dbname": test_db_name}
        )
        exists = result.scalar()
        
        if not exists:
            print(f"Creating test database: {test_db_name}")
            await conn.execute(text(f"CREATE DATABASE {test_db_name}"))
            
    await engine.dispose()

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
    # 1. Ensure the test database exists
    await create_test_db_if_not_exists()
    
    # 2. Connect to the test database
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # 3. Create all tables in the test database
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    yield engine
    
    # 4. Clean up tables in the test database after testing
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
