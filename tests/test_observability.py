"""Covers request correlation, access logging and the health endpoint."""

import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.observability import LOGGER_NAME, REQUEST_ID_HEADER, JsonFormatter, record_context


def test_health_reports_that_the_service_is_up(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_every_response_carries_a_request_id(client: TestClient) -> None:
    assert client.get("/health").headers[REQUEST_ID_HEADER]


def test_an_inbound_request_id_is_carried_through(client: TestClient) -> None:
    response = client.get("/health", headers={REQUEST_ID_HEADER: "trace-from-the-proxy"})

    assert response.headers[REQUEST_ID_HEADER] == "trace-from-the-proxy"


def test_the_request_is_logged_with_its_method_path_and_status(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        client.get("/health")

    records = [record for record in caplog.records if record.name == LOGGER_NAME]
    assert records, "the access logger recorded nothing"

    context = record_context(records[0])
    assert context["method"] == "GET"
    assert context["path"] == "/health"
    assert context["status"] == 200
    assert context["duration_ms"] >= 0


def test_records_are_rendered_as_single_line_json() -> None:
    record = logging.makeLogRecord(
        {
            "name": LOGGER_NAME,
            "levelname": "INFO",
            "msg": "request",
            "context": {"request_id": "abc", "status": 200},
        }
    )

    rendered = JsonFormatter().format(record)

    assert "\n" not in rendered
    assert json.loads(rendered)["request_id"] == "abc"
    assert json.loads(rendered)["event"] == "request"
