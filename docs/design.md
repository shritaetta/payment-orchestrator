# Design Document

## Tradeoffs

### 1. DB-Enforced vs App-Enforced Invariants
**Decision**: Enforce all absolute invariants (ledger balances, valid status transitions, maximum refunds) via PostgreSQL `CHECK` constraints, triggers, and `INSERT ON CONFLICT`.
**Tradeoff**: 
- *Pros*: Data integrity is mathematically guaranteed regardless of application bugs, concurrency issues, or orphaned workers. 
- *Cons*: Business logic leaks into the database layer. Database migrations are heavier. Application must handle DB-level exceptions (e.g. `IntegrityError`) gracefully.

### 2. Outbox Pattern vs Direct Publish
**Decision**: Transactional outbox polling (via `FOR UPDATE SKIP LOCKED`) instead of publishing directly to a queue inside the transaction.
**Tradeoff**: 
- *Pros*: Guarantees at-least-once delivery. If the app crashes immediately after a DB commit, the event isn't lost. 
- *Cons*: Introduces a minor delay (polling frequency) and requires a separate worker process.

### 3. Polling Reconciliation vs Event-Driven
**Decision**: Polling `in_flight` and `unknown` payments every minute via a background cron script.
**Tradeoff**:
- *Pros*: Extremely resilient. It catches payments that failed silently (e.g., OOM kill).
- *Cons*: Adds DB load (though indexed). Can delay final resolution of ambiguous payments up to the polling interval.

## Failure Mode Table

| Failure Mode | Detection | Mitigation | Final State |
|--------------|-----------|------------|-------------|
| Processor 500 (Internal Error) | HTTP Status 5xx | Immediate exponential backoff retry. If max retries hit, failover to next candidate. | `captured` via alternative processor, or `failed` if all exhausted. |
| Processor Timeout (Ambiguous) | ReadTimeout | Save as `ambiguous`. Do not failover. Background recon worker polls processor's `/lookup`. | `captured` or `failed` (resolved). |
| DB Disconnect mid-flight | `sqlalchemy.exc.OperationalError` | Fast fail request. Tx rolls back automatically. | Idempotency handles retry safely. |
| Outbox Worker Crash | Process death | Unacknowledged messages stay in `outbox_events` and are claimed by a new worker lock. | Event delivered. |

## Changes for Scale
1. **Partitioning**: Partition `ledger_entries` and `payment_attempts` by month to maintain fast insertion and sequential scans.
2. **Dedicated Queues**: Replace Postgres-based Outbox polling with Change Data Capture (Debezium + Kafka) for lower latency event streaming.
3. **Sharded Idempotency**: Move `idempotency_keys` to a distributed cache like Redis or a highly write-optimized key-value store (Aerospike/DynamoDB) to reduce lock contention on the primary RDBMS.
4. **Sub-Ledgers**: Introduce specialized rollup tables or materialize views for per-merchant accounting. Read replicas would serve these queries to isolate reporting from the critical path.
