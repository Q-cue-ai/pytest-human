import git
import pytest
from playwright.sync_api import Page, expect

from tests import utils


def test_source_no_git(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        def test_example(human):
            human.log.debug("This is a DEBUG log message.")
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    log_lines = page.locator("tr.log-level-debug").filter(visible=True)
    expect(log_lines).to_have_count(1)
    log_lines = log_lines.first

    expect(log_lines.locator("td.level-cell")).to_have_text("DEBUG")
    expect(log_lines.locator("td.source-cell")).to_have_text("test_source_no_git.py:2")
    expect(log_lines.locator("td.source-cell .source-text")).to_have_attribute(
        "title", "test_source_no_git.py:2"
    )
    expect(log_lines.locator("td.msg-cell")).to_have_text("This is a DEBUG log message.")


def test_source_span_no_git(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
        def test_example(human):
            with human.span.debug("This is a DEBUG log message."):
                pass
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    log_lines = page.locator("tr.log-level-debug").filter(visible=True)
    expect(log_lines).to_have_count(1)
    log_lines = log_lines.first

    expect(log_lines.locator("td.level-cell")).to_have_text("DEBUG")
    expect(log_lines.locator("td.source-cell")).to_have_text("test_source_span_no_git.py:2")
    expect(log_lines.locator("td.source-cell .source-text")).to_have_attribute(
        "title", "test_source_span_no_git.py:2"
    )
    expect(log_lines.locator("td.msg-cell")).to_have_text("This is a DEBUG log message.")


def test_source_traced_no_git(pytester: pytest.Pytester, page: Page) -> None:
    pytester.makepyfile("""
            from pytest_human.log import traced
            from logging import DEBUG

            @traced(log_level=DEBUG)
            def traced_function():
                return

            def test_example(human):
                traced_function()
    """)

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    log_lines = page.locator("tr.log-level-debug").filter(visible=True)
    expect(log_lines.first.locator("td.msg-cell")).to_contain_text("traced_function()")
    expect(log_lines.first.locator("td.source-cell")).to_have_text("test_source_traced_no_git.py:9")

    opened = utils.open_span(page, "traced_function()")
    expect(opened.locator("td.msg-cell").last).to_contain_text("traced_function() -> None")
    expect(opened.locator("td.source-cell").last).to_have_text("test_source_traced_no_git.py:9")


def test_source_git_repo(pytester: pytest.Pytester, page: Page) -> None:
    repo = git.Repo.init(pytester.path)
    repo.create_remote("origin", "git@github.com:repo/test.git")

    pytester.makepyfile("""
        def test_example(human):
            human.log.debug("This is a DEBUG log message.")
    """)

    repo.index.add(pytester.path / "test_source_git_repo.py")
    repo.index.commit("First commit")

    result = pytester.runpytest_subprocess("--enable-html-log", "--log-level=debug")
    html_path = utils.find_test_log_location(result)
    assert result.ret == 0

    page.goto(html_path.as_uri())
    log_lines = page.locator("tr.log-level-debug").filter(visible=True)
    expect(log_lines).to_have_count(1)

    link = page.get_by_role("link", name="test_source_git_repo.py:2")
    expect(link).to_have_attribute(
        "href", "https://github.com/repo/test/blob/master/test_source_git_repo.py#L2"
    )
