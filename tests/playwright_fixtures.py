import logging
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("playwright", "Playwright options")
    group.addoption(
        "--browser",
        action="append",
        default=[],
        help="Browser engine to run tests with (chromium, firefox, webkit). Default: chromium",
    )
    group.addoption(
        "--tracing",
        default="off",
        choices=["on", "off", "retain-on-failure"],
        help="Tracing mode",
    )
    group.addoption(
        "--screenshot",
        default="off",
        choices=["on", "off", "only-on-failure"],
        help="Screenshot mode",
    )
    group.addoption(
        "--video",
        default="off",
        choices=["on", "off", "retain-on-failure"],
        help="Video mode",
    )
    group.addoption("--output", default="test-results", help="Output directory for artifacts")


@pytest.fixture(scope="session")
def playwright_instance() -> Iterator[Playwright]:
    with sync_playwright() as playwright:
        yield playwright


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "browser_name" in metafunc.fixturenames:
        browsers = metafunc.config.getoption("--browser")
        if not browsers:
            browsers = ["chromium"]
        metafunc.parametrize("browser_name", browsers, scope="session")


@pytest.fixture(scope="session")
def browser(playwright_instance: Playwright, browser_name: str) -> Iterator[Browser]:
    browser_type = getattr(playwright_instance, browser_name)
    browser = browser_type.launch()
    yield browser
    browser.close()


def _slugify(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-\.]", "_", text)


def _has_failed(request: pytest.FixtureRequest) -> bool:
    return bool(getattr(request.node, "rep_call", None) and request.node.rep_call.failed)


def _handle_tracing(
    context: BrowserContext,
    output_dir: Path,
    slug: str,
    tracing_option: str,
    failed: bool,
) -> None:
    if tracing_option == "on" or (tracing_option == "retain-on-failure" and failed):
        trace_path = output_dir / f"{slug}-trace.zip"
        context.tracing.stop(path=str(trace_path))
        return

    context.tracing.stop()


def _handle_screenshot(
    page: Page,
    output_dir: Path,
    slug: str,
    screenshot_option: str,
    failed: bool,
) -> None:
    if screenshot_option == "on" or (screenshot_option == "only-on-failure" and failed):
        path = output_dir / f"{slug}-screenshot.png"
        page.screenshot(path=str(path))


def _handle_video(
    page: Page,
    output_dir: Path,
    slug: str,
    video_option: str,
    failed: bool,
) -> None:
    if video_option not in ["on", "retain-on-failure"]:
        return

    video = page.video
    if not video:
        return

    video_path = None
    try:
        if not page.is_closed():
            page.close()
        video_path = Path(video.path())
    except Exception as exc:
        logging.debug(f"Could not get video path: {exc}")

    if not video_path or not video_path.exists():
        return

    if video_option == "retain-on-failure" and not failed:
        video_path.unlink()
        return

    new_path = output_dir / f"{slug}.webm"
    if new_path.exists():
        logging.debug(f"Video path already exists, overwriting: {new_path}")
        new_path.unlink()
    video_path.rename(new_path)


@pytest.fixture
def context(
    browser: Browser, request: pytest.FixtureRequest, pytestconfig: pytest.Config
) -> Iterator[BrowserContext]:
    video_option = pytestconfig.getoption("--video")
    tracing_option = pytestconfig.getoption("--tracing")
    output_dir = Path(pytestconfig.getoption("--output")).absolute()

    output_dir.mkdir(parents=True, exist_ok=True)

    context_args = {}
    if video_option in ["on", "retain-on-failure"]:
        context_args["record_video_dir"] = output_dir

    context = browser.new_context(**context_args)

    if tracing_option in ["on", "retain-on-failure"]:
        context.tracing.start(screenshots=True, snapshots=True, sources=True)

    yield context

    failed = _has_failed(request)
    slug = _slugify(request.node.nodeid)

    _handle_tracing(context, output_dir, slug, tracing_option, failed)
    context.close()


@pytest.fixture
def page(
    context: BrowserContext, request: pytest.FixtureRequest, pytestconfig: pytest.Config
) -> Iterator[Page]:
    page_obj = context.new_page()
    yield page_obj

    failed = _has_failed(request)
    slug = _slugify(request.node.nodeid)
    output_dir = Path(pytestconfig.getoption("--output")).absolute()

    _handle_screenshot(page_obj, output_dir, slug, pytestconfig.getoption("--screenshot"), failed)
    _handle_video(page_obj, output_dir, slug, pytestconfig.getoption("--video"), failed)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Iterator[None]:
    # https://stackoverflow.com/a/72629285
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)
