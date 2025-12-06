import re
from pathlib import Path

from _pytest.pytester import RunResult
from playwright.sync_api import Locator, Page, expect

from pytest_human.tracing import traced


@traced
def find_test_log_location(result: RunResult) -> Path:
    """Find the test log location from the pytest output."""
    for line in result.outlines:
        matches = re.match(r". Test (?P<test_name>.*) HTML log at (?P<log_path>file://.+)", line)

        if matches is None:
            continue

        log_path = matches.group("log_path")
        assert log_path is not None, f"Expected log_path group to match. {line=}"
        return Path(log_path.removeprefix("file://"))

    raise ValueError("Could not find test log location in pytest output.")


@traced
def open_span(page: Page | Locator, span_text: str | re.Pattern) -> Locator:
    nested_span = page.locator('tr[id^="header"]').filter(has_text=span_text)

    expand_button = nested_span.locator("td.toggle-cell").get_by_role("button")
    if expand_button.inner_text() == "[+]":
        expand_button.click()

    inner_log_block = nested_span.locator("xpath=following-sibling::tr[1]")
    return inner_log_block


@traced
def assert_unopenable_span(page: Page | Locator, span_text: str | re.Pattern) -> None:
    nested_span = page.locator('tr[id^="header"]').filter(has_text=span_text)

    expand_button = nested_span.locator("td.toggle-cell").get_by_role("button")
    expect(expand_button).to_be_hidden()
