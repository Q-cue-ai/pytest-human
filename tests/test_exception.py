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


def test_exception_xfail_test_throws(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        from pytest_human.fixtures import test_log
        import pytest

        @pytest.mark.xfail
        def test_exception_xfail(test_log):
            test_log.info("Before exception.")
            raise ValueError("This is a test exception.")
            test_log.info("After exception.")
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=info")
    html_path = utils.find_test_log_location(result)
    assert result.ret == ExitCode.OK

    page.goto(html_path.as_uri())
    exception = page.locator("tr.log-level-warning").filter(visible=True)
    expect(exception).to_have_count(1)
    expect(exception.locator("td.level-cell")).to_have_text("WARNING")
    expect(exception.locator("td.source-cell")).to_have_text("test_exception_xfail")
    expect(exception.locator("td.msg-cell")).to_contain_text(re.compile("XFAIL: \n\nValueError.*"))


def test_exception_xfail_reason_test_throws_expect_log_reason(
    pytester: pytest.Pytester, page: Page
) -> None:
    pytester.makepyfile("""
        from pytest_human.fixtures import test_log
        import pytest

        @pytest.mark.xfail(reason="Some reason")
        def test_exception_xfail(test_log):
            test_log.info("Before exception.")
            raise ValueError("This is a test exception.")
            test_log.info("After exception.")
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=info")
    html_path = utils.find_test_log_location(result)
    assert result.ret == ExitCode.OK

    page.goto(html_path.as_uri())
    exception = page.locator("tr.log-level-warning").filter(visible=True)
    expect(exception).to_have_count(1)
    expect(exception.locator("td.level-cell")).to_have_text("WARNING")
    expect(exception.locator("td.source-cell")).to_have_text("test_exception_xfail")
    expect(exception.locator("td.msg-cell")).to_contain_text(
        re.compile("XFAIL: Some reason\n\nValueError.*")
    )
