from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import LedgerEntry, Payment

async def post_capture(payment: Payment, db: AsyncSession):
    # Debit processor_clearing, Credit merchant_payable and fees_revenue
    # For simplicity, 2.9% + 0.30 fee
    fee_minor = int(payment.amount_minor * 0.029) + 30
    merchant_amount = payment.amount_minor - fee_minor
    
    txn_id = uuid4()
    
    # 1. Debit processor_clearing for full amount
    db.add(LedgerEntry(
        txn_id=txn_id,
        account_id='processor_clearing',
        debits=payment.amount_minor,
        credits=0
    ))
    
    # 2. Credit fees_revenue
    db.add(LedgerEntry(
        txn_id=txn_id,
        account_id='fees_revenue',
        debits=0,
        credits=fee_minor
    ))
    
    # 3. Credit merchant_payable
    db.add(LedgerEntry(
        txn_id=txn_id,
        account_id='merchant_payable',
        debits=0,
        credits=merchant_amount
    ))
