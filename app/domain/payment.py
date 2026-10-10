from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, select
from uuid import uuid4
import json
import logging
from typing import Callable, Awaitable, Optional

from app.db.models import Payment, IdempotencyKey, PaymentAttempt
from app.domain.ledger import post_capture
from app.domain.processor_client import ProcessorClient, ProcessorResult

logger = logging.getLogger(__name__)

async def create_and_capture_payment(
    amount_minor: int, 
    idempotency_key: str, 
    db: AsyncSession,
    processor_url: str = "http://localhost:8001",
    test_crash_hook: Optional[Callable[[], Awaitable[None]]] = None
):
    # Tx 1: Prepare the charge
    payment_id = uuid4()
    processor_key = f"{payment_id}:1"
    
    async with db.begin():
        payment = Payment(
            id=payment_id,
            amount_minor=amount_minor,
            status='created'
        )
        db.add(payment)
        await db.flush()
        
        payment.status = 'processing'
        
        attempt = PaymentAttempt(
            payment_id=payment.id,
            processor='mock_a',
            processor_idempotency_key=processor_key,
            status='in_flight'
        )
        db.add(attempt)
        # Commit Tx 1
    
    # ----------------------------------------------------
    # Call the processor
    # ----------------------------------------------------
    client = ProcessorClient(processor_url)
    result = await client.charge(amount_minor, processor_key)
    
    if test_crash_hook:
        await test_crash_hook()
        
    # Tx 2: Record the outcome
    async with db.begin():
        # Fetch payment and attempt for update
        payment_stmt = select(Payment).where(Payment.id == payment_id).with_for_update()
        payment = (await db.execute(payment_stmt)).scalar_one()
        
        attempt_stmt = select(PaymentAttempt).where(PaymentAttempt.processor_idempotency_key == processor_key).with_for_update()
        attempt = (await db.execute(attempt_stmt)).scalar_one()
        
        # We classify as follows:
        # succeeded -> captured
        # declined -> failed
        # ambiguous / retryable -> unknown
        
        attempt.latency_ms = result.latency_ms
        attempt.error_type = result.error_type
        
        status_code = 200
        resp_body = {}
        
        if result.status == 'succeeded':
            payment.status = 'captured'
            attempt.status = 'successful'
            await db.flush()
            
            # Post ledger entries
            await post_capture(payment, db)
            
            status_code = 201
            resp_body = {
                "id": str(payment.id),
                "status": "captured",
                "amount_minor": payment.amount_minor,
                "charge_id": result.charge_id
            }
            
        elif result.status == 'declined':
            payment.status = 'failed'
            attempt.status = 'failed'
            status_code = 400
            resp_body = {
                "id": str(payment.id),
                "status": "failed",
                "amount_minor": payment.amount_minor,
                "error": result.error_type
            }
            
        else: # ambiguous or retryable
            payment.status = 'unknown'
            attempt.status = 'ambiguous'
            status_code = 502
            resp_body = {
                "id": str(payment.id),
                "status": "unknown",
                "amount_minor": payment.amount_minor,
                "error": "ambiguous_processor_response"
            }
        
        # Update idempotency key with final known result
        await db.execute(
            update(IdempotencyKey).where(IdempotencyKey.key == idempotency_key).values(
                status='completed',
                response_code=status_code,
                response_body=resp_body
            )
        )
        
    return resp_body, status_code
