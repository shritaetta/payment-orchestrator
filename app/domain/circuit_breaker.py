import time
from enum import Enum
from typing import Dict
from threading import Lock

class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, cooldown_seconds: int = 10):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        
        self.state = CircuitBreakerState.CLOSED
        self.failures = 0
        self.last_failure_time = 0.0
        self.lock = Lock()

    def record_failure(self) -> None:
        with self.lock:
            self.failures += 1
            if self.state == CircuitBreakerState.HALF_OPEN or self.failures >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                self.last_failure_time = time.time()

    def record_success(self) -> None:
        with self.lock:
            self.failures = 0
            self.state = CircuitBreakerState.CLOSED

    def can_execute(self) -> bool:
        with self.lock:
            if self.state == CircuitBreakerState.CLOSED:
                return True
            
            if self.state == CircuitBreakerState.OPEN:
                if time.time() - self.last_failure_time >= self.cooldown_seconds:
                    self.state = CircuitBreakerState.HALF_OPEN
                    return True
                return False
            
            # HALF_OPEN: We only let one request through to probe
            # For simplicity, returning True here means we might let multiple requests through concurrently
            # But the first failure puts it back to OPEN immediately, so it's fine for our constraints.
            return True

class CircuitBreakerManager:
    def __init__(self) -> None:
        self._breakers: Dict[str, CircuitBreaker] = {}
        self.lock = Lock()

    def get_breaker(self, processor_name: str) -> CircuitBreaker:
        with self.lock:
            if processor_name not in self._breakers:
                self._breakers[processor_name] = CircuitBreaker()
            return self._breakers[processor_name]

# Global singleton for in-memory tracking
circuit_breakers = CircuitBreakerManager()
