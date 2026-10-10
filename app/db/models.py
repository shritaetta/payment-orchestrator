import uuid
from datetime import datetime, timezone
from typing import Optional, Any

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    CheckConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class AllowedTransition(Base):
    __tablename__ = 'allowed_transitions'
    from_status: Mapped[str] = mapped_column(String(50), primary_key=True)
    to_status: Mapped[str] = mapped_column(String(50), primary_key=True)

class Payment(Base):
    __tablename__ = 'payments'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    amount_minor: Mapped[int] = mapped_column(BigInteger, CheckConstraint('amount_minor > 0'), nullable=False)
    amount_refunded: Mapped[int] = mapped_column(BigInteger, CheckConstraint('amount_refunded >= 0 AND amount_refunded <= amount_minor'), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default='created')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

class IdempotencyKey(Base):
    __tablename__ = 'idempotency_keys'
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default='in_progress') # 'in_progress', 'completed'
    response_code: Mapped[int] = mapped_column(Integer, nullable=True)
    response_body: Mapped[dict[str, "Any"]] = mapped_column(JSONB, nullable=True)

class PaymentAttempt(Base):
    __tablename__ = 'payment_attempts'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('payments.id'), nullable=False)
    processor: Mapped[str] = mapped_column(String(50), nullable=False)
    processor_idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False) # 'in_flight', 'successful', 'failed', 'ambiguous'
    error_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=True)

class LedgerAccount(Base):
    __tablename__ = 'ledger_accounts'
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

class LedgerEntry(Base):
    __tablename__ = 'ledger_entries'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    txn_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    account_id: Mapped[str] = mapped_column(String(50), ForeignKey('ledger_accounts.id'), nullable=False)
    debits: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    credits: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

class OutboxEvent(Base):
    __tablename__ = 'outbox_events'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, "Any"]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default='pending') # pending, processed, failed
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=True)

class DeadLetter(Base):
    __tablename__ = 'dead_letters'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('outbox_events.id'), nullable=False)
    error_reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
