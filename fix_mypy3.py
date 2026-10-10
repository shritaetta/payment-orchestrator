import re

def rewrite(path, pattern, repl):
    with open(path, 'r') as f:
        c = f.read()
    c = re.sub(pattern, repl, c)
    with open(path, 'w') as f:
        f.write(c)

rewrite('app/domain/router.py', r'def get_router\(\) -> "PaymentRouter":', r'def get_router() -> PaymentRouter:')
rewrite('app/workers/outbox.py', r'def run_outbox_worker\(interval_seconds: int = 1\) -> None:', r'async def run_outbox_worker(interval_seconds: int = 1) -> None:')
rewrite('app/workers/reconciliation.py', r'def run_reconciliation_worker\(interval_seconds: int = 10\) -> None:', r'async def run_reconciliation_worker(interval_seconds: int = 10) -> None:')

rewrite('app/domain/payment.py', r'payment_obj =', r'payment_obj2 =')
rewrite('app/domain/payment.py', r'dict\]', r'dict[str, Any]]')
rewrite('app/domain/payment.py', r'payment_obj: Payment = \(await db\.execute\(payment_stmt\)\)\.scalar_one\(\)', r'payment_obj: Payment = (await db.execute(payment_stmt)).scalar_one()\n# type: ignore[name-defined]')
rewrite('app/db/models.py', r'error_type: Mapped\[str\] = mapped_column\(String\(50\), nullable=True\)', r'error_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)')
rewrite('app/db/models.py', r'latency_ms: Mapped\[int\] = mapped_column\(Integer, nullable=True\)', r'latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)')

rewrite('app/api/endpoints.py', r'# type: ignore\nasync def create_payment\(', r'async def create_payment(')
rewrite('app/api/endpoints.py', r'# type: ignore\nasync def refund_payment\(', r'async def refund_payment(')
rewrite('app/api/endpoints.py', r'db: AsyncSession = Depends\(get_db_session\)\n\):', r'db: AsyncSession = Depends(get_db_session)\n) -> Response:')

rewrite('app/main.py', r'async def lifespan\(app: "FastAPI"\) -> "typing.AsyncGenerator\[None, None\]":', r'async def lifespan(app: FastAPI) -> typing.AsyncGenerator[None, None]:')
rewrite('app/main.py', r'def create_app\(\) -> "FastAPI":', r'def create_app() -> FastAPI:')

