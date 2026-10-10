from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from uuid import uuid4
import json

from app.db.models import Payment, IdempotencyKey
from app.domain.ledger import post_capture

async def create_and_capture_payment(amount_minor: int, idempotency_key: str, db: AsyncSession):
    async with db.begin():
        # 1. Create Payment
        payment = Payment(
            id=uuid4(),
            amount_minor=amount_minor,
            status='created'
        )
        db.add(payment)
        await db.flush()
        
        # 2. Stub processor: transition to processing, then captured
        payment.status = 'processing'
        await db.flush()
        
        payment.status = 'captured'
        await db.flush()
        
        # 3. Post capture ledger entries
        await post_capture(payment, db)
        
        # 4. Update idempotency key in the SAME transaction
        resp_body = {
            "id": str(payment.id),
            "status": payment.status,
            "amount_minor": payment.amount_minor
        }
        status_code = 201
        
        await db.execute(
            update(IdempotencyKey).where(IdempotencyKey.key == idempotency_key).values(
                status='completed',
                response_code=status_code,
                response_body=resp_body
            )
        )
        
    return resp_body, status_code
