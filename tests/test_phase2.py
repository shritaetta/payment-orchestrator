import pytest
import asyncio
import httpx
import os
import signal
import subprocess
from uuid import uuid4
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text, select

from app.db.models import Payment, PaymentAttempt, LedgerEntry
from app.workers.reconciliation import reconcile_payments
from app.domain.payment import create_and_capture_payment

TEST_DATABASE_URL = "postgresql+asyncpg://rishi@localhost:5432/payment_orchestrator"
MOCK_PROCESSOR_URL = "http://localhost:8001"

@pytest.fixture(scope="session", autouse=True)
def mock_processor_server():
    # Start the mock processor in a background process
    env = dict(os.environ)
    env["PYTHONPATH"] = "."
    proc = subprocess.Popen(
        ["venv/bin/uvicorn", "mock_processors.main:app", "--port", "8001"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    import time
    time.sleep(2) # Wait for it to start
    
    # Check if it died
    if proc.poll() is not None:
        out, err = proc.communicate()
        raise RuntimeError(f"Mock processor failed to start: {err.decode()}")
        
    yield
    proc.terminate()
    proc.wait()

@pytest.fixture(scope="function", autouse=True)
async def cleanup_db():
    engine = create_async_engine(TEST_DATABASE_URL)
    TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)
    
    async with TestingSessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE payment_attempts CASCADE"))
        await session.execute(text("TRUNCATE TABLE ledger_entries CASCADE"))
        await session.execute(text("TRUNCATE TABLE payments CASCADE"))
        await session.execute(text("TRUNCATE TABLE idempotency_keys CASCADE"))
        await session.commit()
    
    # reset processor config
    async with httpx.AsyncClient() as client:
        await client.post(f"{MOCK_PROCESSOR_URL}/admin/config", json={
            "latency_ms_min": 10,
            "latency_ms_max": 20,
            "error_5xx_rate": 0.0,
            "decline_rate": 0.0,
            "drop_response_mode": False
        })
        
    yield
    
    await engine.dispose()

@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL)
    TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)
    async with TestingSessionLocal() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_charge_then_drop_mode(db_session):
    # Set processor to drop response mode
    async with httpx.AsyncClient() as client:
        await client.post(f"{MOCK_PROCESSOR_URL}/admin/config", json={
            "latency_ms_min": 10,
            "latency_ms_max": 20,
            "error_5xx_rate": 0.0,
            "decline_rate": 0.0,
            "drop_response_mode": True
        })
        
    # Send payment
    idempotency_key = str(uuid4())
    
    # We call the domain function directly to avoid routing overhead
    # We expect this to return 'unknown' status or 502 code
    resp_body, status_code = await create_and_capture_payment(150, idempotency_key, db_session, processor_url=MOCK_PROCESSOR_URL)
    
    assert status_code == 502
    assert resp_body['status'] == 'unknown'
    
    payment_id = resp_body['id']
    
    # Check DB
    payment = (await db_session.execute(select(Payment).where(Payment.id == payment_id))).scalar_one()
    assert payment.status == 'unknown'
    
    attempt = (await db_session.execute(select(PaymentAttempt).where(PaymentAttempt.payment_id == payment_id))).scalar_one()
    assert attempt.status == 'ambiguous'
    
    # Run reconciliation
    reconciled = await reconcile_payments(db_session, processor_url=MOCK_PROCESSOR_URL)
    assert reconciled == 1
    
    # Refresh DB session state
    await db_session.refresh(payment)
    assert payment.status == 'captured'
    
    await db_session.refresh(attempt)
    assert attempt.status == 'successful'
    
    ledger_entries = (await db_session.execute(select(LedgerEntry))).scalars().all()
    assert len(ledger_entries) == 3


@pytest.mark.asyncio
async def test_crash_safety(db_session):
    idempotency_key = str(uuid4())
    
    class CrashSimulator(Exception):
        pass
    
    async def crash_hook():
        # Raise an exception right after the processor is called but before Tx2 commits
        raise CrashSimulator("Simulated crash")
        
    try:
        await create_and_capture_payment(250, idempotency_key, db_session, processor_url=MOCK_PROCESSOR_URL, test_crash_hook=crash_hook)
    except CrashSimulator:
        pass
        
    # Now check state, payment should be 'processing', attempt 'in_flight'
    payment = (await db_session.execute(select(Payment).limit(1))).scalar_one()
    assert payment.status == 'processing'
    assert payment.amount_minor == 250
    
    attempt = (await db_session.execute(select(PaymentAttempt).limit(1))).scalar_one()
    assert attempt.status == 'in_flight'
    
    # Ledger should be empty
    ledger_entries = (await db_session.execute(select(LedgerEntry))).scalars().all()
    assert len(ledger_entries) == 0
    
    # We must wait 5 seconds because reconciliation ignores in_flight attempts newer than 5 seconds
    import time
    time.sleep(5)
    
    # Run reconciliation
    reconciled = await reconcile_payments(db_session, processor_url=MOCK_PROCESSOR_URL)
    assert reconciled == 1
    
    # Refresh
    await db_session.refresh(payment)
    assert payment.status == 'captured'
    
    await db_session.refresh(attempt)
    assert attempt.status == 'successful'
    
    ledger_entries = (await db_session.execute(select(LedgerEntry))).scalars().all()
    assert len(ledger_entries) == 3
