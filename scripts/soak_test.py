import asyncio
import httpx
import uuid
import time
import random
import sys
from app.main import app
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

TEST_DATABASE_URL = "postgresql+asyncpg://rishi@localhost:5432/payment_orchestrator"

async def main():
    print("Starting soak test...")
    
    # 1. Start random failure simulator
    async def mess_with_processors():
        ports = [8001, 8002, 8003]
        async with httpx.AsyncClient() as client:
            for _ in range(5): # run for 5 seconds
                port = random.choice(ports)
                fail_rate = random.choice([0.0, 0.5, 1.0])
                try:
                    await client.post(f"http://localhost:{port}/admin/config", json={"error_5xx_rate": fail_rate})
                except Exception:
                    pass
                await asyncio.sleep(1.0)
            
            # Reset all
            for port in ports:
                try:
                    await client.post(f"http://localhost:{port}/admin/config", json={"error_5xx_rate": 0.0})
                except Exception:
                    pass

    async def generate_load():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for _ in range(50):
                await client.post("/payments", json={
                    "amount_minor": random.randint(100, 5000),
                    "idempotency_key": str(uuid.uuid4())
                })
                await asyncio.sleep(0.1)
                
    await asyncio.gather(mess_with_processors(), generate_load())
    
    # Run audit logic directly in python
    print("Running audit queries...")
    engine = create_async_engine(TEST_DATABASE_URL)
    TestingSessionLocal = async_sessionmaker(bind=engine)
    
    async with TestingSessionLocal() as session:
        # Check global balance
        res = await session.execute(text("SELECT SUM(debits), SUM(credits) FROM ledger_entries"))
        row = res.one()
        if row[0] is not None:
            assert row[0] == row[1], f"Global ledger unbalanced: {row}"
            print("Global ledger is balanced.")
            
        # Check double captures
        res = await session.execute(text("SELECT payment_id FROM payment_attempts WHERE status = 'successful' GROUP BY payment_id HAVING COUNT(*) > 1"))
        assert len(res.all()) == 0, "Double capture found!"
        print("No double captures found.")
        
if __name__ == "__main__":
    asyncio.run(main())
