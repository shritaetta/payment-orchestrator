# Phase 2: Processors and the Ambiguous Timeout

## Goal
Handle real-world processor behavior, especially "did it charge or not?"

## Decisions Made

1. **Mock Processors**
   - Created three mock processors configurable via admin endpoints (`/admin/config`).
   - Mock processors support configurable latencies, 5xx rate, hard decline rate, and a `drop_response_mode` (simulates a successful charge but timing out the connection).
   - They honor idempotency keys to ensure they do not double charge.

2. **Processor Client Layer**
   - Developed `ProcessorClient` (`app/domain/processor_client.py`) that classifies HTTP exceptions and status codes into our predefined state-machine transitions: `succeeded`, `declined`, `retryable` (e.g. 502/503 or connection refused), and `ambiguous` (e.g. read timeout after the connection was successfully established).

3. **Crash-Safe Charge Flow**
   - Updated the orchestration (`create_and_capture_payment`) to use a crash-safe flow.
   - **Tx 1 (Prepare):** Creates `Payment` and `PaymentAttempt` with status `in_flight`. Uses a deterministic processor idempotency key (the `payment_id` concatenated with an attempt counter, or the original idempotent key string).
   - **Tx 2 (Record):** Updates the `Payment` and `PaymentAttempt` statuses post-processor call and writes ledger entries if successful.

4. **Reconciliation Worker**
   - Implemented an asynchronous reconciliation worker (`app/workers/reconciliation.py`).
   - Selects payments in `unknown` state, or `processing` state where the `PaymentAttempt` is `in_flight` and older than 5 seconds.
   - Uses `SELECT ... FOR UPDATE SKIP LOCKED` to lock rows and prevent race conditions if multiple workers run concurrently.
   - Checks processor status via the processor's lookup endpoint to resolve `ambiguous`/`unknown` states to either `captured`, `failed`, or leave them to be retried.
   - Posts ledger entries for payments found to be successfully captured.

5. **Testing**
   - Implemented tests to verify the `drop_response_mode` correctly handles read timeouts by leaving the payment in an `unknown` state and then correctly reconciling it into a `captured` state upon lookup.
   - Added `test_crash_safety` that injects a failure simulating the application dying directly after issuing the payment command to the processor but before `Tx 2` is committed, confirming that the worker will cleanly pick it up and reconcile it.
