from __future__ import annotations

import json
import asyncio
from pathlib import Path

import httpx

from app import logging_config
from app.main import app


def test_chat_response_log_exposes_quality_for_dashboard(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post(
                "/chat",
                json={
                    "user_id": "student-01",
                    "session_id": "session-01",
                    "feature": "qa",
                    "message": "Explain observability",
                },
            )

    response = asyncio.run(send_request())

    assert response.status_code == 200
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    response_event = next(event for event in events if event["event"] == "response_sent")
    assert response_event["quality_score"] == response.json()["quality_score"]
    assert response_event["ttft_ms"] == response.json()["ttft_ms"]
    assert response_event["tool_name"] == "retrieval"
    assert response_event["tool_success"] is True


def test_correlation_id_and_log_enrichment(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    async def run_scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Request without x-request-id (auto-generated)
            r1 = await client.post(
                "/chat",
                json={
                    "user_id": "user-A",
                    "session_id": "session-A",
                    "feature": "qa",
                    "message": "Hello from user A, email a@test.com",
                },
            )
            assert r1.status_code == 200
            cid1 = r1.headers.get("x-request-id")
            assert cid1 is not None and cid1.startswith("req-")
            assert "x-response-time-ms" in r1.headers
            assert r1.json()["correlation_id"] == cid1

            # 2. Request with custom x-request-id
            r2 = await client.post(
                "/chat",
                headers={"x-request-id": "req-custom99"},
                json={
                    "user_id": "user-B",
                    "session_id": "session-B",
                    "feature": "summary",
                    "message": "Hello from user B",
                },
            )
            assert r2.status_code == 200
            assert r2.headers.get("x-request-id") == "req-custom99"
            assert r2.json()["correlation_id"] == "req-custom99"

    asyncio.run(run_scenario())

    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    api_events = [e for e in events if e.get("service") == "api"]
    assert len(api_events) >= 4  # 2 request_received + 2 response_sent

    for e in api_events:
        assert "correlation_id" in e and e["correlation_id"] != "MISSING"
        assert "user_id_hash" in e
        assert "session_id" in e
        assert "feature" in e
        assert "model" in e
        assert "ts" in e
        assert "level" in e

    # Verify context isolation (user A events don't have session-B)
    user_a_events = [e for e in api_events if e["session_id"] == "session-A"]
    user_b_events = [e for e in api_events if e["session_id"] == "session-B"]
    assert len(user_a_events) == 2
    assert len(user_b_events) == 2
    assert user_a_events[0]["correlation_id"] != user_b_events[0]["correlation_id"]

    # Verify PII was scrubbed in log file
    raw_logs = log_path.read_text(encoding="utf-8")
    assert "a@test.com" not in raw_logs
    assert "[REDACTED_EMAIL]" in raw_logs

