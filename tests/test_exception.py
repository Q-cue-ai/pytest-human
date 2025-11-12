import re

import pytest
from _pytest.config import ExitCode
from playwright.sync_api import Page, expect

from tests import utils


def test_exception_test_throws(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        from pytest_human.fixtures import test_log

        def test_exception(test_log):
            test_log.warning("Before exception.")
            raise ValueError("This is a test exception.")
            test_log.warning("After exception.")
    """)

    result = pytester.runpytest_subprocess("--enable-html-log")
    html_path = utils.find_test_log_location(result)
    assert result.ret == ExitCode.TESTS_FAILED

    page.goto(html_path.as_uri())
    exception = page.locator("tr.log-level-error").filter(visible=True)
    expect(exception).to_have_count(1)
    expect(exception.locator("td.level-cell")).to_have_text("ERROR")
    expect(exception.locator("td.source-cell")).to_have_text("test_exception")
    exception_span = utils.open_span(page, "Exception: ValueError This is a test exception.")
    expect(exception_span.locator("td.msg-cell").first).to_contain_text(re.compile("^traceback"))
