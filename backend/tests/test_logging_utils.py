import asyncio
import json
import logging

import pytest
from app.logging_utils import JsonFormatter, log_call


def _make_record(**extra) -> logging.LogRecord:
    record = logging.LogRecord(
        name="visionnaire",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="something happened",
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_produces_expected_fields():
    record = _make_record(
        operation="qdrant.upsert_photo", duration_ms=12.3, photo_id="abc123"
    )
    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "visionnaire"
    assert payload["message"] == "something happened"
    assert payload["operation"] == "qdrant.upsert_photo"
    assert payload["duration_ms"] == 12.3
    assert payload["photo_id"] == "abc123"
    assert "exception" not in payload


def test_json_formatter_includes_exception_when_exc_info_set():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="visionnaire",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="op failed",
            args=(),
            exc_info=sys.exc_info(),
        )

    payload = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in payload["exception"]


def test_log_call_logs_completed_with_context_on_success(caplog):
    @log_call("test.op", context_keys=("photo_id",))
    async def fake_op(photo_id: str, secret_blob: bytes) -> str:
        return "ok"

    with caplog.at_level(logging.INFO, logger="visionnaire"):
        result = asyncio.run(fake_op("abc123", b"should not be logged"))

    assert result == "ok"
    record = next(r for r in caplog.records if r.name == "visionnaire")
    assert record.getMessage() == "test.op completed"
    assert record.operation == "test.op"
    assert record.photo_id == "abc123"
    assert not hasattr(record, "secret_blob")
    assert isinstance(record.duration_ms, float)


def test_log_call_logs_failed_and_reraises_on_exception(caplog):
    @log_call("test.fail", context_keys=("photo_id",))
    async def fake_fail(photo_id: str) -> None:
        raise ValueError("boom")

    with caplog.at_level(logging.INFO, logger="visionnaire"):
        with pytest.raises(ValueError, match="boom"):
            asyncio.run(fake_fail("xyz789"))

    record = next(r for r in caplog.records if r.name == "visionnaire")
    assert record.getMessage() == "test.fail failed"
    assert record.levelname == "ERROR"
    assert record.photo_id == "xyz789"
    assert record.exc_info is not None
