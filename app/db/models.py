import uuid
from datetime import datetime, timezone
from typing import Optional

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
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def utcnow():
    return datetime.now(timezone.utc)

class AllowedTransition(Base):
    __tablename__ = 'allowed_transitions'
    from_status = Column(String(50), primary_key=True)
    to_status = Column(String(50), primary_key=True)

class Payment(Base):
    __tablename__ = 'payments'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    amount_minor = Column(BigInteger, CheckConstraint('amount_minor > 0'), nullable=False)
    status = Column(String(50), nullable=False, default='created')
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

class IdempotencyKey(Base):
    __tablename__ = 'idempotency_keys'
    key = Column(String(255), primary_key=True)
    request_hash = Column(String(255), nullable=False)
    locked_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    status = Column(String(50), nullable=False, default='in_progress') # 'in_progress', 'completed'
    response_code = Column(Integer, nullable=True)
    response_body = Column(JSONB, nullable=True)

class PaymentAttempt(Base):
    __tablename__ = 'payment_attempts'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(UUID(as_uuid=True), ForeignKey('payments.id'), nullable=False)
    processor = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

class LedgerAccount(Base):
    __tablename__ = 'ledger_accounts'
    id = Column(String(50), primary_key=True)
    name = Column(String(255), nullable=False)

class LedgerEntry(Base):
    __tablename__ = 'ledger_entries'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    txn_id = Column(UUID(as_uuid=True), nullable=False)
    account_id = Column(String(50), ForeignKey('ledger_accounts.id'), nullable=False)
    debits = Column(BigInteger, nullable=False, default=0)
    credits = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

class OutboxEvent(Base):
    __tablename__ = 'outbox_events'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aggregate_type = Column(String(50), nullable=False)
    aggregate_id = Column(String(255), nullable=False)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    processed_at = Column(DateTime(timezone=True), nullable=True)

class DeadLetter(Base):
    __tablename__ = 'dead_letters'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey('outbox_events.id'), nullable=False)
    error_reason = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
