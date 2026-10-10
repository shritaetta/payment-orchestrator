from fastapi import FastAPI
import uvicorn
from app.api import endpoints

app = FastAPI(title="Payment Orchestrator")

app.include_router(endpoints.router, prefix="/payments", tags=["payments"])

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
