from pathlib import Path

import pytest
from _pytest.config import ExitCode
from playwright.sync_api import Page, expect

from tests import utils


def test_artifacts_empty(pytester: pytest.Pytester, page: Page) -> None:
    """Test that artifacts show no attachments when none were added."""

    pytester.makepyfile("""
        def test_no_artifacts():
            pass
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=DEBUG")
    html_path = utils.find_test_log_location(result)
    assert result.ret == ExitCode.OK

    page.goto(html_path.as_uri())
    utils.assert_unopenable_span(page, "Test artifacts")


def test_artifacts_stdout(pytester: pytest.Pytester, page: Page) -> None:
    """Test that artifacts show captured stdout."""

    pytester.makepyfile("""
        def test_stdout():
            print("This is a test stdout message.")
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=DEBUG")
    html_path = utils.find_test_log_location(result)
    assert result.ret == ExitCode.OK

    page.goto(html_path.as_uri())
    test_artifacts = utils.open_span(page, "Test artifacts")
    stdout = utils.open_span(test_artifacts, "Captured stdout call")
    log_cell = stdout.locator("td.msg-cell").last
    expect(log_cell).to_have_text("This is a test stdout message.")


def test_artifacts_stderr(pytester: pytest.Pytester, page: Page) -> None:
    """Test that artifacts show captured stderr."""

    pytester.makepyfile("""
        import sys

        def test_stderr():
            print("This is a test stderr message.", file=sys.stderr)
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=DEBUG")
    html_path = utils.find_test_log_location(result)
    assert result.ret == ExitCode.OK

    page.goto(html_path.as_uri())
    test_artifacts = utils.open_span(page, "Test artifacts")
    stdout = utils.open_span(test_artifacts, "Captured stderr call")
    log_cell = stdout.locator("td.msg-cell").last
    expect(log_cell).to_have_text("This is a test stderr message.")


def test_artifacts_log_text(pytester: pytest.Pytester, page: Page, tmp_path: Path) -> None:
    """Test that artifacts show attached log text."""

    pytester.makepyfile("""
        def test_log_file(human):
            log_content = '''This is a sample log file.'''
            human.artifacts.add_log_text(log_content, "sample.log", description="Sample log file")
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=DEBUG")
    html_path = utils.find_test_log_location(result)
    assert result.ret == ExitCode.OK

    page.goto(html_path.as_uri())
    test_artifacts = utils.open_span(page, "Test artifacts")
    log_attachment = utils.open_span(test_artifacts, "sample.log")

    description_cell = log_attachment.locator("td.msg-cell").first
    expect(description_cell).to_have_text("# Sample log file")

    log_cell = log_attachment.locator("td.msg-cell").last
    expect(log_cell).to_have_text("This is a sample log file.")


def test_artifacts_log_file(pytester: pytest.Pytester, page: Page, tmp_path: Path) -> None:
    """Test that artifacts show attached log file."""

    log_file = tmp_path / "some.log"
    log_file.write_text("This is some text file i have around.")

    pytester.makepyfile(f"""
        def test_log_file(human):
            log_content = '''This is a sample log file.'''
            human.artifacts.add_log_file('{log_file}', description="Sample log file")
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=DEBUG")
    html_path = utils.find_test_log_location(result)
    assert result.ret == ExitCode.OK

    page.goto(html_path.as_uri())
    test_artifacts = utils.open_span(page, "Test artifacts")
    log_attachment = utils.open_span(test_artifacts, "some.log")

    description_cell = log_attachment.locator("td.msg-cell").first
    expect(description_cell).to_have_text("# Sample log file")

    log_cell = log_attachment.locator("td.msg-cell").last
    expect(log_cell).to_have_text("This is some text file i have around.")
