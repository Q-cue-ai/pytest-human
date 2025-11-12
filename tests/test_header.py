import pytest
from playwright.sync_api import Page, expect

from tests import utils


def test_header_title(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        def test_title(human):
            human.warning("This is an INFO log message.")
    """)

    result = pytester.runpytest_subprocess("--enable-html-log")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    expect(page).to_have_title("test_title")

    header_title = page.locator(".report-header h1")
    expect(header_title).to_have_text("test_title")


def test_header_description(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        def test_description(human):
            '''This is a test with a funky description.'''

            human.warning("This is an INFO log message.")
    """)

    result = pytester.runpytest_subprocess("--enable-html-log")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    header_description = page.locator(".report-header .description")
    expect(header_description).to_have_text("This is a test with a funky description.")
