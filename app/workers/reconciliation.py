import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, timezone

from app.db.session import async_session_maker
from app.db.models import Payment, PaymentAttempt
from app.domain.processor_client import ProcessorClient
from app.domain.ledger import post_capture
import structlog

logger = structlog.get_logger(__name__)

async def reconcile_payments(db: AsyncSession, processor_url: str = "http://localhost:8001") -> int:
    # Find payments that need reconciliation
    # status == 'unknown' or (status == 'processing' and attempt is older than 5 seconds)
    
    # Subquery to lock payments
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(seconds=5)
    
    stmt = (
        select(Payment)
        .join(PaymentAttempt)
        .where(
            (Payment.status == 'unknown') |
            ((Payment.status == 'processing') & (PaymentAttempt.created_at < threshold) & (PaymentAttempt.status == 'in_flight'))
        )
        .with_for_update(skip_locked=True)
    )
    
    payments_to_reconcile = (await db.execute(stmt)).scalars().all()
    
    if not payments_to_reconcile:
        return 0

    client = ProcessorClient(processor_url)
    reconciled_count = 0
    
    for payment in payments_to_reconcile:
        # Find the latest attempt
        attempt_stmt = (
            select(PaymentAttempt)
            .where(PaymentAttempt.payment_id == payment.id)
            .order_by(PaymentAttempt.created_at.desc())
            .limit(1)
        )
        attempt: PaymentAttempt = (await db.execute(attempt_stmt)).scalar_one()
        
        if attempt.correlation_id:
            from app.logging import set_correlation_id
            set_correlation_id(attempt.correlation_id)
            
        logger.info("reconciling_payment", payment_id=str(payment.id), idempotency_key=attempt.processor_idempotency_key)
        
        # Perform lookup
        result = await client.lookup(attempt.processor_idempotency_key)
        
        if result:
            if result.status == 'succeeded':
                payment.status = 'captured'
                attempt.status = 'successful'
                await db.flush()
                
                # Post ledger
                await post_capture(payment, db)
                reconciled_count += 1
                
            elif result.status == 'declined' or result.status == 'not_found':
                payment.status = 'failed'
                attempt.status = 'failed'
                reconciled_count += 1
            
            elif result.status == 'retryable':
                # Keep it unknown, we'll backoff and try again later
                pass
        else:
            # null result? means error or exception
            pass
            
    await db.commit()
    return reconciled_count
