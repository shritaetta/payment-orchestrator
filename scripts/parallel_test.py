import asyncio
import httpx
import uuid
import time
from app.main import app

async def main():
    print("Starting 1,000-parallel-same-key test...")
    idempotency_key = str(uuid.uuid4())
    payload = {"amount_minor": 500, "idempotency_key": idempotency_key}
    
    # We use a real HTTP client hitting the running server on port 8000
    # Wait, the prompt says "scripted, reproducible with one command", so we assume the server is running or we start it here?
    # Let's hit http://localhost:8000/payments directly, assuming it's running via uvicorn in another window, or we can use ASGITransport!
    # Let's use ASGITransport for isolated test script so it doesn't need external uvicorn (except processors).
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Fire 1000 requests concurrently
        tasks = []
        for _ in range(1000):
            tasks.append(client.post("/payments", json=payload))
            
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        status_counts = {}
        for r in results:
            if isinstance(r, Exception):
                status = "Exception"
            else:
                status = str(r.status_code)
            status_counts[status] = status_counts.get(status, 0) + 1
            
        print(f"Completed 1000 requests in {end_time - start_time:.2f} seconds.")
        print("Status code distribution:")
        for status, count in status_counts.items():
            print(f"  HTTP {status}: {count} requests")
            
        # For idempotency, we expect exactly ONE 201 Created (or 200 OK depending on implementation).
        # Actually, all requests might get 201 or 409 Retry-After, or 201 (cached).
        # Our idempotency layer returns the cached 201 response for all subsequent requests!
        # So we should see a mix of 409 (Retry-After) during lock contention, and 201 (cached) after completion.
        
if __name__ == "__main__":
    asyncio.run(main())
