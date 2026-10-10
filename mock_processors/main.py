from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import asyncio
import random
from typing import Optional

app = FastAPI(title="Mock Processor")

# In-memory store for idempotency
charges = {}

class Config(BaseModel):
    latency_ms_min: int = 50
    latency_ms_max: int = 150
    error_5xx_rate: float = 0.0
    decline_rate: float = 0.0
    drop_response_mode: bool = False

current_config = Config()

class ChargeRequest(BaseModel):
    amount_minor: int

class ChargeResponse(BaseModel):
    id: str
    status: str

@app.post("/admin/config")
def update_config(config: Config):
    global current_config
    current_config = config
    return {"status": "updated", "config": current_config}

@app.post("/charge", response_model=ChargeResponse)
async def charge(req: ChargeRequest, idempotency_key: str = Header(..., alias="Idempotency-Key")):
    global current_config
    
    if idempotency_key in charges:
        return charges[idempotency_key]
        
    # Simulate latency
    latency = random.randint(current_config.latency_ms_min, current_config.latency_ms_max)
    await asyncio.sleep(latency / 1000.0)
    
    # Check 5xx
    if random.random() < current_config.error_5xx_rate:
        raise HTTPException(status_code=500, detail="Internal Server Error")
        
    # Check decline
    if random.random() < current_config.decline_rate:
        raise HTTPException(status_code=400, detail="Card Declined")
        
    charge_id = f"ch_{random.randint(10000, 99999)}"
    response = ChargeResponse(id=charge_id, status="succeeded")
    
    charges[idempotency_key] = response
    
    if current_config.drop_response_mode:
        # Simulate network drop by hanging forever or throwing a timeout-like error, 
        # actually, just sleep longer than the client timeout to simulate drop
        await asyncio.sleep(10.0) 
        
    return response

@app.get("/charges/{idempotency_key}")
async def lookup(idempotency_key: str):
    if idempotency_key in charges:
        return charges[idempotency_key]
    raise HTTPException(status_code=404, detail="Not Found")
