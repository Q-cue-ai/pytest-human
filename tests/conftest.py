from collections.abc import Iterator

import pytest
from playwright.sync_api import Locator, LocatorAssertionsImpl, Page

from pytest_human.tracing import trace_calls, trace_public_api

pytest_plugins = "pytester"


@pytest.fixture(autouse=True)
def _log_3rdparty_methods() -> Iterator[None]:
    """
    Setup logging for 3rd party methods used in tests.

    Will only work in this test if using --runpytest subprocess, because of a conflict
    with the sub-pytest html logging.
    """
    with (
        trace_calls(
            pytest.Pytester.runpytest,
            pytest.Pytester.makepyfile,
        ),
        trace_calls(Page.screenshot, suppress_return=True, suppress_self=False),
        # this skips Page.screenshot as it is already defined above
        trace_public_api(Page, Locator, LocatorAssertionsImpl, suppress_self=False),
    ):
        yield
