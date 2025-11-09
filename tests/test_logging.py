import re

import pytest
from playwright.sync_api import Page, expect

from tests import utils


def test_logging_log_levels_trace(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        def test_example(human):
            human.trace("This is a TRACE log message.")
    """)

    result = pytester.runpytest("--enable-html-log", "--log-level=trace")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    log_lines = page.locator("tr.log-level-trace")
    expect(log_lines).to_have_count(1)
    expect(log_lines.locator("td.level-cell")).to_have_text("TRACE")
    expect(log_lines.locator("td.source-cell")).to_have_text("test_example")
    expect(log_lines.locator("td.msg-cell")).to_have_text("This is a TRACE log message.")


def test_logging_log_levels_debug(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        def test_example(human):
            human.debug("This is a DEBUG log message.")
    """)

    result = pytester.runpytest("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    log_lines = page.locator("tr.log-level-debug").filter(visible=True)
    expect(log_lines).to_have_count(1)
    expect(log_lines.locator("td.level-cell")).to_have_text("DEBUG")
    expect(log_lines.locator("td.source-cell")).to_have_text("test_example")
    expect(log_lines.locator("td.msg-cell")).to_have_text("This is a DEBUG log message.")


def test_logging_log_levels_info(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        def test_example(human):
            human.info("This is an INFO log message.")
    """)

    result = pytester.runpytest("--enable-html-log", "--log-level=info")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    log_lines = page.locator("tr.log-level-info").filter(visible=True)
    expect(
        log_lines,
        "There should only be 3 info messages, our log, test setup and test cleanup",
    ).to_have_count(3)
    log_lines = log_lines.nth(1)
    expect(log_lines.locator("td.level-cell")).to_have_text("INFO")
    expect(log_lines.locator("td.source-cell")).to_have_text("test_example")
    expect(log_lines.locator("td.msg-cell")).to_have_text("This is an INFO log message.")


def test_logging_log_levels_warning(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        def test_example(human):
            human.warning("This is a WARNING log message.")
    """)

    result = pytester.runpytest("--enable-html-log")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    log_lines = page.locator("tr.log-level-warning").filter(visible=True)
    expect(log_lines).to_have_count(1)
    expect(log_lines.locator("td.level-cell")).to_have_text("WARNING")
    expect(log_lines.locator("td.source-cell")).to_have_text("test_example")
    expect(log_lines.locator("td.msg-cell")).to_have_text("This is a WARNING log message.")


def test_logging_log_levels_error(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        def test_example(human):
            human.error("This is an ERROR log message.")
    """)

    result = pytester.runpytest("--enable-html-log")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    log_lines = page.locator("tr.log-level-error").filter(visible=True)
    expect(log_lines).to_have_count(1)
    expect(log_lines.locator("td.level-cell")).to_have_text("ERROR")
    expect(log_lines.locator("td.source-cell")).to_have_text("test_example")
    expect(log_lines.locator("td.msg-cell")).to_have_text("This is an ERROR log message.")


def test_logging_log_levels_critical(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        def test_example(human):
            human.critical("This is a CRITICAL log message.")
    """)

    result = pytester.runpytest("--enable-html-log")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    log_lines = page.locator("tr.log-level-critical").filter(visible=True)
    expect(log_lines).to_have_count(1)
    expect(log_lines.locator("td.level-cell")).to_have_text("CRITICAL")
    expect(log_lines.locator("td.source-cell")).to_have_text("test_example")
    expect(log_lines.locator("td.msg-cell")).to_have_text("This is a CRITICAL log message.")


def test_logging_span_simple(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        def test_example(human):
            with human.span_info("Awesome Span"):
                human.info("This is an INFO log message inside a span.")
    """)

    result = pytester.runpytest("--enable-html-log", "--log-level=info")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    span = page.get_by_role("row", name="Awesome Span")
    expect(span).to_be_visible()

    span_content = page.get_by_role("cell", name="This is an INFO log message inside a span.")
    expect(span_content).to_be_hidden()

    expand_button = span.get_by_role("button")
    expect(expand_button).to_have_text("[+]")
    expand_button.click()
    expect(expand_button).to_have_text("[–]")  # noqa: RUF001

    open_block = span.locator("xpath=following-sibling::tr[1]").first
    expect(open_block).to_contain_text("This is an INFO log message inside a span.")


def test_logging_span_error_propagates(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        def test_example(human):
            with human.span_info("Awesome Span"):
                with human.span_info("Nested Span"):
                    human.error("This is an ERROR log message inside a span.")
    """)

    result = pytester.runpytest("--enable-html-log", "--log-level=info")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    span = page.get_by_role("row", name="Awesome Span")
    expect(span).to_have_class("log-level-error")

    expand_button = span.get_by_role("button")
    expand_button.click()

    nested_span = page.locator('tr[id^="header"]').filter(has_text="Nested Span")
    expect(nested_span).to_have_class("log-level-error")

    expand_button = nested_span.get_by_role("button")
    expand_button.click()

    inner_log_block = nested_span.locator("xpath=following-sibling::tr[1]").first
    inner_log = inner_log_block.get_by_role("row").first
    expect(inner_log).to_contain_text("This is an ERROR log message inside a span.")
    expect(inner_log).to_have_class("log-level-error")


def test_logging_span_critical_propagates(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        def test_example(human):
            with human.span_warning("Awesome Span"):
                with human.span_critical("Nested Span"):
                    human.error("This is an ERROR log message inside a span.")
    """)

    result = pytester.runpytest("--enable-html-log", "--log-level=info")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    span = page.get_by_role("row", name="Awesome Span")
    expect(span).to_have_class("log-level-critical")

    expand_button = span.get_by_role("button")
    expand_button.click()

    nested_span = page.locator('tr[id^="header"]').filter(has_text="Nested Span")
    expect(nested_span).to_have_class("log-level-critical")

    expand_button = nested_span.get_by_role("button")
    expand_button.click()

    inner_log_block = nested_span.locator("xpath=following-sibling::tr[1]").first
    inner_log = inner_log_block.get_by_role("row").first
    expect(inner_log).to_contain_text("This is an ERROR log message inside a span.")
    expect(inner_log).to_have_class("log-level-error")


def test_logging_log_fixtures_setup(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        import pytest

        @pytest.fixture
        def foobulator():
            return 3

        @pytest.fixture()
        def sandwich(foobulator):
            return foobulator + 2

        def test_example(sandwich):
            assert True
    """)

    result = pytester.runpytest("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    test_setup = utils.open_span(page, "Test setup")
    sandwich_setup = utils.open_span(test_setup, "setup fixture sandwich(foobulator=3)")
    expect(sandwich_setup.locator("td.msg-cell").last).to_contain_text(
        "setup fixture sandwich() -> 5"
    )

    foobulator_setup = utils.open_span(test_setup, "setup fixture foobulator()")
    expect(foobulator_setup.locator("td.msg-cell").last).to_contain_text(
        "setup fixture foobulator() -> 3"
    )


def test_logging_log_fixtures_teardown(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        import pytest

        @pytest.fixture
        def foobulator():
            return 3

        @pytest.fixture()
        def sandwich(foobulator):
            return foobulator + 2

        def test_example(sandwich):
            assert True
    """)

    result = pytester.runpytest("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    test_teardown = utils.open_span(page, "Test teardown")
    expect(
        test_teardown.locator("td.msg-cell").filter(has_text="Tore down fixture sandwich()")
    ).to_have_count(1)
    expect(
        test_teardown.locator("td.msg-cell").filter(has_text="Tore down fixture foobulator()")
    ).to_have_count(1)


def test_logging_log_method_call(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        from pytest_human.log import log_method_call

        @log_method_call()
        def a(x):
            return b(x+1)

        @log_method_call()
        def b(x):
            return x + 1

        def test_example(human):
            a(1)
    """)

    result = pytester.runpytest("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    a_call = utils.open_span(page, "a(x=1)")
    b_call = utils.open_span(a_call, "b(x=2)")
    expect(b_call.locator("td.msg-cell").last).to_contain_text("b(x=2) -> 3")
    expect(a_call.locator("td.msg-cell").last).to_contain_text("a(x=1) -> 3")


def test_logging_patch_method_logger(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        from pytest_human.log import patch_method_logger
        import os

        def test_example(human):
            a = [1, 2, 3]
            os.path.join("path", "one")

            with patch_method_logger(os.path.join):
                os.path.join("path", "two")

            os.path.join("path", "three")
    """)

    result = pytester.runpytest("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    path_call = utils.open_span(page, "posixpath.join(")
    expect(path_call.locator("td.msg-cell").last).to_contain_text(
        re.compile(r"posixpath.join\(.*-> 'path/two'")
    )


def test_logging_patch_all_public_methods_module(pytester: pytest.Pytester, page: Page) -> None:
    """
    Adds logging to all public methods in a module
    """
    pytester.makepyfile("""
        from pytest_human.log import patch_all_public_methods
        import math

        def test_example(human):
            math.sqrt(9)
            with patch_all_public_methods(math):
                math.sqrt(16)
                math.factorial(5)
            math.factorial(4)
            math.sqrt(25)
    """)

    result = pytester.runpytest("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    sqrt_call = utils.open_span(page, "math.sqrt(")
    expect(sqrt_call.locator("td.msg-cell").last).to_contain_text("math.sqrt(x=16) -> 4.0")

    factorial_call = utils.open_span(page, "math.factorial(")
    expect(factorial_call.locator("td.msg-cell").last).to_contain_text("math.factorial(x=5) -> 120")


def test_logging_patch_all_public_methods_class(pytester: pytest.Pytester, page: Page) -> None:
    """
    Adds logging to all public methods in a class
    """
    pytester.makepyfile("""
        from pytest_human.log import patch_all_public_methods

        class TestClass:
            def fobulator(self, x):
                return x + 1

            def sandwich(self, y):
                return y * 2

        def test_example(human):
            x = TestClass()
            x.fobulator(3)
            with patch_all_public_methods(TestClass):
                x.fobulator(4)
                x.sandwich(5)
            x.sandwich(6)
    """)

    result = pytester.runpytest("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    sqrt_call = utils.open_span(page, "TestClass.fobulator(")
    expect(sqrt_call.locator("td.msg-cell").last).to_contain_text("TestClass.fobulator(x=4) -> 5")

    factorial_call = utils.open_span(page, "TestClass.sandwich(")
    expect(factorial_call.locator("td.msg-cell").last).to_contain_text(
        "TestClass.sandwich(y=5) -> 10"
    )
