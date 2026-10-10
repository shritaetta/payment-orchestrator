-- audit.sql: Run this to verify system invariants

-- 1. Ledger Balance Check
-- The sum of all credits should exactly match the sum of all debits across the entire ledger.
SELECT 
    SUM(debits) AS total_debits, 
    SUM(credits) AS total_credits, 
    (SUM(debits) - SUM(credits)) AS imbalance
FROM ledger_entries;

-- 2. Per-Transaction Balance Check
-- Every individual transaction must have debits == credits.
-- Any rows returned here represent an unbalanced transaction.
SELECT txn_id, SUM(debits) AS txn_debits, SUM(credits) AS txn_credits
FROM ledger_entries
GROUP BY txn_id
HAVING SUM(debits) != SUM(credits);

-- 3. Payment Invariants Check
-- Refunded amount must never exceed the total captured amount.
-- Any rows returned here violate the basic invariant.
SELECT id, amount_minor, amount_refunded, status
FROM payments
WHERE amount_refunded > amount_minor OR amount_refunded < 0;

-- 4. Duplicate Captured Attempts Check
-- There should never be more than one successful attempt per payment.
SELECT payment_id, COUNT(*) AS successful_attempts
FROM payment_attempts
WHERE status = 'successful'
GROUP BY payment_id
HAVING COUNT(*) > 1;

-- 5. Orphaned In-Flight Attempts
-- Attempts that are stuck in 'in_flight' for more than 5 minutes.
SELECT id, payment_id, processor, created_at
FROM payment_attempts
WHERE status = 'in_flight' 
  AND created_at < NOW() - INTERVAL '5 minutes';

-- 6. Stuck Unknown Payments
-- Payments that have been 'unknown' for more than 5 minutes (should have been reconciled).
SELECT id, amount_minor, status, created_at, updated_at
FROM payments
WHERE status = 'unknown' 
  AND updated_at < NOW() - INTERVAL '5 minutes';
