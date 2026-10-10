import asyncio
import httpx
import uuid
import sys
import subprocess
import time
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

TEST_DATABASE_URL = "postgresql+asyncpg://rishi@localhost:5432/payment_orchestrator"

async def main():
    print("Starting kill-and-recover test...")
    
    # Reset DB
    engine = create_async_engine(TEST_DATABASE_URL)
    TestingSessionLocal = async_sessionmaker(bind=engine)
    async with TestingSessionLocal() as session:
        await session.execute(text("TRUNCATE TABLE payments CASCADE"))
        await session.execute(text("TRUNCATE TABLE idempotency_keys CASCADE"))
        await session.commit()
    
    # Set processor to drop response mode
    async with httpx.AsyncClient() as client:
        await client.post("http://localhost:8001/admin/config", json={"drop_response_mode": True})
        
    # Start the app server in background
    app_proc = subprocess.Popen(["venv/bin/uvicorn", "app.main:app", "--port", "8000"])
    time.sleep(2)
    
    # Send a payment that will hang
    print("Sending payment...")
    idempotency_key = str(uuid.uuid4())
    
    async def send_payment():
        async with httpx.AsyncClient() as client:
            try:
                await client.post("http://localhost:8000/payments", json={
                    "amount_minor": 1000,
                    "idempotency_key": idempotency_key
                }, timeout=2.0)
            except Exception:
                pass # Timeout expected
                
    task = asyncio.create_task(send_payment())
    
    # Wait 1 second (payment is in_flight)
    await asyncio.sleep(1.0)
    
    print("Killing app server aggressively...")
    app_proc.kill()
    app_proc.wait()
    
    # Wait out the 5 minute window? We can't wait 5 minutes in a test.
    # We will simulate time travel by updating created_at in the DB!
    print("Simulating time travel (updating created_at)...")
    async with TestingSessionLocal() as session:
        await session.execute(text("UPDATE payment_attempts SET created_at = created_at - INTERVAL '6 minutes'"))
        await session.execute(text("UPDATE payments SET updated_at = updated_at - INTERVAL '6 minutes'"))
        await session.commit()
        
    print("Running reconciliation worker...")
    from app.workers.reconciliation import reconcile_payments
    async with TestingSessionLocal() as session:
        reconciled = await reconcile_payments(session, "http://localhost:8001")
        print(f"Reconciled {reconciled} payments.")
        
    # Verify
    async with TestingSessionLocal() as session:
        res = await session.execute(text("SELECT status FROM payments LIMIT 1"))
        status = res.scalar()
        print(f"Final payment status: {status}")
        
    # Reset config
    async with httpx.AsyncClient() as client:
        await client.post("http://localhost:8001/admin/config", json={"drop_response_mode": False})
        
if __name__ == "__main__":
    asyncio.run(main())
