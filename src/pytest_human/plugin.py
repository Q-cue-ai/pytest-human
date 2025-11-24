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
from _pytest._code.code import ExceptionRepr
from _pytest.nodes import Node
from rich.pretty import pretty_repr

from pytest_human._flags import is_output_to_test_tmp
from pytest_human.exceptions import HumanLogLevelWarning
from pytest_human.html_handler import HtmlFileHandler, HtmlHandlerContext
from pytest_human.human import Human
from pytest_human.log import TestLogger, get_function_location, get_logger
from pytest_human.repo import Repo


class HtmlLogPlugin:
    """Pytest plugin to create HTML log files for each test."""

    HTML_LOG_PLUGIN_NAME = "html-log-plugin"
    html_log_handler_key = pytest.StashKey[HtmlFileHandler]()
    human_logger_key = pytest.StashKey[Human]()
    test_item_key = pytest.StashKey[pytest.Item]()

    def __init__(self) -> None:
        self.test_tmp_path = None
        self._warned_about_log_level = False
        self._test_reports_paths: dict[str, Path] = {}
        self._repo = Repo()

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
    def _print_test_report_location(
        cls,
        terminal: pytest.TerminalReporter,
        config: pytest.Config,
        test_name: str,
        log_path: Path,
        flush: bool = False,
    ) -> None:
        """Log the HTML log path to the terminal."""

        if config.getoption("quiet", config.getoption("html_quiet")):
            return

        terminal.ensure_newline()
        terminal.write("🌎 Test ")
        terminal.write(f"{test_name}", bold=True)
        terminal.write(" HTML log at ")
        terminal.write(f"{log_path.resolve().as_uri()}", bold=True, cyan=True)
        terminal.line("")

        if flush:
            terminal.flush()

    @classmethod
    def _print_item_report_location(
        cls, item: pytest.Item, log_path: Path, flush: bool = False
    ) -> None:
        """Log the HTML log path to the terminal."""

        terminal: pytest.TerminalReporter | None = item.config.pluginmanager.get_plugin(
            "terminalreporter"
        )
        if terminal is None:
            return

        cls._print_test_report_location(
            terminal,
            item.config,
            item.name,
            log_path,
            flush,
        )

    def validate_log_level(self, item: pytest.Item) -> None:
        """Warn if the root logger level is higher than the HTML log level."""
        root_logger = logging.getLogger()
        level = self._get_log_level(item)

        if root_logger.level <= level:
            return

        msg = (
            f"The root logger level {logging.getLevelName(root_logger.level)} is higher than "
            f"the HTML log level {logging.getLevelName(level)}."
            " This means logs will be missing from the HTML log."
            "\nConsider lowering the logger level using the --log-level option."
        )

        if not self._warned_about_log_level:
            warnings.warn(
                msg,
                HumanLogLevelWarning,
            )
            self._warned_about_log_level = True

        logging.warning(msg)

    @classmethod
    def _is_live_logging_enabled(cls, config: pytest.Config) -> bool:
        """Check if live logging is enabled."""
        return config.getini("log_cli")

    @pytest.hookimpl(tryfirst=True, hookwrapper=True)
    def pytest_runtest_protocol(
        self, item: pytest.Item, nextitem: Optional[pytest.Item]
    ) -> Iterator[None]:
        """Set up HTML log handler for the test and clean up afterwards."""
        item.config.stash[self.test_item_key] = item
        log_path = self._get_log_path(item)
        level = self._get_log_level(item)
        self.validate_log_level(item)

        with HtmlHandlerContext(
            filename=log_path,
            title=item.name,
            description=self._get_test_doc_string(item),
            level=level,
            repo=self._repo,
        ) as html_handler:
            item.stash[self.html_log_handler_key] = html_handler
            yield

        self.test_tmp_path = None
        self._test_reports_paths[item.name] = html_handler.path

        if self._is_live_logging_enabled(item.config):
            self._print_item_report_location(item, log_path, flush=True)

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
        extra = {"_location": get_function_location(fixturedef.func)}
        with logger.span.debug(f"setup fixture {call_str}", highlight=True, extra=extra):
            result = yield
            try:
                fix_result = result.get_result()
                logger.debug(
                    f"setup fixture {fixturedef.argname}() -> {pretty_repr(fix_result)}",
                    highlight=True,
                    extra=extra,
                )
            except Exception as e:
                logger.error(
                    f"setup fixture {fixturedef.argname}() !-> {pretty_repr(e)}",
                    highlight=True,
                    extra=extra,
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

    # Depend on _relocate_test_log fixture to ensure it runs first
    @pytest.fixture
    def human_test_log_path(self, request: pytest.FixtureRequest, _relocate_test_log: None) -> Path:
        """Fixture to get the HTML log file path for the current test."""
        item = request.node
        log_path = item.stash[self.html_log_handler_key].path
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
        extra = {"_location": get_function_location(fixturedef.func)}
        logger.debug(f"Tore down fixture {fixturedef.argname}()", highlight=True, extra=extra)

    @staticmethod
    def _strip_ansi_codes(text: str) -> str:
        """Remove ANSI escape codes (used for terminal colors) from a string."""

        ansi_escape_pattern = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape_pattern.sub("", text)

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

        traceback = str(report.longreprtext)
        traceback = self._strip_ansi_codes(traceback)

        exception_details = f"Exception: {excinfo.type.__name__} {excinfo.value}"
        with logger.span.error(self._strip_ansi_codes(exception_details), highlight=True):
            logger.error(f"traceback: {traceback}", highlight=True)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item: pytest.Item, call: pytest.CallInfo) -> Iterator[None]:
        """Hook to create the test report.

        We use it to attach the `item` to the `report` object, and track xfail exceptions.
        """  # noqa: D401
        outcome = yield
        report = outcome.get_result()

        report.item = item

        logger = get_logger(item.name)

        # xfail exceptions do not show up in pytest_exception_interact
        if hasattr(report, "wasxfail") and call.excinfo is not None:
            exctext = self._strip_ansi_codes(call.excinfo.exconly())
            logger.warning(f"XFAIL: {report.wasxfail}\n\n{exctext}", highlight=True)

        if not hasattr(report, "wasxfail") and report.skipped:
            logger.info(f"Test {item.name} was skipped.")

    def _log_artifacts(self, human: Human) -> None:
        for attachment in human.artifacts.logs():
            with human.span.info(attachment.file_name):
                if attachment.description:
                    human.log.info(f"# {attachment.description}", highlight=True)
                content = cast(str, attachment.content)
                human.log.info(content, highlight=True)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        """Log test report information to the HTML log."""
        if report.when != "teardown":
            return

        human: Human = report.item.stash.get(self.human_logger_key, None)
        logger = self._get_test_logger(report.item)

        with logger.span.info("Test artifacts"):
            for section_name, content in report.sections:
                if section_name.startswith("Captured log"):
                    # no need to write the logs again
                    continue

                with logger.span.info(f"{section_name}"):
                    logger.info(f"{content}", highlight=True)

            if human:
                self._log_artifacts(human)

    def pytest_assertrepr_compare(
        self, config: pytest.Config, op: str, left: object, right: object
    ) -> Optional[list[str]]:
        """Log all assertion comparisons to the HTML log."""
        test = config.stash[self.test_item_key]
        logger = self._get_test_logger(test)
        logger.error(f"assert {pretty_repr(left)} {op} {pretty_repr(right)}", highlight=True)

        return None

    def pytest_internalerror(self, excrepr: ExceptionRepr) -> None:
        """Log internal pytest errors to the HTML log."""
        logger = get_logger("pytest")
        logger.critical(f"Internal pytest error: {excrepr!s}", highlight=True)

    @pytest.hookimpl(trylast=True)
    def pytest_terminal_summary(
        self, terminalreporter: pytest.TerminalReporter, config: pytest.Config
    ) -> None:
        """Log all HTML log paths to the terminal summary."""
        if self._test_reports_paths:
            terminalreporter.write_sep("-", "pytest-human HTML log reports")

        for test_name, log_path in self._test_reports_paths.items():
            self._print_test_report_location(
                terminalreporter,
                config,
                test_name,
                log_path,
            )

        if self._test_reports_paths:
            terminalreporter.write_sep("-")

        terminalreporter.flush()
