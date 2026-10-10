import logging
import structlog
import uuid
from contextvars import ContextVar
from typing import Optional, Any, MutableMapping

correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

def set_correlation_id(corr_id: str) -> None:
    correlation_id_var.set(corr_id)

def get_correlation_id() -> Optional[str]:
    return correlation_id_var.get()

def add_correlation_id(logger: Any, method_name: str, event_dict: "MutableMapping[str, Any]") -> "MutableMapping[str, Any]":
    corr_id = get_correlation_id()
    if corr_id:
        event_dict["correlation_id"] = corr_id
    return event_dict

def redact_sensitive_data(logger: Any, method_name: str, event_dict: "MutableMapping[str, Any]") -> "MutableMapping[str, Any]":
    # Very basic redaction if someone logs full payloads
    if "payload" in event_dict:
        # Avoid mutating the original payload dict if it's passed directly
        payload = event_dict["payload"]
        if isinstance(payload, dict):
            redacted = payload.copy()
            for key in ["card_number", "cvv", "hmac_key", "secret"]:
                if key in redacted:
                    redacted[key] = "***REDACTED***"
            event_dict["payload"] = redacted
    return event_dict

def setup_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            add_correlation_id,
            redact_sensitive_data,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure stdlib logging to route through structlog
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
    )
