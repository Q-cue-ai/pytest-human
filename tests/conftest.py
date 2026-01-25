from collections.abc import Iterator

import pytest
from playwright.sync_api import (
    Locator,
    LocatorAssertions,  # pyright: ignore[reportPrivateImportUsage]
    Page,
)

from pytest_human.tracing import trace_calls, trace_public_api

pytest_plugins = ["pytester", "tests.playwright_fixtures"]


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
        trace_calls(Page.screenshot, suppress_return=True, suppress_self=False, suppress_none=True),
        # this skips Page.screenshot as it is already defined above
        trace_public_api(
            Page,
            Locator,
            LocatorAssertions,
            suppress_self=False,
            suppress_none=True,
            suppress_init=True,
        ),
    ):
        yield
