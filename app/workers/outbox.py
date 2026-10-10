import asyncio
import logging
import hmac
import hashlib
import json
import time
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
import httpx

from app.db.models import OutboxEvent, DeadLetter

import structlog

logger = structlog.get_logger(__name__)

WEBHOOK_URL = "http://localhost:8004/webhook"
WEBHOOK_SECRET = b"my-super-secret-key"
MAX_ATTEMPTS = 5

def generate_signature(payload_str: str, timestamp: str) -> str:
    message = f"{timestamp}.{payload_str}".encode('utf-8')
    return hmac.new(WEBHOOK_SECRET, message, hashlib.sha256).hexdigest()

async def process_outbox_events(db: AsyncSession) -> int:
    now = datetime.now(timezone.utc)
    
    # Claim events
    stmt = (
        select(OutboxEvent)
        .where(
            (OutboxEvent.status == 'pending') &
            (OutboxEvent.next_attempt_at <= now)
        )
        .with_for_update(skip_locked=True)
        .limit(50)
    )
    
    events = (await db.execute(stmt)).scalars().all()
    if not events:
        return 0
        
    async with httpx.AsyncClient() as client:
        for event in events:
            if event.correlation_id:
                from app.logging import set_correlation_id
                set_correlation_id(event.correlation_id)
            
            logger.info("processing_outbox_event", event_id=str(event.id), aggregate_type=event.aggregate_type)
            
            payload_str = json.dumps(event.payload, separators=(',', ':'))
            timestamp = str(int(time.time()))
            signature = generate_signature(payload_str, timestamp)
            
            headers = {
                "Content-Type": "application/json",
                "Webhook-Timestamp": timestamp,
                "Webhook-Signature": signature
            }
            
            success = False
            last_error = ""
            try:
                resp = await client.post(WEBHOOK_URL, content=payload_str, headers=headers, timeout=5.0)
                if resp.status_code in (200, 201, 202, 204):
                    success = True
                else:
                    last_error = f"HTTP {resp.status_code}: {resp.text}"
            except Exception as e:
                last_error = str(e)
                
            event.attempts += 1
            
            if success:
                event.status = 'processed'
                event.processed_at = datetime.now(timezone.utc)
            else:
                if event.attempts >= MAX_ATTEMPTS:
                    # Move to dead letters
                    event.status = 'failed'
                    dead_letter = DeadLetter(
                        event_id=event.id,
                        error_reason=last_error
                    )
                    db.add(dead_letter)
                else:
                    # Exponential backoff
                    delay_seconds = 2 ** event.attempts
                    event.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
                    
    await db.commit()
    return len(events)
