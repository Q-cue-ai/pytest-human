"""Fixtures provided by pytest-human."""

import pytest

from pytest_human.human import Human
from pytest_human.log import TestLogger


@pytest.fixture
def _human_log_only_to_html(request: pytest.FixtureRequest) -> bool:
    """Return whether Human object logging is only sent to HTML logger."""
    html_log_to_all = request.config.getoption("--html-log-to-all")
    return not html_log_to_all


@pytest.fixture
def human(request: pytest.FixtureRequest, _human_log_only_to_html: bool) -> Human:
    """Provide a human logger to the test."""
    return Human(request.node, _human_log_only_to_html)


@pytest.fixture
def test_log(human: Human) -> TestLogger:
    """Provides a test logger.

    This is equivalent to human.log.
    """
    return human.log
