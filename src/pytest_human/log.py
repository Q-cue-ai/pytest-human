"""Custom logging utilities for pytest-human."""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator, MutableMapping
from contextlib import AbstractContextManager, ExitStack, contextmanager
from typing import Any, Optional

TRACE_LEVEL_NUM = logging.NOTSET + 5

_SPAN_START_TAG = "span_start"
_SPAN_END_TAG = "span_end"
_TRACED_TAG = "was_traced"
_LOCATION_TAG = "_location"
_SYNTAX_HIGHLIGHT_TAG = "syntax"
_HIGHLIGHT_EXTRA = {_SYNTAX_HIGHLIGHT_TAG: True}

_USER_HTML_NAMESPACE = logging.getLogger("human.user.html")
_USER_NAMESPACE = logging.getLogger("human.user")
_INTERNAL_NAMESPACE = logging.getLogger("human")


class HtmlLogging:
    """Manages Html logging.

    Sets up a logging handler that only logs to the HTML log, to be used by default
    for library and user logging through library.
    """

    @staticmethod
    @contextmanager
    def setup_single(handler: logging.Handler, namespace: str, level: int) -> Iterator[None]:
        """Context manager to set and clear the HTML handler."""
        html_log = logging.getLogger(namespace)
        old_propagate = html_log.propagate
        old_level = html_log.level
        html_log.propagate = False
        html_log.setLevel(level)
        html_log.addHandler(handler)
        try:
            yield
        finally:
            html_log.propagate = old_propagate
            html_log.handlers.remove(handler)
            html_log.setLevel(old_level)

    @staticmethod
    @contextmanager
    def setup_multiple(
        handlers: logging.Handler, namespaces: list[str], level: int
    ) -> Iterator[None]:
        """Context manager to set and clear the HTML handler on multiple namespaces."""
        with ExitStack() as stack:
            for namespace in namespaces:
                stack.enter_context(HtmlLogging.setup_single(handlers, namespace, level))
            yield

    @staticmethod
    @contextmanager
    def setup(
        handler: logging.Handler, level: int = logging.DEBUG, log_to_all: bool = False
    ) -> Iterator[None]:
        """Context manager to setup HTML logging on human namespaces."""

        if log_to_all:
            yield
            return

        with HtmlLogging.setup_multiple(
            handler, ["human.user.html", "human.tracing", "human.plugin"], level=level
        ):
            yield


class SpanLogger:
    """Logger interface for logging spans.

    The interface is similar to a regular logger, but each method is
    a context manager that creates a nested logging span.
    """

    def __init__(self, logger: TestLogger) -> None:
        self._logger = logger

    @contextmanager
    def emit(
        self,
        log_level: int,
        message: str,
        highlight: bool = False,
        extra: Optional[dict[str, Any]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Iterator[None]:
        """Create a nested logging span.

        A span is a logging message that can be expanded/collapsed in the HTML log viewer.
        """
        extra = extra or {}
        _add_stacklevel_py310_compat(kwargs, added=1)
        if highlight:
            extra |= _HIGHLIGHT_EXTRA
        try:
            self._logger.log(
                log_level,
                message,
                *args,
                **kwargs,
                extra=extra | {_SPAN_START_TAG: True},
            )

            yield
        finally:
            self._logger.log(log_level, "", extra={_SPAN_END_TAG: True})

    def trace(self, message: str, *args: Any, **kwargs: Any) -> AbstractContextManager[None]:
        """Create a nested TRACE logging span.

        This is a logging message that can be expanded/collapsed in the HTML log viewer.
        Using TRACE level requires enabling TRACE logging via TestLogger.setup_trace_logging()
        """
        _add_stacklevel(kwargs)
        return self.emit(TRACE_LEVEL_NUM, message, *args, **kwargs)

    def debug(self, message: str, *args: Any, **kwargs: Any) -> AbstractContextManager[None]:
        """Create a nested DEBUG logging span.

        This is a logging message that can be expanded/collapsed in the HTML log viewer.
        """
        _add_stacklevel(kwargs)
        return self.emit(logging.DEBUG, message, *args, **kwargs)

    def info(self, message: str, *args: Any, **kwargs: Any) -> AbstractContextManager[None]:
        """Create a nested INFO logging span.

        This is a logging message that can be expanded/collapsed in the HTML log viewer.
        """
        _add_stacklevel(kwargs)
        return self.emit(logging.INFO, message, *args, **kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any) -> AbstractContextManager[None]:
        """Create a nested WARNING logging span.

        This is a logging message that can be expanded/collapsed in the HTML log viewer.
        """
        _add_stacklevel(kwargs)
        return self.emit(logging.WARNING, message, *args, **kwargs)

    def error(self, message: str, *args: Any, **kwargs: Any) -> AbstractContextManager[None]:
        """Create a nested ERROR logging span.

        This is a logging message that can be expanded/collapsed in the HTML log viewer.
        """
        _add_stacklevel(kwargs)
        return self.emit(logging.ERROR, message, *args, **kwargs)

    def critical(self, message: str, *args: Any, **kwargs: Any) -> AbstractContextManager[None]:
        """Create a nested CRITICAL logging span.

        This is a logging message that can be expanded/collapsed in the HTML log viewer.
        """
        _add_stacklevel(kwargs)
        return self.emit(logging.CRITICAL, message, *args, **kwargs)


class TestLogger(logging.LoggerAdapter):
    """A logger adapter (wrapper) that adds a trace method, spans and syntax highlighting."""

    __test__ = False
    TRACE = TRACE_LEVEL_NUM
    span: SpanLogger
    """Logs spans for nested logging."""

    def __init__(self, logger: logging.Logger) -> None:
        super().__init__(logger, {})
        self.span = SpanLogger(self)

    def _log_with_highlight(
        self,
        level: int,
        message: str,
        args: tuple,
        highlight: bool = False,
        **kwargs: Any,
    ) -> None:
        """Central method to handle the highlighting logic."""
        if self.isEnabledFor(level):
            if highlight:
                extra = kwargs.get("extra", {}) | _HIGHLIGHT_EXTRA
                kwargs["extra"] = extra

            _add_stacklevel_py310_compat(kwargs, 1)

            self.log(level, message, *args, **kwargs)

    def process(
        self,
        msg: Any,
        kwargs: MutableMapping[str, Any],
    ) -> tuple[Any, MutableMapping[str, Any]]:
        """Pass extra fields to the log record.

        The logging.LoggerAdapter.process method overwrites the log record
        extra fields if we don't handle them here.
        """
        return msg, kwargs

    def emit(self, log_level: int, message: str, *args: Any, **kwargs: Any) -> None:
        """Emit a log message at the specified log level."""
        _add_stacklevel(kwargs)
        self._log_with_highlight(log_level, message, args, **kwargs)

    def trace(self, message: str, *args: Any, highlight: bool = False, **kwargs: Any) -> None:
        """Log a TRACE message."""
        _add_stacklevel(kwargs)
        self._log_with_highlight(TRACE_LEVEL_NUM, message, args, highlight, **kwargs)

    def debug(self, message: str, *args: Any, highlight: bool = False, **kwargs: Any) -> None:
        """Log a DEBUG message."""
        _add_stacklevel(kwargs)
        self._log_with_highlight(logging.DEBUG, message, args, highlight, **kwargs)

    def info(self, message: str, *args: Any, highlight: bool = False, **kwargs: Any) -> None:
        """Log an INFO message."""
        _add_stacklevel(kwargs)
        self._log_with_highlight(logging.INFO, message, args, highlight, **kwargs)

    def warning(self, message: str, *args: Any, highlight: bool = False, **kwargs: Any) -> None:
        """Log a WARNING message."""
        _add_stacklevel(kwargs)
        self._log_with_highlight(logging.WARNING, message, args, highlight, **kwargs)

    def error(self, message: str, *args: Any, highlight: bool = False, **kwargs: Any) -> None:
        """Log an ERROR message."""
        _add_stacklevel(kwargs)
        self._log_with_highlight(logging.ERROR, message, args, highlight, **kwargs)

    def critical(self, message: str, *args: Any, highlight: bool = False, **kwargs: Any) -> None:
        """Log a CRITICAL message."""
        _add_stacklevel(kwargs)
        self._log_with_highlight(logging.CRITICAL, message, args, highlight, **kwargs)

    @classmethod
    def setup_trace_logging(cls) -> None:
        """Add the TRACE logging level to the logging module.

        Run this early enough to setup the TRACE log level
        For example the pytest_cmdline_main hook under the top-level conftest.py
        """
        logging.TRACE = TRACE_LEVEL_NUM  # pyright: ignore[reportAttributeAccessIssue]: monkey patching
        logging.addLevelName(TRACE_LEVEL_NUM, "TRACE")


def _add_stacklevel(kwargs: dict[str, Any], added: int = 1) -> dict[str, Any]:
    """Increment the logging frames stacklevel. Defaults to 1 if missing.

    This is used to remove helper function frames from the log record source info.
    """
    current_level = kwargs.pop("stacklevel", 1)
    kwargs["stacklevel"] = current_level + added
    return kwargs


def _add_stacklevel_py310_compat(kwargs: dict[str, Any], added: int = 1) -> dict[str, Any]:
    """Increment the logging frames stacklevel with Python 3.10 compatibility.

    Apparently in Python 3.11 the entire stacklevel handling was changed,
    https://github.com/python/cpython/pull/28287
    In order to make this compatible with later versions, we need to adjust the stacklevel
    differently.
    """
    if sys.version_info[:2] <= (3, 10):
        return _add_stacklevel(kwargs, added + 1)

    return _add_stacklevel(kwargs, added)


def get_global_logger(name: str) -> TestLogger:
    """Return a logger that supports pytest-human features in any logging namespace.

    Args:
        name: Name of the logger, typically `__name__`.

    """
    logger = logging.getLogger(name)
    return TestLogger(logger)


def get_logger(name: str, html_only: bool = True) -> TestLogger:
    """Return a logger that supports pytest-human features under the human namespace.

    While get_global_logger supports any namespace, this function always uses the human logging
    namespace, with the added benefit of controlling whether the logger logs only to the HTML log
    or to all handlers (including HTML).

    By default logs only to HTML log. To log to all handlers, set html_only=False.

    Args:
        name: Name of the logger, typically `__name__`.
        html_only:   If True, returns a logger that only logs to the HTML handler.
                    Overriden by --html-log-to-all flag.

    Returns:
        TestLogger: The logger instance.

    """
    if html_only:
        logger = _USER_HTML_NAMESPACE.getChild(name)
        return TestLogger(logger)

    logger = _USER_NAMESPACE.getChild(name)
    return TestLogger(logger)


def _get_internal_logger(name: str) -> TestLogger:
    """Return an internal logger for pytest-human library code."""
    logger = _INTERNAL_NAMESPACE.getChild(name)
    return TestLogger(logger)
