# Phase 1: Correctness Core

## Goal
Establish a single-processor-free skeleton where the database makes double-charging and unbalanced books impossible.

## Decisions Made

- **Tech Stack & ORM**: We utilized FastAPI, asyncpg, and SQLAlchemy 2 (async). Alembic was set up with async environment to manage migrations.
- **Data Integrity at the DB Level**: Instead of relying solely on application-level checks, we injected strict database triggers and constraints directly into the Alembic migration script to guarantee consistency:
  - **State Machine**: A `BEFORE UPDATE OF status` trigger on `payments` checks all status transitions against the `allowed_transitions` table, rejecting any illegal paths (e.g., `captured` to `created`).
  - **Append-only Ledger**: A `BEFORE UPDATE OR DELETE` trigger on `ledger_entries` throws a hard error if any historical financial data is mutated.
  - **Balanced Books**: A `DEFERRABLE INITIALLY DEFERRED` trigger verifies that `SUM(debits) = SUM(credits)` per `txn_id` at transaction commit. If not perfectly zeroed, the transaction automatically rolls back.
- **Idempotency Flow**: 
  - An `IdempotencyKey` table tracks `request_hash`, `locked_at`, and `status`. 
  - `INSERT ... ON CONFLICT DO NOTHING` is utilized for safely gating concurrent processing.
  - Stale locks older than 2 minutes are recovered through guarded `UPDATE ... WHERE locked_at < timeout` logic.
  - Processed payments serialize their status and store it directly onto the completed idempotency key, allowing seamless identical responses on replay.
- **Testing**: We validated invariants via Pytest with an event loop per test to isolate DB sessions. 1,000 concurrent requests correctly produce exactly one payment without DB connection lockups or racing inserts. TRUNCATE CASCADE is used for cleanup in tests because the ledger block trigger prevents normal DELETEs.

## Current State
All acceptance tests pass. Phase 1 is complete.
