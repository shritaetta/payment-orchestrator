import httpx
from pydantic import BaseModel
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class ProcessorResult(BaseModel):
    status: str # 'succeeded', 'declined', 'retryable', 'ambiguous'
    charge_id: Optional[str] = None
    error_type: Optional[str] = None
    latency_ms: Optional[int] = None

class ProcessorClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.timeout = 2.0 # Strict timeout

    async def charge(self, amount_minor: int, idempotency_key: str) -> ProcessorResult:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/charge",
                    json={"amount_minor": amount_minor},
                    headers={"Idempotency-Key": idempotency_key}
                )
                
                # Check status
                if resp.status_code == 200:
                    data = resp.json()
                    return ProcessorResult(status='succeeded', charge_id=data['id'], latency_ms=int(resp.elapsed.total_seconds() * 1000))
                elif resp.status_code >= 500:
                    return ProcessorResult(status='retryable', error_type='server_error', latency_ms=int(resp.elapsed.total_seconds() * 1000))
                elif resp.status_code >= 400:
                    return ProcessorResult(status='declined', error_type='declined', latency_ms=int(resp.elapsed.total_seconds() * 1000))
                    
            except httpx.ReadTimeout as e:
                # Ambiguous: Request was sent, but we timed out reading the response
                return ProcessorResult(status='ambiguous', error_type='read_timeout')
            except httpx.ConnectError as e:
                # Retryable: Connection refused, request definitely didn't make it
                return ProcessorResult(status='retryable', error_type='connect_error')
            except Exception as e:
                return ProcessorResult(status='retryable', error_type=str(type(e).__name__))
                
        return ProcessorResult(status='retryable', error_type='unknown')

    async def lookup(self, idempotency_key: str) -> Optional[ProcessorResult]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(f"{self.base_url}/charges/{idempotency_key}")
                if resp.status_code == 200:
                    data = resp.json()
                    return ProcessorResult(status='succeeded', charge_id=data['id'], latency_ms=int(resp.elapsed.total_seconds() * 1000))
                elif resp.status_code == 404:
                    return ProcessorResult(status='not_found')
                elif resp.status_code >= 500:
                    return ProcessorResult(status='retryable', error_type='server_error')
            except Exception:
                return ProcessorResult(status='retryable', error_type='lookup_error')
        return None
