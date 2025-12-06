import warnings
from pathlib import Path

import pytest


def _validate_dir_flags(config: pytest.Config) -> None:
    custom_dir = config.getoption("html_output_dir")
    use_test_tmp = config.getoption("html_use_test_tmp")

    if custom_dir is not None and use_test_tmp:
        warnings.warn(
            pytest.PytestConfigWarning(
                "The --html-output-dir will override the --html-use-test-tmp option."
            )
        )


def is_output_to_test_tmp(config: pytest.Config) -> bool:
    if config.getoption("html_output_dir"):
        return False

    return config.getoption("html_use_test_tmp")


def is_live_logging_enabled(config: pytest.Config) -> bool:
    """Check if live logging is enabled."""
    return config.getini("log_cli")


def is_quiet_mode_enabled(config: pytest.Config) -> bool:
    """Check if quiet mode is enabled for pytest-human."""
    return config.getoption("quiet", config.getoption("html_quiet"))


def validate_flags(config: pytest.Config) -> None:
    _validate_dir_flags(config)


def register_flags(parser: pytest.Parser) -> None:
    group = parser.getgroup("human")
    group.addoption(
        "--enable-html-log",
        action="store_true",
        default=False,
        help="enable HTML nested test report.",
    )
    group.addoption(
        "--html-use-test-tmp",
        action="store_true",
        default=False,
        help="""
        Stores HTML test logs in each test's temporary directory instead of the default session-wide
        temporary directory.
        """,
    )
    group.addoption(
        "--html-output-dir",
        type=Path,
        help="""
        If present, store all HTML test logs in the specified directory.
        Creates the directory if it does not exist.
        """,
    )

    group.addoption(
        "--html-log-level",
        type=str,
        default=None,
        help="""
        Set the logging level for HTML test logs. Does not override the root logger level.
        If you need to override the root logger level, use the standard pytest `--log-level` option.
        Example levels: TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL.
        """,
    )

    group.addoption(
        "--html-quiet",
        action="store_true",
        default=False,
        help="Remove console logging output from pytest-human when HTML logging is enabled.",
    )

    group.addoption(
        "--html-log-to-all",
        action="store_true",
        default=False,
        help="""Send all pytest-human logs to every logger, not just the HTML log file.
        """,
    )
