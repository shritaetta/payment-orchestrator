from datetime import datetime, timedelta, timezone
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from dataclasses import dataclass

from app.domain.circuit_breaker import circuit_breakers

@dataclass
class ProcessorConfig:
    name: str
    url: str
    supported_currencies: List[str]
    max_amount_minor: int
    base_fee: int
    fee_percent: float

PROCESSORS = [
    ProcessorConfig(
        name="processor_a",
        url="http://localhost:8001",
        supported_currencies=["USD", "EUR"],
        max_amount_minor=1000000,
        base_fee=10,
        fee_percent=0.029,
    ),
    ProcessorConfig(
        name="processor_b",
        url="http://localhost:8002",
        supported_currencies=["USD"],
        max_amount_minor=500000,
        base_fee=5,
        fee_percent=0.025,
    ),
    ProcessorConfig(
        name="processor_c",
        url="http://localhost:8003",
        supported_currencies=["USD", "GBP"],
        max_amount_minor=2000000,
        base_fee=20,
        fee_percent=0.015,
    )
]

async def get_processor_success_rates(db: AsyncSession) -> dict[str, float]:
    """Returns success rate (0.0 to 1.0) for processors over the last 5 minutes."""
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(minutes=5)
    
    query = text("""
        SELECT processor, 
               COUNT(*) FILTER (WHERE status = 'successful') * 1.0 / COUNT(*) AS success_rate
        FROM payment_attempts
        WHERE created_at > :threshold
        GROUP BY processor
    """)
    result = await db.execute(query, {"threshold": threshold})
    await db.commit() # Close the autobegun transaction
    return {row[0]: float(row[1]) for row in result.all()}

async def route_payment(amount_minor: int, currency: str, db: AsyncSession) -> List[ProcessorConfig]:
    """
    Returns an ordered list of candidates for failover.
    Rules:
    1. Filter out processors by currency support and amount limits.
    2. Filter out processors whose circuit breaker is OPEN.
    3. Order by rolling success rate (desc) and fee cost (asc).
    """
    candidates = []
    for p in PROCESSORS:
        if currency not in p.supported_currencies:
            continue
        if amount_minor > p.max_amount_minor:
            continue
            
        breaker = circuit_breakers.get_breaker(p.name)
        if not breaker.can_execute():
            continue
            
        candidates.append(p)
        
    if not candidates:
        return []
        
    success_rates = await get_processor_success_rates(db)
    
    def score(p: ProcessorConfig) -> tuple[float, float]:
        rate = success_rates.get(p.name, 1.0) # default 100% success if no data
        fee = p.base_fee + int(amount_minor * p.fee_percent)
        # Sort descending by rate, ascending by fee. 
        # Using a tuple: (-rate, fee) so default sorting works.
        return (-rate, fee)
        
    candidates.sort(key=score)
    return candidates
