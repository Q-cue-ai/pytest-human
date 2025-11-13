import inspect
import logging
import time

from pytest_human.log import get_logger, traced


@traced()
def insert_db(data):
    query = "INSERT INTO flowers (petals) VALUES ('{{1,2,3,4,5}}');"
    logging.info(f"executing {query=}")
    return len(data)


def test_example(human):
    """This test demonstrates pytest-human logging."""
    human.info("Established test agent connection")

    with human.span_info("Generating sample data"):
        data = [1, 2, 3, 4, 5]
        human.info(f"Loaded sample data {data=} {len(data)=}", highlight=True)
        insert_db(data)

        with human.span_debug("Validating sample"):
            result = sum(data)
            human.debug(f"Sum {result=}", highlight=True)

    assert result == 15


def test_logging_methods(human):
    # Basic logging at different levels
    human.trace("Trace level message")
    human.debug("Debug level message")
    human.info("Info level message")
    human.warning("Warning level message")
    human.error("Error level message")
    human.critical("Critical level message")

    # Syntax highlighting for code
    code = """
    import numpy as np

    def bark(volume: float) -> bool:
        return volume > 0.5:
    """
    code = inspect.cleandoc(code)
    human.info(code, highlight=True)


def load_config():
    return {}


def process_data():
    pass


def test_spans(human):
    human.info("Starting complex operation")

    # Top-level span
    with human.span_info("Phase 1: Initialization"):
        human.debug("Initializing resources...")

        # Nested span
        with human.span_debug("Loading configuration"):
            human.trace("Reading config file")
            config = load_config()
            human.debug(f"Config loaded: {config}")

        human.info("Initialization complete")

    # Another top-level span
    with human.span_info("Phase 2: Processing"):
        human.debug("Processing data...")
        process_data()

    human.info("Operation completed")


@traced()
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
