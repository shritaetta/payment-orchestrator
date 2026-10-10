import pytest
import httpx
import uuid
import json
import logging
from io import StringIO
from fastapi.testclient import TestClient

from app.main import app

def test_json_logging_and_correlation_id():
    # Setup a string buffer to capture logs
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    
    # We want to capture structlog output. Structlog is wired into logging in our app.
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    client = TestClient(app)
    
    corr_id = str(uuid.uuid4())
    resp = client.post("/payments", json={
        "amount_minor": 1000,
        "idempotency_key": str(uuid.uuid4())
    }, headers={"X-Correlation-ID": corr_id})
    
    # Fast path or something might not hit logger if we don't have log statements in endpoints.
    # Wait, we don't have explicit logger.info() in our endpoints yet?
    # Let's verify we get a correlation ID in the response headers!
    assert resp.headers["X-Correlation-ID"] == corr_id
    
    logger.removeHandler(handler)
    
    # We should see the log in log_output
    log_output = log_stream.getvalue()
    
    # Assert there is at least one log line
    lines = [line for line in log_output.strip().split('\n') if line]
    assert len(lines) >= 1
    
    # Parse the first JSON log line
    log_data = json.loads(lines[0])
    
    # Verify structlog format
    assert log_data["event"] == "create_payment_request"
    assert log_data["correlation_id"] == corr_id
    assert "timestamp" in log_data
    assert log_data["level"] == "info"
    assert "logger" in log_data
