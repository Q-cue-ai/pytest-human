import re

import pytest
from playwright.sync_api import Page, expect

from tests import utils


def test_tracing_log_fixtures_setup(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        import pytest

        @pytest.fixture
        def foobulator():
            return 3

        @pytest.fixture()
        def sandwich(foobulator):
            return foobulator + 2

        @pytest.fixture(scope="session", autouse=True)
        def autouse_fixture():
            pass

        def test_example(sandwich):
            assert True
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    test_setup = utils.open_span(page, "Test setup")
    sandwich_setup = utils.open_span(test_setup, "setup fixture function sandwich(foobulator=3)")
    expect(sandwich_setup.locator("td.msg-cell").last).to_contain_text(
        "setup fixture sandwich() -> 5"
    )

    foobulator_setup = utils.open_span(test_setup, "setup fixture function foobulator()")
    expect(foobulator_setup.locator("td.msg-cell").last).to_contain_text(
        "setup fixture foobulator() -> 3"
    )

    autouse_setup = utils.open_span(test_setup, "setup fixture session autouse autouse_fixture()")
    expect(autouse_setup.locator("td.msg-cell").last).to_contain_text(
        "setup fixture autouse_fixture() -> None"
    )


def test_tracing_log_fixtures_setup_async(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        import pytest
        import pytest_asyncio

        @pytest_asyncio.fixture
        async def foobulator():
            return 3

        @pytest_asyncio.fixture
        async def sandwich(foobulator):
            return foobulator + 2

        @pytest.mark.asyncio
        async def test_example(sandwich):
            assert True
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    test_setup = utils.open_span(page, "Test setup")
    sandwich_setup = utils.open_span(
        test_setup, "setup fixture async function sandwich(foobulator=3)"
    )
    expect(sandwich_setup.locator("td.msg-cell").last).to_contain_text(
        "setup fixture sandwich() -> "
    )

    foobulator_setup = utils.open_span(test_setup, "setup fixture async function foobulator()")
    expect(foobulator_setup.locator("td.msg-cell").last).to_contain_text(
        "setup fixture foobulator() -> "
    )


def test_tracing_log_fixtures_setup_scopes(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        import pytest

        @pytest.fixture(autouse=True)
        def autouse_fixture():
            pass

        @pytest.fixture(scope="module")
        def module_fixture():
            pass

        @pytest.fixture(scope="session")
        def session_fixture():
            pass

        def test_example(session_fixture, module_fixture):
            assert True
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    test_setup = utils.open_span(page, "Test setup")
    autouse_setup = utils.open_span(test_setup, "setup fixture function autouse autouse_fixture()")
    expect(autouse_setup.locator("td.msg-cell").last).to_contain_text(
        "setup fixture autouse_fixture() -> None"
    )

    module_setup = utils.open_span(test_setup, "setup fixture module module_fixture()")
    expect(module_setup.locator("td.msg-cell").last).to_contain_text(
        "setup fixture module_fixture() -> None"
    )

    session_setup = utils.open_span(test_setup, "setup fixture session session_fixture()")
    expect(session_setup.locator("td.msg-cell").last).to_contain_text(
        "setup fixture session_fixture() -> None"
    )


def test_tracing_log_fixtures_teardown(pytester: pytest.Pytester, page: Page) -> None:
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

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    test_teardown = utils.open_span(page, "Test teardown")
    expect(
        test_teardown.locator("td.msg-cell").filter(has_text="Clean fixture function sandwich()")
    ).to_have_count(1)
    expect(
        test_teardown.locator("td.msg-cell").filter(has_text="Clean fixture function foobulator()")
    ).to_have_count(1)


def test_tracing_log_fixtures_teardown_async(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        import pytest
        import pytest_asyncio

        @pytest_asyncio.fixture
        async def foobulator():
            return 3

        @pytest_asyncio.fixture
        async def sandwich(foobulator):
            return foobulator + 2

        @pytest.mark.asyncio
        async def test_example(sandwich):
            assert True
    """)

    result = pytester.runpytest_subprocess(
        "--enable-html-log",
        "--log-level=debug",
    )
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    test_teardown = utils.open_span(page, "Test teardown")
    expect(
        test_teardown.locator("td.msg-cell").filter(
            has_text="Clean fixture async function sandwich()"
        )
    ).to_have_count(1)
    expect(
        test_teardown.locator("td.msg-cell").filter(
            has_text="Clean fixture async function foobulator()"
        )
    ).to_have_count(1)


def test_tracing_log_fixtures_teardown_scopes(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        import pytest

        @pytest.fixture(autouse=True)
        def autouse_fixture():
            pass

        @pytest.fixture(scope="module")
        def module_fixture():
            pass

        @pytest.fixture(scope="session")
        def session_fixture():
            pass

        def test_example(session_fixture, module_fixture):
            assert True
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    test_teardown = utils.open_span(page, "Test teardown")
    expect(
        test_teardown.locator("td.msg-cell").filter(
            has_text="Clean fixture function autouse autouse_fixture()"
        )
    ).to_have_count(1)
    expect(
        test_teardown.locator("td.msg-cell").filter(
            has_text="Clean fixture module module_fixture()"
        )
    ).to_have_count(1)
    expect(
        test_teardown.locator("td.msg-cell").filter(
            has_text="Clean fixture session session_fixture()"
        )
    ).to_have_count(1)


def test_tracing_traced(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        from pytest_human.tracing import traced

        @traced()
        def a(x):
            return b(x+1)

        @traced()
        def b(x):
            return x + 1

        def test_example(human):
            a(1)
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    a_call = utils.open_span(page, "a(x=1)")
    b_call = utils.open_span(a_call, "b(x=2)")
    expect(b_call.locator("td.msg-cell").last).to_contain_text("b(x=2) -> 3")
    expect(a_call.locator("td.msg-cell").last).to_contain_text("a(x=1) -> 3")


def test_tracing_traced_no_params(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        from pytest_human.tracing import traced

        @traced
        def a(x):
            return b(x+1)

        @traced
        def b(x):
            return x + 1

        def test_example(human):
            a(1)
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    a_call = utils.open_span(page, "a(x=1)")
    b_call = utils.open_span(a_call, "b(x=2)")
    expect(b_call.locator("td.msg-cell").last).to_contain_text("b(x=2) -> 3")
    expect(a_call.locator("td.msg-cell").last).to_contain_text("a(x=1) -> 3")


def test_tracing_traced_async(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        from pytest_human.tracing import traced
        import pytest

        @traced
        async def a(x):
            return x + 1

        @pytest.mark.asyncio
        async def test_example(human):
            await a(1)
    """)

    result = pytester.runpytest_subprocess(
        "--enable-html-log",
        "--log-level=debug",
    )
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    a_call = utils.open_span(page, "a(x=1)")
    expect(a_call.locator("td.msg-cell").last).to_contain_text("a(x=1) -> 2")


def test_tracing_traced_suppress_return(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        from pytest_human.tracing import traced

        @traced(suppress_return=True)
        def a(x):
            return x+1

        def test_example(human):
            a(1)
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    a_call = utils.open_span(page, "a(x=1)")
    expect(a_call.locator("td.msg-cell").last).to_contain_text("a(x=1) -> <suppressed>")


def test_tracing_traced_suppress_params(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        from pytest_human.tracing import traced

        @traced(suppress_params=True)
        def a(x, y):
            return x+1

        def test_example(human):
            a(1, y=2)
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    a_call = utils.open_span(page, "a()")
    expect(a_call.locator("td.msg-cell").last).to_contain_text("a() -> 2")


def test_tracing_traced_log_level(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        from pytest_human.tracing import traced
        import logging

        @traced(log_level=logging.TRACE)
        def a(x, y):
            return x+1

        def test_example(human):
            a(1, y=2)
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=trace")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())

    log_lines = page.locator("tr.log-level-trace").filter(visible=True)
    expect(log_lines).to_have_count(1)
    log_lines = log_lines.first
    expect(log_lines.locator("td.level-cell")).to_have_text("TRACE")
    expect(log_lines.locator("td.msg-cell")).to_contain_text("a(x=1, y=2)")


def test_tracing_trace_calls(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        from pytest_human.tracing import trace_calls
        import os
        import base64

        def test_example(human):
            os.path.join("path", "one")

            with trace_calls(os.path.join, base64.b64encode):
                os.path.join("path", "two")
                base64.b64encode(b"three")

            base64.b64encode(b"three")
            os.path.join("path", "three")
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    path_call = utils.open_span(page, "posixpath.join(")
    expect(path_call.locator("td.msg-cell").last).to_contain_text(
        re.compile(r"posixpath.join\(.*-> 'path/two'")
    )

    base_call = utils.open_span(page, "base64.b64encode(")
    expect(base_call.locator("td.msg-cell").last).to_contain_text(
        re.compile(r"base64.b64encode\(.*-> b'dGhyZWU='")
    )


def test_tracing_trace_calls_infinite_recursion(pytester: pytest.Pytester, page: Page) -> None:
    """
    The logging system itself calls os.path.basename, so this test make sure
    we don't get into an infinite recursion.
    """
    pytester.makepyfile("""
        from pytest_human.tracing import trace_calls
        import os

        def test_example(human):
            with trace_calls(os.path.basename):
                os.path.basename("path/two")
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    base_call = utils.open_span(page, "posixpath.basename(")
    expect(base_call.locator("td.msg-cell").last).to_contain_text(
        re.compile(r"posixpath.basename\(.*-> 'two'")
    )


def test_tracing_trace_public_api_module(pytester: pytest.Pytester, page: Page) -> None:
    """
    Adds logging to all public methods in a module
    """
    pytester.makepyfile("""
        from pytest_human.tracing import trace_public_api
        import math

        def test_example(human):
            math.sqrt(9)
            with trace_public_api(math):
                math.sqrt(16)
                math.factorial(5)
            math.factorial(4)
            math.sqrt(25)
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    sqrt_call = utils.open_span(page, "math.sqrt(")
    expect(sqrt_call.locator("td.msg-cell").last).to_contain_text("math.sqrt(x=16) -> 4.0")

    factorial_call = utils.open_span(page, "math.factorial(")
    # factorial either uses `n` or `x` as parameter name.
    expect(factorial_call.locator("td.msg-cell").last).to_contain_text(
        re.compile(r"math\.factorial\(\w+=5\) -> 120")
    )


def test_tracing_trace_public_api_class(pytester: pytest.Pytester, page: Page) -> None:
    """
    Adds logging to all public methods in a class
    """
    pytester.makepyfile("""
        from pytest_human.tracing import trace_public_api

        class TestClass:
            def fobulator(self, x):
                return x + 1

            def sandwich(self, y):
                return y * 2

        def test_example(human):
            x = TestClass()
            x.fobulator(3)
            with trace_public_api(TestClass):
                x.fobulator(4)
                x.sandwich(5)
            x.sandwich(6)
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    sqrt_call = utils.open_span(page, "TestClass.fobulator(")
    expect(sqrt_call.locator("td.msg-cell").last).to_contain_text("TestClass.fobulator(x=4) -> 5")

    sandwich_call = utils.open_span(page, "TestClass.sandwich(")
    expect(sandwich_call.locator("td.msg-cell").last).to_contain_text(
        "TestClass.sandwich(y=5) -> 10"
    )
