import re

def rewrite(path, pattern, repl):
    with open(path, 'r') as f:
        c = f.read()
    c = re.sub(pattern, repl, c)
    with open(path, 'w') as f:
        f.write(c)

rewrite('app/domain/payment.py', r'payment_obj: Payment = \(await db\.execute\(payment_stmt\)\)\.scalar_one\(\)', r'payment_obj = (await db.execute(payment_stmt)).scalar_one()')
rewrite('app/domain/payment.py', r'attempt_obj: PaymentAttempt = \(await db\.execute\(attempt_stmt\)\)\.scalar_one\(\)', r'attempt_obj = (await db.execute(attempt_stmt)).scalar_one()')

# Now add back the type annotation for the first definition
rewrite('app/domain/payment.py', r'payment_obj = \(await db\.execute\(payment_stmt\)\)\.scalar_one\(\)\n            payment_obj.status =', r'payment_obj: Payment = (await db.execute(payment_stmt)).scalar_one()\n            payment_obj.status =')
rewrite('app/domain/payment.py', r'attempt_obj = PaymentAttempt\(', r'attempt_obj: PaymentAttempt = PaymentAttempt(')

rewrite('app/workers/outbox.py', r'async def process_outbox_events\(db: AsyncSession\) -> None:', r'async def process_outbox_events(db: AsyncSession) -> int:')
rewrite('app/workers/reconciliation.py', r'async def reconcile_payments\(db: AsyncSession, processor_url: str = "http://localhost:8001"\) -> None:', r'async def reconcile_payments(db: AsyncSession, processor_url: str = "http://localhost:8001") -> int:')

