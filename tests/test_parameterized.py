import re

import pytest
from _pytest.config import ExitCode
from playwright.sync_api import Page, expect

from tests import utils


def test_parameterized_fixture_expect_parameter_in_title(
    pytester: pytest.Pytester, page: Page
) -> None:
    """Test that parameterized fixture tests are logged correctly."""
    pytester.makepyfile("""
        import pytest

        @pytest.fixture(params=["blah"])
        def some_value(request):
            return request.param

        def test_parameter(some_value):
            assert some_value == "blah"
    """)

    result = pytester.runpytest("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == ExitCode.OK

    page.goto(html_path.as_uri())
    expect(page).to_have_title("test_parameter[blah]")

    header_title = page.locator(".report-header h1")
    expect(header_title).to_have_text("test_parameter[blah]")


def test_parameterized_test_expect_parameter_in_title(
    pytester: pytest.Pytester, page: Page
) -> None:
    """Test that parameterized fixture tests are logged correctly."""
    pytester.makepyfile("""
        import pytest

        @pytest.mark.parametrize("some_value, other_value", [
            (5, "test"),
        ])
        def test_parameter(some_value, other_value):
            assert some_value == 5
            assert other_value == "test"
    """)

    result = pytester.runpytest("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == ExitCode.OK

    page.goto(html_path.as_uri())
    expect(page).to_have_title("test_parameter[5-test]")

    header_title = page.locator(".report-header h1")
    expect(header_title).to_have_text("test_parameter[5-test]")
