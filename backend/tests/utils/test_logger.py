import logging

from app.utils.logger import get_logger


def test_get_logger_returns_stdlib_logger_named_after_caller():
    logger = get_logger("test.module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test.module"


def test_get_logger_emits_message_with_module_and_function_context(caplog):
    logger = get_logger("test.module")
    with caplog.at_level(logging.INFO):
        logger.info("hello")
    record = caplog.records[-1]
    assert record.message == "hello"
    assert record.name == "test.module"
    assert record.funcName == "test_get_logger_emits_message_with_module_and_function_context"
