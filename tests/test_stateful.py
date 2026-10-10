import asyncio
import httpx
import uuid
import os
import subprocess
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, text
import pytest

from app.db.models import Payment, PaymentAttempt, LedgerEntry
from app.main import app

# Hypothesis tests should not be slow or do network, but we are running a small integration loop here.
# To do async property testing with Hypothesis stateful, we must wrap it.
# Wait, Hypothesis stateful tests don't support async natively well. We'll run a synchronous event loop wrapper.

TEST_DATABASE_URL = "postgresql+asyncpg://rishi@localhost:5432/payment_orchestrator"

def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

class PaymentOrchestratorMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.engine = create_async_engine(TEST_DATABASE_URL)
        self.Session = async_sessionmaker(bind=self.engine)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        
        # We start processors synchronously before tests? 
        # For a stateful test, it's better to just mock the endpoints or assume they're up.
        # We'll assume the mock processors are running on 8001, 8002, 8003
        
        # Truncate tables for fresh state
        run_async(self._truncate())
        
        self.known_idempotency_keys = []
        self.payments_created = []

    async def _truncate(self):
        async with self.Session() as db:
            await db.execute(text("TRUNCATE TABLE payment_attempts CASCADE"))
            await db.execute(text("TRUNCATE TABLE ledger_entries CASCADE"))
            await db.execute(text("TRUNCATE TABLE payments CASCADE"))
            await db.execute(text("TRUNCATE TABLE idempotency_keys CASCADE"))
            await db.execute(text("TRUNCATE TABLE outbox_events CASCADE"))
            await db.commit()
            
    async def _set_processor_config(self, port, config):
        async with httpx.AsyncClient() as client:
            await client.post(f"http://localhost:{port}/admin/config", json=config)
            
    @initialize()
    def setup(self):
        pass

    @rule(amount=st.integers(min_value=1, max_value=100000))
    def rule_create_payment(self, amount):
        key = str(uuid.uuid4())
        self.known_idempotency_keys.append(key)
        
        # Normal processing
        resp = run_async(self.client.post("/payments", json={
            "amount_minor": amount,
            "idempotency_key": key
        }))
        if resp.status_code == 201:
            self.payments_created.append(resp.json()["id"])
            
    @rule()
    def rule_duplicate_request(self):
        if not self.known_idempotency_keys:
            return
        key = self.known_idempotency_keys[-1]
        # Just repeat
        run_async(self.client.post("/payments", json={
            "amount_minor": 100, # payload mismatch might happen if amount doesn't match!
            # so this might hit 422 which is fine.
            "idempotency_key": key
        }))

    @rule(amount=st.integers(min_value=1, max_value=100000))
    def rule_refund(self, amount):
        if not self.payments_created:
            return
        payment_id = self.payments_created[-1]
        key = str(uuid.uuid4())
        
        run_async(self.client.post(f"/payments/{payment_id}/refunds", json={
            "amount_minor": amount,
            "idempotency_key": key
        }))

    @rule(failure_rate=st.floats(min_value=0.0, max_value=1.0))
    def rule_set_failures(self, failure_rate):
        run_async(self._set_processor_config(8001, {"error_5xx_rate": failure_rate}))
        run_async(self._set_processor_config(8002, {"error_5xx_rate": failure_rate}))

    @rule(drop_rate=st.booleans())
    def rule_set_timeout(self, drop_rate):
        run_async(self._set_processor_config(8001, {"drop_response_mode": drop_rate}))

    @rule()
    def rule_reconcile(self):
        from app.workers.reconciliation import reconcile_payments
        async def run_reconcile():
            async with self.Session() as db:
                await reconcile_payments(db, "http://localhost:8001")
        run_async(run_reconcile())

    @invariant()
    def invariant_audit(self):
        # We assert DB constraints
        async def check():
            async with self.Session() as db:
                # 1. Debits == Credits per txn
                q1 = await db.execute(text("SELECT txn_id, SUM(debits), SUM(credits) FROM ledger_entries GROUP BY txn_id HAVING SUM(debits) != SUM(credits)"))
                assert len(q1.all()) == 0, "Unbalanced transaction found"
                
                # 2. Globally sum is zero
                q2 = await db.execute(text("SELECT SUM(debits), SUM(credits) FROM ledger_entries"))
                res = q2.one()
                if res[0] is not None:
                    assert res[0] == res[1], "Global ledger is unbalanced"
                
                # 3. No payment captured twice
                q3 = await db.execute(text("SELECT payment_id FROM payment_attempts WHERE status = 'successful' GROUP BY payment_id HAVING COUNT(*) > 1"))
                assert len(q3.all()) == 0, "Payment captured twice"
                
                # 4. Refunded <= Captured
                q4 = await db.execute(text("SELECT id FROM payments WHERE amount_refunded > amount_minor OR amount_refunded < 0"))
                assert len(q4.all()) == 0, "Refunded total > captured total"
                
        run_async(check())

    def teardown(self):
        run_async(self.client.aclose())
        run_async(self.engine.dispose())

# Setup pytest entry point
TestPaymentOrchestrator = PaymentOrchestratorMachine.TestCase
