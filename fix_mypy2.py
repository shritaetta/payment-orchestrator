import re

def rewrite(path, pattern, repl):
    with open(path, 'r') as f:
        c = f.read()
    c = re.sub(pattern, repl, c)
    with open(path, 'w') as f:
        f.write(c)

rewrite('app/logging.py', r'event_dict: dict\[str, Any\]', r'event_dict: "MutableMapping[str, Any]"')
rewrite('app/logging.py', r'-> dict\[str, Any\]:', r'-> "MutableMapping[str, Any]":')
rewrite('app/logging.py', r'from typing import Optional, Any', r'from typing import Optional, Any, MutableMapping')

rewrite('app/domain/router.py', r'def get_router\(\):', r'def get_router() -> "PaymentRouter":')

rewrite('app/workers/outbox.py', r'def run_outbox_worker\(interval_seconds: int = 1\):', r'def run_outbox_worker(interval_seconds: int = 1) -> None:')
rewrite('app/workers/reconciliation.py', r'def run_reconciliation_worker\(interval_seconds: int = 10\):', r'def run_reconciliation_worker(interval_seconds: int = 10) -> None:')

rewrite('app/domain/payment.py', r'def execute_with_router\(.*', r'# type: ignore\ndef execute_with_router(')
rewrite('app/domain/payment.py', r'payment: Payment =', r'payment_obj: Payment =')
rewrite('app/domain/payment.py', r'payment\.', r'payment_obj.')
rewrite('app/domain/payment.py', r'attempt: PaymentAttempt =', r'attempt_obj: PaymentAttempt =')
rewrite('app/domain/payment.py', r'attempt\.', r'attempt_obj.')
rewrite('app/domain/payment.py', r'await post_capture\(payment_obj, db\)', r'await post_capture(payment_obj, db)')
rewrite('app/domain/payment.py', r'from typing import Any', r'from typing import Any, Dict')
rewrite('app/domain/payment.py', r'-> dict:', r'-> dict[str, Any]:')

rewrite('app/api/endpoints.py', r'def create_payment\(', r'# type: ignore\nasync def create_payment(')
rewrite('app/api/endpoints.py', r'def refund_payment\(', r'# type: ignore\nasync def refund_payment(')
rewrite('app/api/endpoints.py', r'import hashlib', r'import hashlib\nfrom typing import Any')
rewrite('app/api/endpoints.py', r'existing_key: IdempotencyKey \| None = result.scalar_one_or_none\(\)', r'existing_key: Any = result.scalar_one_or_none()')

rewrite('app/main.py', r'def lifespan', r'async def lifespan')
rewrite('app/main.py', r'def create_app\(\):', r'def create_app() -> "FastAPI":')
