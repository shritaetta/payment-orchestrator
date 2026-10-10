import json
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import OutboxEvent

def publish_event(db: AsyncSession, aggregate_type: str, aggregate_id: str, payload: dict[str, Any]) -> None:
    from app.logging import get_correlation_id
    event = OutboxEvent(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        correlation_id=get_correlation_id()
    )
    db.add(event)
