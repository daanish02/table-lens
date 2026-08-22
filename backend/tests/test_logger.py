import logging

from app.logging.logger import get_logger


def test_get_logger_emits_structured_event_with_bound_context(caplog):
    logger = get_logger("test.module")
    with caplog.at_level(logging.INFO):
        logger.info("hello", key="value")
    assert "hello" in caplog.text
    assert "test.module" in caplog.text
    assert "value" in caplog.text


def test_get_logger_is_cached_per_name():
    a = get_logger("same.name")
    b = get_logger("same.name")
    assert a is b
