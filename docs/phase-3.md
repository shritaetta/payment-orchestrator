# Phase 3: Routing, resilience, refunds, outbox

## Decisions

1. **Routing**: 
   - A router queries `payment_attempts` over a rolling window (5 minutes) for success rates.
   - It filters out candidates based on `supported_currencies`, `max_amount_minor`, and circuit breaker states.
   - It sorts candidates by success rate (descending) and fee cost (ascending) to prefer the most reliable and cheapest processor.

2. **Circuit Breaker**:
   - An in-memory circuit breaker limits cascading failures to broken downstream processors.
   - `OPEN` state prevents routing requests to the processor for a configurable cooldown.
   - `HALF_OPEN` state allows a test request through to check recovery.
   - 5xx errors and connection refused mark failures, whereas `declined` or `succeeded` mark successes (business-level declines don't affect system health).

3. **Retries and Failover**:
   - Retries use exponential backoff and jitter.
   - A `retryable` (5xx, connection error) error triggers retries. If max retries are hit, we fail over to the next candidate processor.
   - An `ambiguous` (read timeout) error triggers internal retry via the `lookup` endpoint. If ambiguity is resolved to a final state, we break the loop. If it remains ambiguous, we return 502 and let the background reconciliation worker handle it (preventing double charges by avoiding unsafe failover).

4. **Refunds**:
   - Enforced by a DB `CheckConstraint('amount_refunded >= 0 AND amount_refunded <= amount_minor')` on the `payments` table.
   - Refunds update the `amount_refunded` atomically and insert reversing `LedgerEntry` rows (credit `processor_clearing`, debit `merchant_payable`).
   - Idempotency ensures the same refund key cannot be executed twice.

5. **Transactional Outbox**:
   - Domain logic writes `OutboxEvent` rows atomically with updates to `Payment`.
   - A separate async worker claims rows using `FOR UPDATE SKIP LOCKED`.
   - Payloads are signed via HMAC-SHA256.
   - Repeated failures trigger exponential backoff, eventually moving to `dead_letters` after N attempts.
