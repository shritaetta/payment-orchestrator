# Comparison to Hyperswitch

Hyperswitch is an open-source payments switch designed to unify multiple payment processors. While highly capable, its design is extremely complex to cater to a massive surface area of integrations and features. This Payment Orchestrator aims for a narrower scope but achieves extreme resilience with less complexity.

## 1. Routing and Retry Strategy
- **Hyperswitch**: Uses a DSL-based routing engine (often driven by Rust macros and custom scripting languages or dynamic DB configs). Retries are sophisticated, handling cascades across distinct payment methods (e.g. failing over from Card to Apple Pay).
- **Our Approach**: Rules-based fallback leveraging raw `success_rate` from the DB and basic static attributes. Retries are strictly segregated between *retryable* (5xx) and *ambiguous* (network timeouts), preventing double-charges entirely by forbidding failover on ambiguous states.

## 2. Connector Abstraction
- **Hyperswitch**: Connectors are implemented as massive Rust structs that implement traits for every possible payment flow (Authorize, Capture, Sync, Cancel). Handling API quirks requires building deep into the trait implementation.
- **Our Approach**: `ProcessorClient` is incredibly thin. It reduces everything to a standardized `ProcessorResult` (`succeeded`, `declined`, `retryable`, `ambiguous`). Quirks are isolated to the translation layer, and the core domain code only speaks the language of `ProcessorResult`.

## 3. The State Model
- **Hyperswitch**: Highly normalized state spanning multiple domain tables (`payment_intent`, `payment_attempt`, `refunds`, `mandates`), each with a dozen enums. State transitions are governed by an application-level state machine.
- **Our Approach**: Simpler schema (`payments`, `payment_attempts`, `ledger_entries`). Transitions are physically clamped by Postgres `CHECK` constraints (e.g., you literally cannot update a ledger entry, nor can you refund more than `amount_minor`).

## Why this project is simpler
1. **No Application-Level Locks**: Hyperswitch relies heavily on distributed locks (Redis). We rely exclusively on Postgres row-level locks (`SELECT FOR UPDATE`) and `INSERT ON CONFLICT`, stripping away the distributed cache dependency for correctness.
2. **Double-Entry Ledger Foundation**: Instead of calculating balances by summing application states, all financial state is derived from `ledger_entries`. Refunds and captures are just debits and credits, dramatically reducing edge cases.
