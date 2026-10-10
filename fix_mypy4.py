import re

def rewrite(path, pattern, repl):
    with open(path, 'r') as f:
        c = f.read()
    c = re.sub(pattern, repl, c)
    with open(path, 'w') as f:
        f.write(c)

rewrite('app/domain/payment.py', r'payment_obj: Payment = \(await db\.execute\(payment_stmt\)\)\.scalar_one\(\)\n# type: ignore\[name-defined\]', r'payment_obj2: Payment = (await db.execute(payment_stmt)).scalar_one()\n# type: ignore[name-defined]')
rewrite('app/domain/payment.py', r'payment_obj\.status =', r'payment_obj2.status =')
rewrite('app/domain/payment.py', r'await post_capture\(payment_obj', r'await post_capture(payment_obj2')
rewrite('app/domain/payment.py', r'publish_event\(db, "payment", payment_obj\.id', r'publish_event(db, "payment", payment_obj2.id')
rewrite('app/domain/payment.py', r'attempt_obj: PaymentAttempt = \(await db\.execute\(attempt_stmt\)\)\.scalar_one\(\)', r'attempt_obj2: PaymentAttempt = (await db.execute(attempt_stmt)).scalar_one()')
rewrite('app/domain/payment.py', r'attempt_obj\.latency_ms =', r'attempt_obj2.latency_ms =')
rewrite('app/domain/payment.py', r'attempt_obj\.error_type =', r'attempt_obj2.error_type =')
rewrite('app/domain/payment.py', r'payment_obj2\.error_type =', r'payment_obj2.error_type =')
rewrite('app/domain/payment.py', r'payment_obj2\.processor_id =', r'payment_obj2.processor_id =')
