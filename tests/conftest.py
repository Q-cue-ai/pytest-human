from collections.abc import Iterator

import pytest
from playwright.sync_api import Locator, LocatorAssertionsImpl, Page

from pytest_human.log import patch_all_public_methods, patch_method_logger

pytest_plugins = "pytester"


@pytest.fixture(autouse=True)
def log_3rdparty_methods() -> Iterator[None]:
    """
    Setup logging for 3rd party methods used in tests.

    Will only work in this test if using --runpytest subprocess, because of a conflict
    with the sub-pytest html logging.
    """
    with (
        patch_method_logger(
            pytest.Pytester.runpytest,
            pytest.Pytester.makepyfile,
        ),
        patch_all_public_methods(Page, Locator, LocatorAssertionsImpl),
    ):
        yield
