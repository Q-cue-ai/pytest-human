"""Example tests from README.md"""

import inspect
import logging
import time

from pytest_human.log import get_logger
from pytest_human.tracing import traced


@traced
def insert_db(data):
    query = "INSERT INTO flowers (petals) VALUES ('{{1,2,3,4,5}}');"
    logging.info(f"executing {query=}")
    return len(data)


def test_example(human):
    """This test demonstrates pytest-human logging."""
    human.log.info("Established test agent connection")

    with human.span.info("Generating sample data"):
        data = [1, 2, 3, 4, 5]
        human.log.info(f"Loaded sample data {data=} {len(data)=}", highlight=True)
        insert_db(data)

        with human.span.debug("Validating sample"):
            result = sum(data)
            human.log.debug(f"Sum {result=}", highlight=True)

    assert result == 15


def test_logging_methods(human):
    # Basic logging at different levels
    human.log.trace("Trace level message")
    human.log.debug("Debug level message")
    human.log.info("Info level message")
    human.log.warning("Warning level message")
    human.log.error("Error level message")
    human.log.critical("Critical level message")

    # Syntax highlighting for code
    code = """
    import numpy as np

    def bark(volume: float) -> bool:
        return volume > 0.5:
    """
    code = inspect.cleandoc(code)
    human.log.info(code, highlight=True)


def load_config():
    return {}


def process_data():
    pass


def test_spans(human):
    human.log.info("Starting complex operation")

    with human.span.info("Phase 1: Initialization"):
        human.log.debug("Initializing resources...")

        with human.span.debug("Loading configuration"):
            human.log.trace("Reading config file")
            config = load_config()
            human.log.debug(f"Config loaded: {config}")

        human.log.info("Initialization complete")

    with human.span.info("Phase 2: Processing"):
        human.log.debug("Processing data...")
        process_data()

    human.log.info("Operation completed")


# Add the @traced decorator for automatic logging of method call/return
@traced
def save_login(login):
    log = get_logger(__name__)
    log.info("a log inside save_login")
    return update_db(login)


@traced(log_level=logging.TRACE)
def update_db(login):
    log = get_logger(__name__)
    delay_time = 2
    log.info("delaying by 2 seconds")
    time.sleep(delay_time)
    return delay_time


def test_method_tracing(human):
    delay = save_login("hello")
    assert delay == 2


def test_artifacts(human):
    human.log.info("Attaching artifacts to the test report")

    print("logging something to stdout")

    log_content = inspect.cleandoc("""
    [10:00:01] First line of the log.
    [10:00:03] Line 2 of the log.
    [10:00:05] Line 3 of the log.
    """)
    human.artifacts.add_log_text(log_content, "sample.log", description="Sample log file")
