import json
from datetime import datetime, timezone, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, text
from sqlalchemy.dialects.postgresql import insert
from pydantic import BaseModel, Field
import hashlib

from app.db.session import get_db_session
from app.db.models import IdempotencyKey
from app.domain.payment import create_and_capture_payment

router = APIRouter()

class PaymentRequest(BaseModel):
    amount_minor: int = Field(..., gt=0)
    idempotency_key: str

def generate_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

@router.post("")
async def create_payment(
    request: Request,
    payload: PaymentRequest,
    db: AsyncSession = Depends(get_db_session)
):
    body = await request.json()
    req_hash = generate_hash(body)
    
    # Attempt to insert idempotency key
    stmt = insert(IdempotencyKey).values(
        key=payload.idempotency_key,
        request_hash=req_hash,
        status='in_progress',
        locked_at=datetime.now(timezone.utc)
    ).on_conflict_do_nothing(index_elements=['key']).returning(IdempotencyKey.key)
    
    result = await db.execute(stmt)
    inserted = result.scalar_one_or_none()
    await db.commit()
    
    if not inserted:
        # Key already exists
        result = await db.execute(select(IdempotencyKey).where(IdempotencyKey.key == payload.idempotency_key))
        existing_key = result.scalar_one_or_none()
        
        if existing_key.request_hash != req_hash:
            raise HTTPException(status_code=422, detail="Idempotency key used with different payload")
            
        if existing_key.status == 'completed':
            return Response(
                content=json.dumps(existing_key.response_body),
                status_code=existing_key.response_code,
                media_type="application/json"
            )
            
        # status is in_progress
        lock_timeout = datetime.now(timezone.utc) - timedelta(minutes=2)
        if existing_key.locked_at > lock_timeout:
            return Response(status_code=409, headers={"Retry-After": "5"})
        
        # Take over stale lock
        update_stmt = update(IdempotencyKey).where(
            IdempotencyKey.key == payload.idempotency_key,
            IdempotencyKey.locked_at < lock_timeout
        ).values(locked_at=datetime.now(timezone.utc)).returning(IdempotencyKey.key)
        
        result = await db.execute(update_stmt)
        updated = result.scalar_one_or_none()
        await db.commit()
        
        if not updated:
            return Response(status_code=409, headers={"Retry-After": "5"})

    # Process payment (Create, Capture, Ledger, and update idempotency key in ONE transaction)
    try:
        resp_body, status_code = await create_and_capture_payment(
            amount_minor=payload.amount_minor,
            idempotency_key=payload.idempotency_key,
            db=db
        )
        return Response(content=json.dumps(resp_body), status_code=status_code, media_type="application/json")
    except Exception as e:
        # In a real system we'd handle exceptions. 
        # Here we just raise it to let tests/logging catch it.
        raise e
