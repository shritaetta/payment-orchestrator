import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.db.session import get_db_session
import uuid

TEST_DATABASE_URL = "postgresql+asyncpg://rishi@localhost:5432/payment_orchestrator"

@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, pool_size=50, max_overflow=50)
    yield engine
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=db_engine, class_=AsyncSession)
    
    async def override_get_db_session():
        async with TestingSessionLocal() as session:
            yield session
            
    app.dependency_overrides[get_db_session] = override_get_db_session
    
    async with TestingSessionLocal() as session:
        yield session

@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
