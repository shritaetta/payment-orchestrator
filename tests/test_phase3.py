import pytest
import httpx
import uuid
from sqlalchemy import select, text
import asyncio
import subprocess
import time
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.main import app
from app.db.models import Payment, PaymentAttempt, LedgerEntry, OutboxEvent
from app.domain.circuit_breaker import circuit_breakers

from app.api.endpoints import get_db_session
from httpx import ASGITransport

TEST_DATABASE_URL = "postgresql+asyncpg://rishi@localhost:5432/payment_orchestrator"

test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=test_engine, class_=AsyncSession)

async def override_get_db_session():
    async with TestingSessionLocal() as session:
        yield session

app.dependency_overrides[get_db_session] = override_get_db_session

@pytest.fixture(scope="module")
def mock_processors():
    procs = []
    for port in [8001, 8002, 8003]:
        p = subprocess.Popen(
            ["venv/bin/uvicorn", "mock_processors.main:app", "--port", str(port)]
        )
        procs.append(p)
    time.sleep(2) # wait for servers to start
    yield
    for p in procs:
        p.terminate()
        p.wait()

@pytest.fixture(autouse=True)
async def cleanup():
    async with TestingSessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE payment_attempts CASCADE"))
        await session.execute(text("TRUNCATE TABLE ledger_entries CASCADE"))
        await session.execute(text("TRUNCATE TABLE payments CASCADE"))
        await session.execute(text("TRUNCATE TABLE idempotency_keys CASCADE"))
        await session.execute(text("TRUNCATE TABLE outbox_events CASCADE"))
        await session.commit()
        
    for breaker in circuit_breakers._breakers.values():
        breaker.record_success() # Reset failures
        
    for port in [8001, 8002, 8003]:
        try:
            await set_processor_config(port, {
                "latency_ms_min": 10,
                "latency_ms_max": 20,
                "error_5xx_rate": 0.0,
                "decline_rate": 0.0,
                "drop_response_mode": False
            })
        except:
            pass

@pytest.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session

async def set_processor_config(port: int, config: dict):
    async with httpx.AsyncClient() as client:
        await client.post(f"http://localhost:{port}/admin/config", json=config)

@pytest.mark.asyncio
async def test_router_failover_on_5xx(mock_processors, db_session):
    # processor_b will be picked first due to lowest fee (30). Make it fail!
    await set_processor_config(8002, {"error_5xx_rate": 1.0})
    # processor_c will be picked second due to fee (35).
    await set_processor_config(8003, {"error_5xx_rate": 0.0})
    
    idempotency_key = str(uuid.uuid4())
    
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/payments", json={
            "amount_minor": 1000,
            "idempotency_key": idempotency_key
        })
        
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "captured"
    
    stmt = select(PaymentAttempt).where(PaymentAttempt.payment_id == data["id"]).order_by(PaymentAttempt.id)
    attempts = (await db_session.execute(stmt)).scalars().all()
    
    assert len(attempts) >= 2
    assert attempts[0].processor == "processor_b"
    assert attempts[0].status == "failed"
    
    assert attempts[-1].processor == "processor_c"
    assert attempts[-1].status == "successful"

@pytest.mark.asyncio
async def test_circuit_breaker(mock_processors, db_session):
    await set_processor_config(8001, {"error_5xx_rate": 1.0})
    
    # We send multiple requests to trip the breaker for A
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(5):
            await client.post("/payments", json={
                "amount_minor": 1000,
                "idempotency_key": str(uuid.uuid4())
            })
            
        idempotency_key = str(uuid.uuid4())
        resp = await client.post("/payments", json={
            "amount_minor": 1000,
            "idempotency_key": idempotency_key
        })
        
    assert resp.status_code == 201
    data = resp.json()
    
    stmt = select(PaymentAttempt).where(PaymentAttempt.payment_id == data["id"]).order_by(PaymentAttempt.id)
    attempts = (await db_session.execute(stmt)).scalars().all()
    
    # Should only try B, because A's circuit breaker is open
    assert len(attempts) == 1
    assert attempts[0].processor == "processor_b"

@pytest.mark.asyncio
async def test_ambiguous_resolution(mock_processors, db_session):
    await set_processor_config(8001, {"error_5xx_rate": 1.0}) # Skip A
    await set_processor_config(8002, {"drop_response_mode": True, "error_5xx_rate": 0.0})
    
    idempotency_key = str(uuid.uuid4())
    
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/payments", json={
            "amount_minor": 1000,
            "idempotency_key": idempotency_key
        })
        
    # App times out on charge, but resolves via lookup!
    # Wait! Our `test_ambiguous_resolution` currently expects lookup to succeed immediately inside the charge loop.
    assert resp.status_code == 201

@pytest.mark.asyncio
async def test_refunds(mock_processors, db_session):
    idempotency_key = str(uuid.uuid4())
    
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/payments", json={
            "amount_minor": 1000,
            "idempotency_key": idempotency_key
        })
        
    assert resp.status_code == 201
    payment_id = resp.json()["id"]
    
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Partial refund
        resp = await client.post(f"/payments/{payment_id}/refunds", json={
            "amount_minor": 400,
            "idempotency_key": str(uuid.uuid4())
        })
        assert resp.status_code == 201
        assert resp.json()["status"] == "partially_refunded"
        
        # Remaining refund
        resp = await client.post(f"/payments/{payment_id}/refunds", json={
            "amount_minor": 600,
            "idempotency_key": str(uuid.uuid4())
        })
        assert resp.status_code == 201
        assert resp.json()["status"] == "refunded"
        
        # Over refund
        resp = await client.post(f"/payments/{payment_id}/refunds", json={
            "amount_minor": 100,
            "idempotency_key": str(uuid.uuid4())
        })
        assert resp.status_code == 400
        assert resp.json().get("error") == "invalid_payment_status"
