import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import OutboxEvent

def publish_event(db: AsyncSession, aggregate_type: str, aggregate_id: str, payload: dict):
    event = OutboxEvent(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload
    )
    db.add(event)
