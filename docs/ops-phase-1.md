# Phase 1: CI foundation and structured logging

## Decisions Made

### CI Implementation
- Created `.github/workflows/ci.yml` to define the CI pipeline.
- Separated CI into multiple jobs for faster parallel execution: `lint`, `typecheck`, `unit_and_integration`, and `concurrency`.
- **Linting & Formatting**: Used `ruff` and `ruff format` to ensure code style consistency.
- **Typechecking**: Enabled `mypy --strict` on the `/app` directory. Fixed all existing errors rather than loosening the configuration.
- **Testing**: Configured pytest to run unit and integration tests against a Postgres 16 service container, with migrations applied via Alembic before the tests run.
- **Concurrency Job**: Separated the 1,000-parallel-same-key test into a dedicated job named `concurrency`.
- **Coverage Gate**: Added `pytest-cov` with a strict `--cov-fail-under=75` gate. It automatically publishes HTML coverage reports and pytest HTML reports as workflow artifacts.

### Branch Protection Requirements
The following jobs must be configured as required status checks in GitHub for the `main` branch:
1. `lint`
2. `typecheck`
3. `unit_and_integration`
4. `concurrency`

### Structured Logging
- Adopted `structlog` for structured JSON logging.
- Log lines feature ISO timestamps, severity levels, and `logger` names.
- Configured FastAPI middleware to extract `X-Correlation-ID` from incoming request headers or generate a new UUIDv4 if missing. 
- Integrated a custom structlog processor `add_correlation_id` using `contextvars` to attach the correlation ID automatically to every log event in the current request context.
- Modified the processor client (`ProcessorClient`), Outbox Worker (`outbox.py`), Reconciliation Worker (`reconciliation.py`), and the mock processors to log and propagate the correlation ID.
- Schema Migration: Added a `correlation_id` column to `PaymentAttempt` and `OutboxEvent` tables via Alembic to trace execution flows asynchronously across boundaries.
