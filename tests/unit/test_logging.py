import json
import logging

import pytest
import structlog
from rm_core.logging import REDACTED, bind_context, clear_context, configure_logging


def _lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    return [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]


def test_json_lines_carry_bound_context(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO", json_logs=True)
    clear_context()
    bind_context(request_id="req-12345678", user_id="u1", audit_id=None)
    structlog.get_logger("t").info("hello", extra_field=1)
    clear_context()
    (line,) = _lines(capsys)
    assert line["event"] == "hello"
    assert line["request_id"] == "req-12345678"
    assert line["user_id"] == "u1"
    assert "audit_id" not in line
    assert line["level"] == "info"
    assert str(line["timestamp"]).endswith("Z")


def test_sensitive_keys_are_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO", json_logs=True)
    structlog.get_logger("t").info("login", email="a@example.test", Authorization="Bearer x", listing="ID1")
    (line,) = _lines(capsys)
    assert line["email"] == REDACTED
    assert line["Authorization"] == REDACTED
    assert line["listing"] == "ID1"
    assert "a@example.test" not in json.dumps(line)


def test_stdlib_loggers_are_rendered_as_json(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO", json_logs=True)
    logging.getLogger("uvicorn.error").warning("from uvicorn")
    (line,) = _lines(capsys)
    assert line["event"] == "from uvicorn"
    assert line["level"] == "warning"


def test_level_filters_debug(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="WARNING", json_logs=True)
    structlog.get_logger("t").info("quiet")
    assert _lines(capsys) == []
