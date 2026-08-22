import json

from app.logging.logger import get_logger


def test_get_logger_returns_bound_logger_with_json_output(capsys):
    logger = get_logger("test.module")
    logger.info("hello", key="value")
    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip().splitlines()[-1])
    assert payload["event"] == "hello"
    assert payload["key"] == "value"
    assert payload["logger"] == "test.module"


def test_get_logger_is_cached_per_name():
    a = get_logger("same.name")
    b = get_logger("same.name")
    assert a is b
