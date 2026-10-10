import re

def rewrite(path, pattern, repl):
    with open(path, 'r') as f:
        c = f.read()
    c = re.sub(pattern, repl, c)
    with open(path, 'w') as f:
        f.write(c)

rewrite('app/domain/circuit_breaker.py', r'def record_failure\(self\):', r'def record_failure(self) -> None:')
rewrite('app/domain/circuit_breaker.py', r'def record_success\(self\):', r'def record_success(self) -> None:')
rewrite('app/domain/circuit_breaker.py', r'def __init__\(self\):', r'def __init__(self) -> None:')
rewrite('app/domain/router.py', r'def get_router\(\):', r'def get_router() -> "PaymentRouter":')
rewrite('app/db/models.py', r'def utcnow\(\):', r'def utcnow() -> datetime:')
rewrite('app/db/models.py', r'Mapped\[dict\]', r'Mapped[dict[str, "Any"]]')
rewrite('app/db/models.py', r'from typing import Optional', r'from typing import Optional, Any')
rewrite('app/domain/ledger.py', r'def post_capture\(payment: Payment, db: AsyncSession\):', r'def post_capture(payment: Payment, db: AsyncSession) -> None:')
rewrite('app/domain/outbox.py', r'payload: dict\)', r'payload: dict[str, "Any"]) -> None:')
rewrite('app/domain/outbox.py', r'import json', r'import json\nfrom typing import Any')
rewrite('app/domain/refund.py', r'db: AsyncSession\n\):', r'db: AsyncSession\n) -> tuple[dict[str, "Any"], int]:')
rewrite('app/domain/refund.py', r'import json', r'import json\nfrom typing import Any')
rewrite('app/workers/outbox.py', r'def run_outbox_worker\(interval_seconds: int = 1\):', r'def run_outbox_worker(interval_seconds: int = 1) -> None:')
rewrite('app/workers/reconciliation.py', r'def run_reconciliation_worker\(interval_seconds: int = 10\):', r'def run_reconciliation_worker(interval_seconds: int = 10) -> None:')
rewrite('app/domain/payment.py', r'def exponential_backoff\(attempt: int, base_ms: int = 100, max_ms: int = 2000\):', r'def exponential_backoff(attempt: int, base_ms: int = 100, max_ms: int = 2000) -> None:')
rewrite('app/domain/payment.py', r'resp_body: dict,', r'resp_body: dict[str, "Any"],')
rewrite('app/domain/payment.py', r'import time', r'import time\nfrom typing import Any')
rewrite('app/api/endpoints.py', r'payload: dict\)', r'payload: dict[str, "Any"]) -> None:')
rewrite('app/main.py', r'async def lifespan\(app\):', r'async def lifespan(app: "FastAPI") -> "typing.AsyncGenerator[None, None]":')
rewrite('app/main.py', r'def custom_openapi\(\):', r'def custom_openapi() -> dict[str, "Any"]:')
rewrite('app/main.py', r'import logging', r'import logging\nimport typing\nfrom typing import Any')
