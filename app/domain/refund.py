from uuid import uuid4
import json
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timezone
import logging

from app.db.models import Payment, LedgerEntry, IdempotencyKey
from app.domain.outbox import publish_event

logger = logging.getLogger(__name__)

async def create_refund(
    payment_id: str, 
    refund_amount_minor: int, 
    idempotency_key: str, 
    db: AsyncSession
) -> tuple[dict[str, "Any"], int]:
    async with db.begin():
        # Lock payment
        payment_stmt = select(Payment).where(Payment.id == payment_id).with_for_update()
        payment: Payment | None = (await db.execute(payment_stmt)).scalar_one_or_none()
        
        if not payment:
            return {"error": "payment_not_found"}, 404
            
        if payment.status not in ('captured', 'partially_refunded'):
            return {"error": "invalid_payment_status"}, 400
            
        if payment.amount_refunded + refund_amount_minor > payment.amount_minor:
            return {"error": "refund_amount_exceeds_captured"}, 400
            
        # Update payment
        payment.amount_refunded += refund_amount_minor
        if payment.amount_refunded == payment.amount_minor:
            payment.status = 'refunded'
        else:
            payment.status = 'partially_refunded'
            
        # Create reversing ledger entries
        # Capture debited processor_clearing and credited merchant_payable & fees_revenue
        # Refund reverses this partially or fully. We will just credit processor_clearing and debit merchant_payable
        # For simplicity, refund does not reverse fees
        
        txn_id = uuid4()
        
        # Credit processor_clearing
        db.add(LedgerEntry(
            txn_id=txn_id,
            account_id='processor_clearing',
            debits=0,
            credits=refund_amount_minor
        ))
        
        # Debit merchant_payable
        db.add(LedgerEntry(
            txn_id=txn_id,
            account_id='merchant_payable',
            debits=refund_amount_minor,
            credits=0
        ))
        
        await db.flush()
        
        status_code = 201
        resp_body = {
            "payment_id": str(payment.id),
            "status": payment.status,
            "amount_refunded": payment.amount_refunded
        }
        
        # Outbox event
        publish_event(db, "payment", str(payment.id), resp_body)
        
        # Update idempotency key
        await db.execute(update(IdempotencyKey).where(IdempotencyKey.key == idempotency_key).values(
            status='completed', 
            response_code=status_code, 
            response_body=resp_body
        ))
        
    return resp_body, status_code
