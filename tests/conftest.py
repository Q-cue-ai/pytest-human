from collections.abc import Iterator

import pytest
from playwright.sync_api import Locator, LocatorAssertionsImpl, Page

from pytest_human.log import log_calls, log_public_api

pytest_plugins = "pytester"


@pytest.fixture(autouse=True)
def log_3rdparty_methods() -> Iterator[None]:
    """
    Setup logging for 3rd party methods used in tests.

    Will only work in this test if using --runpytest subprocess, because of a conflict
    with the sub-pytest html logging.
    """
    with (
        log_calls(
            pytest.Pytester.runpytest,
            pytest.Pytester.makepyfile,
        ),
        log_calls(Page.screenshot, suppress_return=True),
        # this skips Page.screenshot as it is already defined above
        log_public_api(Page, Locator, LocatorAssertionsImpl),
    ):
        yield
