from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, select
from uuid import uuid4
import json
import logging
import asyncio
import random
from typing import Callable, Awaitable, Optional, Tuple

from app.db.models import Payment, IdempotencyKey, PaymentAttempt
from app.domain.ledger import post_capture
from app.domain.processor_client import ProcessorClient, ProcessorResult
from app.domain.router import route_payment, PROCESSORS
from app.domain.circuit_breaker import circuit_breakers
from app.domain.outbox import publish_event

logger = logging.getLogger(__name__)

async def exponential_backoff(attempt: int, base_ms: int = 100, max_ms: int = 2000):
    delay_ms = min(base_ms * (2 ** attempt), max_ms)
    jitter = random.uniform(0, delay_ms)
    await asyncio.sleep(jitter / 1000.0)

async def create_and_capture_payment(
    amount_minor: int, 
    idempotency_key: str, 
    db: AsyncSession,
    processor_url: str = "http://localhost:8001",
    test_crash_hook: Optional[Callable[[], Awaitable[None]]] = None,
    currency: str = "USD"
) -> Tuple[dict, int]:
    
    # Fast path: Check idempotency before doing heavy work
    # We do this in endpoints.py in Phase 1, but we might also need to do it here if it's the entrypoint, 
    # but idempotency is already handled in API layer. We assume it's handled.
    
    # Tx 1: Prepare the charge
    payment_id = uuid4()
    
    async with db.begin():
        payment = Payment(
            id=payment_id,
            amount_minor=amount_minor,
            status='created'
        )
        db.add(payment)
        
    # Router Selection
    candidates = await route_payment(amount_minor, currency, db)
    if not candidates:
        return {"error": "no_available_processors"}, 503
        
    final_status = "unknown"
    status_code = 502
    resp_body = {}
    
    for attempt_num, processor in enumerate(candidates):
        processor_key = f"{payment_id}:{attempt_num}"
        
        async with db.begin():
            payment_stmt = select(Payment).where(Payment.id == payment_id).with_for_update()
            payment = (await db.execute(payment_stmt)).scalar_one()
            payment.status = 'processing'
            
            attempt = PaymentAttempt(
                payment_id=payment.id,
                processor=processor.name,
                processor_idempotency_key=processor_key,
                status='in_flight'
            )
            db.add(attempt)
        
        client = ProcessorClient(processor.url)
        breaker = circuit_breakers.get_breaker(processor.name)
        
        max_retries = 3
        result = None
        resolved = False
        
        for retry in range(max_retries):
            result = await client.charge(amount_minor, processor_key)
            
            if test_crash_hook:
                await test_crash_hook()
                
            if result.status == 'succeeded':
                breaker.record_success()
                resolved = True
                break
                
            elif result.status == 'declined':
                breaker.record_success() # Not a system failure
                resolved = True
                break
                
            elif result.status == 'retryable':
                breaker.record_failure()
                if retry < max_retries - 1:
                    await exponential_backoff(retry)
                    continue
                break
                
            elif result.status == 'ambiguous':
                breaker.record_failure()
                # Must resolve ambiguity via lookup before retrying or failing over
                lookup_resolved = False
                for lookup_retry in range(max_retries):
                    await exponential_backoff(lookup_retry)
                    lookup_res = await client.lookup(processor_key)
                    if lookup_res:
                        result = lookup_res # Override result with lookup result
                        if result.status in ['succeeded', 'declined']:
                            lookup_resolved = True
                            breaker.record_success()
                            break
                if lookup_resolved:
                    resolved = True
                    break
                else:
                    # Still ambiguous, cannot safely failover.
                    break
                    
        # Tx 2: Record Outcome
        async with db.begin():
            payment_stmt = select(Payment).where(Payment.id == payment_id).with_for_update()
            payment = (await db.execute(payment_stmt)).scalar_one()
            
            attempt_stmt = select(PaymentAttempt).where(PaymentAttempt.processor_idempotency_key == processor_key).with_for_update()
            attempt = (await db.execute(attempt_stmt)).scalar_one()
            
            if result:
                attempt.latency_ms = result.latency_ms
                attempt.error_type = result.error_type
                
                if result.status == 'succeeded':
                    payment.status = 'captured'
                    attempt.status = 'successful'
                    await post_capture(payment, db)
                    status_code = 201
                    resp_body = {"id": str(payment.id), "status": "captured", "amount_minor": payment.amount_minor, "charge_id": result.charge_id}
                    publish_event(db, "payment", str(payment.id), resp_body)
                    
                    # Update idempotency key
                    await db.execute(update(IdempotencyKey).where(IdempotencyKey.key == idempotency_key).values(status='completed', response_code=status_code, response_body=resp_body))
                    return resp_body, status_code
                    
                elif result.status == 'declined':
                    payment.status = 'failed'
                    attempt.status = 'failed'
                    status_code = 400
                    resp_body = {"id": str(payment.id), "status": "failed", "amount_minor": payment.amount_minor, "error": result.error_type}
                    publish_event(db, "payment", str(payment.id), resp_body)
                    
                    # Update idempotency key
                    await db.execute(update(IdempotencyKey).where(IdempotencyKey.key == idempotency_key).values(status='completed', response_code=status_code, response_body=resp_body))
                    return resp_body, status_code
                    
                else:
                    attempt.status = 'failed' if result.status == 'retryable' else 'ambiguous'
            
            if not resolved and result and result.status == 'ambiguous':
                # We cannot safely failover to the next processor because this processor might have charged the user!
                payment.status = 'unknown'
                status_code = 502
                resp_body = {"id": str(payment.id), "status": "unknown", "amount_minor": payment.amount_minor, "error": "ambiguous_processor_response"}
                
                await db.execute(update(IdempotencyKey).where(IdempotencyKey.key == idempotency_key).values(status='completed', response_code=status_code, response_body=resp_body))
                return resp_body, status_code
                
        # If we reached here, it means we had a retryable failure that exhausted retries, but wasn't ambiguous.
        # We loop to the next processor candidate for failover.

    # If all processors failed (and no ambiguous state locked us in)
    async with db.begin():
        payment_stmt = select(Payment).where(Payment.id == payment_id).with_for_update()
        payment = (await db.execute(payment_stmt)).scalar_one()
        payment.status = 'failed'
        status_code = 502
        resp_body = {"id": str(payment.id), "status": "failed", "amount_minor": payment.amount_minor, "error": "all_processors_failed"}
        publish_event(db, "payment", str(payment.id), resp_body)
        await db.execute(update(IdempotencyKey).where(IdempotencyKey.key == idempotency_key).values(status='completed', response_code=status_code, response_body=resp_body))
        
    return resp_body, status_code
