import re

import pytest
from _pytest.config import ExitCode
from playwright.sync_api import Page, expect

from tests import utils


def test_search_simple_keyboard(pytester: pytest.Pytester, page: Page) -> None:
    """Test searching for text using the keyboard shortcut to focus the search box."""

    pytester.makepyfile("""
        def test_example(human):
            human.log.info("funkadelic.")
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=info")
    html_path = utils.find_test_log_location(result)
    assert result.ret == ExitCode.OK

    page.goto(html_path.as_uri())
    page.locator("body").press("/")

    search_box = page.locator("#search-input")
    expect(search_box).to_be_focused()
    search_box.fill("funkadelic")
    search_box.press("Enter")

    expect(page.locator("#search-counter")).to_have_text("1 / 1")
    active_match = page.locator(".active")
    expect(active_match).to_have_text("funkadelic")


def test_search_simple(pytester: pytest.Pytester, page: Page) -> None:
    """Test searching for text."""

    pytester.makepyfile("""
        def test_example(human):
            human.log.info("searching for this quintessential text")
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=info")
    html_path = utils.find_test_log_location(result)
    assert result.ret == ExitCode.OK

    page.goto(html_path.as_uri())

    search_box = page.locator("#search-input")
    search_box.click()
    expect(search_box).to_be_focused()

    search_box.fill("quintessential")
    search_box.press("Enter")

    expect(page.locator("#search-counter")).to_have_text("1 / 1")
    active_match = page.locator(".active")
    expect(active_match).to_have_text("quintessential")


def test_search_multiple_results_keyboard(pytester: pytest.Pytester, page: Page) -> None:
    """Test navigating forward and backward through multiple search results with keyboard."""

    pytester.makepyfile("""
        def test_example(human):
            human.log.info("first test occurrence")
            human.log.info("second test occurrence")
            human.log.info("third test occurrence")
            human.log.info("fourth test occurrence")
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=info")
    html_path = utils.find_test_log_location(result)
    assert result.ret == ExitCode.OK

    page.goto(html_path.as_uri())
    page.locator("body").press("/")

    search_box = page.locator("#search-input")
    search_box.fill("occurrence")

    active_class = re.compile("active")

    expect(page.locator("#search-counter")).to_have_text("1 / 4")
    expect(page.locator(".highlight").nth(0)).to_have_class(active_class)

    search_box.press("Enter")
    expect(page.locator("#search-counter")).to_have_text("2 / 4")
    expect(page.locator(".highlight").nth(1)).to_have_class(active_class)

    page.locator("body").press("Shift+Enter")
    expect(page.locator("#search-counter")).to_have_text("1 / 4")
    expect(page.locator(".highlight").nth(0)).to_have_class(active_class)

    expect(page.locator(".highlight")).to_have_count(4)
    expect(page.locator(".highlight")).to_have_text(
        ["occurrence", "occurrence", "occurrence", "occurrence"]
    )


def test_search_multiple_results(pytester: pytest.Pytester, page: Page) -> None:
    """Test navigating forward and backward through multiple search results."""

    pytester.makepyfile("""
        def test_example(human):
            human.log.info("first test occurrence")
            human.log.info("second test occurrence")
            human.log.info("third test occurrence")
            human.log.info("fourth test occurrence")
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=info")
    html_path = utils.find_test_log_location(result)
    assert result.ret == ExitCode.OK

    page.goto(html_path.as_uri())

    search_box = page.locator("#search-input")
    search_box.click()
    expect(search_box).to_be_focused()
    search_box.fill("occurrence")

    active_class = re.compile("active")

    prev_button = page.locator("#search-prev")
    next_button = page.locator("#search-next")

    expect(page.locator("#search-counter")).to_have_text("1 / 4")
    expect(page.locator(".highlight").nth(0)).to_have_class(active_class)

    next_button.click()
    expect(page.locator("#search-counter")).to_have_text("2 / 4")
    expect(page.locator(".highlight").nth(1)).to_have_class(active_class)

    prev_button.click()
    expect(page.locator("#search-counter")).to_have_text("1 / 4")
    expect(page.locator(".highlight").nth(0)).to_have_class(active_class)

    expect(page.locator(".highlight")).to_have_count(4)
    expect(page.locator(".highlight")).to_have_text(
        ["occurrence", "occurrence", "occurrence", "occurrence"]
    )


def test_search_wrap_around(pytester: pytest.Pytester, page: Page) -> None:
    """Test wrap around while navigating forward and backward through multiple search results."""

    pytester.makepyfile("""
        def test_example(human):
            human.log.info("first test occurrence")
            human.log.info("second test occurrence")
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=info")
    html_path = utils.find_test_log_location(result)
    assert result.ret == ExitCode.OK

    page.goto(html_path.as_uri())

    search_box = page.locator("#search-input")
    search_box.click()
    expect(search_box).to_be_focused()
    search_box.fill("occurrence")

    active_class = re.compile("active")

    prev_button = page.locator("#search-prev")
    next_button = page.locator("#search-next")

    expect(page.locator("#search-counter")).to_have_text("1 / 2")
    expect(page.locator(".highlight").nth(0)).to_have_class(active_class)

    next_button.click()
    expect(page.locator("#search-counter")).to_have_text("2 / 2")
    expect(page.locator(".highlight").nth(1)).to_have_class(active_class)

    next_button.click()
    expect(page.locator("#search-counter")).to_have_text("1 / 2")
    expect(page.locator(".highlight").nth(0)).to_have_class(active_class)

    prev_button.click()
    expect(page.locator("#search-counter")).to_have_text("2 / 2")
    expect(page.locator(".highlight").nth(1)).to_have_class(active_class)


def test_search_within_spans_expands(pytester: pytest.Pytester, page: Page) -> None:
    """Test searching for text with hidden spans expands the spans to show results."""

    pytester.makepyfile("""
        def test_example(human):
            with human.log.span.info("Styled Text Span"):
                human.log.info("quintessential")
                with human.log.span.info("Nested Span"):
                    human.log.info("expeditious")
    """)

    result = pytester.runpytest_subprocess(
        "--enable-html-log", "--log-level=info", "--html-log-level=info"
    )
    html_path = utils.find_test_log_location(result)
    assert result.ret == ExitCode.OK

    page.goto(html_path.as_uri())
    expect(page.get_by_role("row", name="expeditious")).to_be_hidden()

    page.locator("body").press("/")

    search_box = page.locator("#search-input")
    search_box.fill("expeditious")

    expect(page.locator("#search-counter")).to_have_text("1 / 1")
    nested_span = page.get_by_role("row", name="Nested Span").first
    expect(nested_span).to_be_visible()
    expect(nested_span.get_by_role("row", name="expeditious").first).to_be_visible()
