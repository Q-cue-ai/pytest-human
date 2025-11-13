"""Pytest plugin to create HTML log files for each test."""

from __future__ import annotations

import inspect
import logging
import re
import warnings
from collections.abc import Iterator
from contextlib import suppress
from pathlib import Path
from typing import Optional, cast

import pytest
from _pytest.nodes import Node
from rich.pretty import pretty_repr

from pytest_human._flags import is_output_to_test_tmp
from pytest_human.exceptions import HumanLogLevelWarning
from pytest_human.html_report import HtmlFileHandler
from pytest_human.human import Human
from pytest_human.log import TestLogger, _SpanEndFilter, get_logger


class HtmlLogPlugin:
    """Pytest plugin to create HTML log files for each test."""

    HTML_LOG_PLUGIN_NAME = "html-log-plugin"
    log_path_key = pytest.StashKey[Path]()
    html_log_handler_key = pytest.StashKey[HtmlFileHandler]()
    human_logger_key = pytest.StashKey[Human]()

    def __init__(self) -> None:
        self.test_tmp_path = None
        self._warned_about_log_level = False

    @classmethod
    def register(cls, config: pytest.Config) -> HtmlLogPlugin:
        """Register the HTML log plugin in pytest plugin manager."""
        html_logger_plugin = HtmlLogPlugin()
        config.pluginmanager.register(html_logger_plugin, HtmlLogPlugin.HTML_LOG_PLUGIN_NAME)
        return html_logger_plugin

    @classmethod
    def unregister(cls, config: pytest.Config) -> None:
        """Unregister the HTML log plugin from pytest plugin manager."""
        html_logger_plugin = config.pluginmanager.get_plugin(HtmlLogPlugin.HTML_LOG_PLUGIN_NAME)
        if html_logger_plugin:
            config.pluginmanager.unregister(html_logger_plugin)

    @staticmethod
    def _get_test_logger(item: pytest.Item) -> TestLogger:
        return get_logger(item.name)

    @staticmethod
    def _get_session_scoped_logs_dir(item: pytest.Item) -> Path:
        """Get the session-scoped logs directory."""
        path = item.session.config._tmp_path_factory.getbasetemp() / "session_logs"  # type: ignore # noqa: SLF001
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def _session_scoped_test_log_path(cls, item: pytest.Item) -> Path:
        """Get the session-scoped test log path."""
        logs_dir = cls._get_session_scoped_logs_dir(item)
        return cls._get_test_log_path(item, logs_dir)

    @staticmethod
    def _get_test_log_path(item: pytest.Item, logs_dir: Path) -> Path:
        """Create a test log path inside the given logs directory."""
        logs_dir = logs_dir.resolve()
        safe_test_name = re.sub(r"[^\w]", "_", item.name)[:35]
        return logs_dir / f"{safe_test_name}.html"

    def _get_test_doc_string(self, item: pytest.Item) -> str | None:
        """Get the docstring of the test function, if any."""
        if test := getattr(item, "obj", None):
            return inspect.getdoc(test)

        if not item.parent:
            return ""

        # class/module level docstring
        if module := getattr(item.parent, "obj", None):
            return inspect.getdoc(module)

        return ""

    def _get_log_level(self, item: pytest.Item) -> int:
        """Get the log level for the test item."""
        log_level_name = "DEBUG"

        with suppress(ValueError):
            if ini_level := item.config.getini("log_level"):
                log_level_name = ini_level

        if cli_level := item.config.getoption("log_level"):
            log_level_name = cli_level

        if html_level := item.config.getoption("html_log_level"):
            log_level_name = html_level

        return logging.getLevelName(log_level_name.upper())

    @classmethod
    def _write_html_log_path(cls, item: pytest.Item, log_path: Path, flush: bool = False) -> None:
        """Log the HTML log path to the terminal."""

        if item.config.getoption("quiet", item.config.getoption("html_quiet")):
            return

        terminal: pytest.TerminalReporter | None = item.config.pluginmanager.get_plugin(
            "terminalreporter"
        )
        if terminal is None:
            return

        terminal.ensure_newline()
        terminal.write("🌎 Test ")
        terminal.write(f"{item.name}", bold=True)
        terminal.write(" HTML log at ")
        terminal.write(f"{log_path.resolve().as_uri()}", bold=True, cyan=True)
        terminal.line("")

        if flush:
            terminal.flush()

    @pytest.hookimpl(tryfirst=True, hookwrapper=True)
    def pytest_runtest_protocol(
        self, item: pytest.Item, nextitem: Optional[pytest.Item]
    ) -> Iterator[None]:
        """Set up HTML log handler for the test and clean up afterwards."""
        root_logger = logging.getLogger()
        log_path = self._get_log_path(item)

        item.stash[self.log_path_key] = log_path

        level = self._get_log_level(item)

        html_handler = HtmlFileHandler(
            log_path.as_posix(),
            title=item.name,
            description=self._get_test_doc_string(item),
        )
        item.stash[self.html_log_handler_key] = html_handler
        html_handler.setLevel(level)
        root_logger.addHandler(html_handler)

        if not self._warned_about_log_level and root_logger.level > level:
            warnings.warn(
                f"The root logger level {logging.getLevelName(root_logger.level)} is higher than "
                f"the HTML log level {logging.getLevelName(level)}."
                " This means logs will be missing from the HTML log."
                "\nConsider setting the root logger level lower using the --log-level option.",
                HumanLogLevelWarning,
            )
            self._warned_about_log_level = True

        filtered_handlers = []

        for handler in root_logger.handlers:
            if handler is not html_handler:
                # Remove span end messages noise from other handlers
                handler.addFilter(_SpanEndFilter())
                filtered_handlers.append(handler)

        yield

        self.test_tmp_path = None
        root_logger.removeHandler(html_handler)
        html_handler.close()

        for handler in filtered_handlers:
            handler.removeFilter(_SpanEndFilter())

        log_path = item.stash[self.log_path_key]
        self._write_html_log_path(item, log_path, flush=True)

    def _get_log_path(self, item: pytest.Item) -> Path:
        if custom_dir := item.config.getoption("html_output_dir"):
            custom_dir.resolve().mkdir(parents=True, exist_ok=True)
            return self._get_test_log_path(item, custom_dir)

        if item.config.getoption("html_use_test_tmp"):
            # Will be transferred on test setup to the correct location
            return self._session_scoped_test_log_path(item)

        return self._session_scoped_test_log_path(item)

    def _format_fixture_call(
        self, fixturedef: pytest.FixtureDef, request: pytest.FixtureRequest
    ) -> str:
        s = f"{fixturedef.argname}("
        arg_list = []
        for arg in fixturedef.argnames:
            if arg == "request":
                arg_list.append("request")
                continue
            result = request.getfixturevalue(arg)
            arg_list.append(f"{arg}={pretty_repr(result)}")

        s += ", ".join(arg_list)

        if fixturedef.params is not None and len(fixturedef.params) > 0:
            s += f", params={fixturedef.params}"
        s += ")"
        return s

    @pytest.hookimpl(hookwrapper=True)
    def pytest_fixture_setup(
        self, fixturedef: pytest.FixtureDef, request: pytest.FixtureRequest
    ) -> Iterator[None]:
        """Wrap all fixture functions with the logging decorator."""

        logger = get_logger(fixturedef.argname)
        call_str = self._format_fixture_call(fixturedef, request)
        with logger.span.debug(f"setup fixture {call_str}", highlight=True):
            result = yield
            try:
                fix_result = result.get_result()
                logger.debug(
                    f"setup fixture {fixturedef.argname}() -> {pretty_repr(fix_result)}",
                    highlight=True,
                )
            except Exception as e:
                logger.error(
                    f"setup fixture {fixturedef.argname}() !-> {pretty_repr(e)}",
                    highlight=True,
                )

    @pytest.fixture(autouse=True)
    def _extract_human_object(self, request: pytest.FixtureRequest, human: Human) -> None:
        """Fixture to extract and stash the human object for the test."""
        item = request.node
        item.stash[self.human_logger_key] = human

    @pytest.fixture(autouse=True)
    def _relocate_test_log(self, request: pytest.FixtureRequest, tmp_path: Path) -> None:
        """Fixture to relocate the test log file to the test temporary directory if needed."""
        item = request.node
        if not is_output_to_test_tmp(item.config):
            return

        new_log_path = tmp_path / "test.html"
        logging.info(f"Relocating HTML log file to {new_log_path}")

        handler = item.stash[self.html_log_handler_key]
        handler.relocate(new_log_path)
        item.stash[self.log_path_key] = new_log_path

    # Depend on _relocate_test_log fixture to ensure it runs first
    @pytest.fixture
    def human_test_log_path(self, request: pytest.FixtureRequest, _relocate_test_log: None) -> Path:
        """Fixture to get the HTML log file path for the current test."""
        item = request.node
        log_path = item.stash[self.log_path_key]
        return log_path

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_setup(self, item: pytest.Item) -> Iterator[None]:
        """Start a span covering all fixture setup for this test item."""

        logger = self._get_test_logger(item)
        with logger.span.info("Test setup"):
            yield

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_teardown(self, item: pytest.Item, nextitem: object) -> Iterator[None]:
        """Start a span covering all fixture cleanup (teardown) for this test item."""

        logger = self._get_test_logger(item)
        with logger.span.info("Test teardown"):
            yield

    def pytest_fixture_post_finalizer(
        self, fixturedef: pytest.FixtureDef, request: pytest.FixtureRequest
    ) -> None:
        """Log when fixture finalizer finishes call."""

        # This method is only called after the fixture finished.
        # We can log each cleanup fixture in its own span, but it is
        # too hacky and involved.
        # Therefore currently logging a single line for teardown.

        if fixturedef.cached_result is None:
            # fixture was already cleaned up, skipping log
            return

        logger = get_logger(fixturedef.argname)
        logger.debug(f"Tore down fixture {fixturedef.argname}()", highlight=True)

    def pytest_exception_interact(
        self,
        node: Node,
        call: pytest.CallInfo,
        report: pytest.TestReport,
    ) -> None:
        """Log test exceptions in an error span."""
        logger = get_logger(node.name)
        excinfo = call.excinfo
        if excinfo is None:
            logger.error("Failed extracting exception info")
            return

        traceback = report.longreprtext

        with logger.span.error(
            f"Exception: {excinfo.type.__name__} {excinfo.value}", highlight=True
        ):
            logger.error(f"traceback: {traceback}", highlight=True)

    def pytest_assertion_pass(self, item: pytest.Item, lineno: int, orig: str, expl: str) -> None:
        """Log successful assertions to the test log."""
        logger = self._get_test_logger(item)
        logger.debug(f"assert {orig}", highlight=True)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item: pytest.Item, call: pytest.CallInfo) -> Iterator[None]:
        """Hook to create the test report.

        We use it to attach the `item` to the `report` object.
        """  # noqa: D401
        outcome = yield
        report = outcome.get_result()

        report.item = item

    def _log_artifacts(self, human: Human) -> None:
        for attachment in human.artifacts.logs():
            with human.log.span.info(attachment.file_name):
                if attachment.description:
                    human.log.info(f"# {attachment.description}", highlight=True)
                content = cast(str, attachment.content)
                human.log.info(content, highlight=True)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        """Log test report information to the HTML log."""
        if report.when != "teardown":
            return

        logger = get_logger(report.nodeid)
        human: Human = report.item.stash.get(self.human_logger_key, None)

        with logger.span.info("Test artifacts"):
            for section_name, content in report.sections:
                if section_name.startswith("Captured log"):
                    # no need to write the logs again
                    continue

                with logger.span.info(f"{section_name}"):
                    logger.info(f"{content}", highlight=True)

            if human:
                self._log_artifacts(human)
