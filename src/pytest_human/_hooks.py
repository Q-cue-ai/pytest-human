import pytest

import pytest_human._flags as flags
from pytest_human.fixtures import human  # noqa: F401
from pytest_human.log import TRACE_LEVEL_NUM, TestLogger
from pytest_human.plugin import HtmlLogPlugin


def pytest_addoption(parser: pytest.Parser) -> None:
    flags.register_flags(parser)


def pytest_cmdline_main(config: pytest.Config) -> None:
    """Set up trace logging level early enough to be detected by pytest command line parsing."""
    TestLogger.setup_trace_logging()


def setup_logging_color(config: pytest.Config) -> None:
    """Set up new trace level logging colors."""
    logging_plugin = config.pluginmanager.get_plugin("logging-plugin")
    if logging_plugin is None:
        return

    logging_plugin.log_cli_handler.formatter.add_color_level(TRACE_LEVEL_NUM, "white")


@pytest.hookimpl(trylast=True)
def pytest_configure(config: pytest.Config) -> None:
    setup_logging_color(config)
    flags.validate_flags(config)
    register_plugin(config)


def register_plugin(config: pytest.Config) -> None:
    enabled = config.getoption("enable_html_log")
    if not enabled:
        return

    HtmlLogPlugin.register(config)


def pytest_unconfigure(config: pytest.Config) -> None:
    HtmlLogPlugin.unregister(config)
