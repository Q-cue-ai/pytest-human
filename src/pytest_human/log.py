"""Custom logging utilities for pytest-human."""

import functools
import inspect
import logging
import threading
from collections.abc import Callable, Iterator, MutableMapping
from contextlib import AbstractContextManager, contextmanager
from typing import Any, Optional

from rich.pretty import pretty_repr

TRACE_LEVEL_NUM = logging.NOTSET + 5

_SPAN_START_TAG = "span_start"
_SPAN_END_TAG = "span_end"
_SYNTAX_HIGHLIGHT_TAG = "syntax"
_HIGHLIGHT_EXTRA = {_SYNTAX_HIGHLIGHT_TAG: True}

_log_local = threading.local()


class TestLogger(logging.LoggerAdapter):
    """Custom logger class that adds a trace method, support for spans and syntax highlighting."""

    __test__ = False
    TRACE = TRACE_LEVEL_NUM

    def __init__(self, logger: logging.Logger) -> None:
        super().__init__(logger, {})

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

            self._log(level, message, args, **kwargs)

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
        self._log_with_highlight(log_level, message, args, **kwargs)

    def trace(self, message: str, *args: Any, highlight: bool = False, **kwargs: Any) -> None:
        """Log a TRACE message."""
        self._log_with_highlight(TRACE_LEVEL_NUM, message, args, highlight, **kwargs)

    def debug(self, message: str, *args: Any, highlight: bool = False, **kwargs: Any) -> None:
        """Log a DEBUG message."""
        self._log_with_highlight(logging.DEBUG, message, args, highlight, **kwargs)

    def info(self, message: str, *args: Any, highlight: bool = False, **kwargs: Any) -> None:
        """Log an INFO message."""
        self._log_with_highlight(logging.INFO, message, args, highlight, **kwargs)

    def warning(self, message: str, *args: Any, highlight: bool = False, **kwargs: Any) -> None:
        """Log a WARNING message."""
        self._log_with_highlight(logging.WARNING, message, args, highlight, **kwargs)

    def error(self, message: str, *args: Any, highlight: bool = False, **kwargs: Any) -> None:
        """Log an ERROR message."""
        self._log_with_highlight(logging.ERROR, message, args, highlight, **kwargs)

    def critical(self, message: str, *args: Any, highlight: bool = False, **kwargs: Any) -> None:
        """Log a CRITICAL message."""
        self._log_with_highlight(logging.CRITICAL, message, args, highlight, **kwargs)

    @contextmanager
    def span(
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
        if highlight:
            extra |= _HIGHLIGHT_EXTRA
        try:
            self.log(
                log_level,
                message,
                *args,
                **kwargs,
                extra=extra | {_SPAN_START_TAG: True},
            )
            yield
        finally:
            self.log(log_level, "", extra={_SPAN_END_TAG: True})

    def span_trace(self, message: str, *args: Any, **kwargs: Any) -> AbstractContextManager[None]:
        """Create a nested TRACE logging span.

        This is a logging message that can be expanded/collapsed in the HTML log viewer.
        Using TRACE level requires enabling TRACE logging via TestLogger.setup_trace_logging()
        """
        return self.span(TRACE_LEVEL_NUM, message, *args, **kwargs)

    def span_debug(self, message: str, *args: Any, **kwargs: Any) -> AbstractContextManager[None]:
        """Create a nested DEBUG logging span.

        This is a logging message that can be expanded/collapsed in the HTML log viewer.
        """
        return self.span(logging.DEBUG, message, *args, **kwargs)

    def span_info(self, message: str, *args: Any, **kwargs: Any) -> AbstractContextManager[None]:
        """Create a nested INFO logging span.

        This is a logging message that can be expanded/collapsed in the HTML log viewer.
        """
        return self.span(logging.INFO, message, *args, **kwargs)

    def span_warning(self, message: str, *args: Any, **kwargs: Any) -> AbstractContextManager[None]:
        """Create a nested WARNING logging span.

        This is a logging message that can be expanded/collapsed in the HTML log viewer.
        """
        return self.span(logging.WARNING, message, *args, **kwargs)

    def span_error(self, message: str, *args: Any, **kwargs: Any) -> AbstractContextManager[None]:
        """Create a nested ERROR logging span.

        This is a logging message that can be expanded/collapsed in the HTML log viewer.
        """
        return self.span(logging.ERROR, message, *args, **kwargs)

    def span_critical(
        self, message: str, *args: Any, **kwargs: Any
    ) -> AbstractContextManager[None]:
        """Create a nested CRITICAL logging span.

        This is a logging message that can be expanded/collapsed in the HTML log viewer.
        """
        return self.span(logging.CRITICAL, message, *args, **kwargs)

    @classmethod
    def setup_trace_logging(cls) -> None:
        """Add the TRACE logging level to the logging module.

        Run this early enough to setup the TRACE log level
        For example the pytest_cmdline_main hook under the top-level conftest.py
        """
        logging.TRACE = TRACE_LEVEL_NUM  # pyright: ignore[reportAttributeAccessIssue]: monkey patching
        logging.addLevelName(TRACE_LEVEL_NUM, "TRACE")


class _SpanEndFilter(logging.Filter):
    """A logging filter that blocks log records marking the end of a span."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out span end log records.

        These can spam the log with non-HTML log handlers.
        """
        return not getattr(record, _SPAN_END_TAG, False)


def _get_class_name(func: Callable) -> str:
    """Get a class name from a method or function."""
    if self_attr := getattr(func, "__self__", None):
        if inspect.ismodule(self_attr):
            return self_attr.__name__
        return self_attr.__class__.__name__

    func_components = func.__qualname__.split(".")

    if len(func_components) == 1:
        # last module component is actually interesting
        return func.__module__.split(".")[-1]

    # First qualifier is class
    return func_components[0]


def _format_call_string(
    func: Callable, args: tuple, kwargs: dict, suppress_params: bool = False
) -> str:
    sig = inspect.signature(func)
    bound_args = sig.bind(*args, **kwargs)
    bound_args.apply_defaults()

    class_name = _get_class_name(func)
    func_name = func.__name__
    params = []
    param_str = ""
    for name, value in bound_args.arguments.items():
        if name == "self":
            continue
        params.append(f"{name}={value!r}")

    if not suppress_params:
        param_str = ", ".join(params)

    return f"{class_name}.{func_name}({param_str})"


def _is_in_trace() -> bool:
    """Return whether we are currently already tracing a @log_call."""
    return getattr(_log_local, "in_trace", False)


@contextmanager
def _in_trace() -> Iterator[None]:
    """Context manager to set the in_trace flag."""
    previous = getattr(_log_local, "in_trace", False)
    _log_local.in_trace = True
    try:
        yield
    finally:
        _log_local.in_trace = previous


@contextmanager
def _out_of_trace() -> Iterator[None]:
    """Context manager to unset the in_trace flag."""
    previous = getattr(_log_local, "in_trace", False)
    _log_local.in_trace = False
    try:
        yield
    finally:
        _log_local.in_trace = previous


def log_call(
    *, log_level: int = logging.INFO, suppress_return: bool = False, suppress_params: bool = False
) -> Callable[[Callable], Callable]:
    """Decorate log method calls with parameters and return values.

    :param log_level: The log level that will be used for logging.
                      Errors are always logged with ERROR level.
    :param suppress_return: If True, do not log the return value.
    """

    def decorator(func: Callable) -> Callable:
        logger = get_logger(func.__module__)
        is_async = inspect.iscoroutinefunction(func)

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any):  # noqa: ANN202
                if _is_in_trace():
                    return await func(*args, **kwargs)

                if not logger.isEnabledFor(log_level):
                    return await func(*args, **kwargs)

                with _in_trace():
                    func_str = _format_call_string(
                        func, args, kwargs, suppress_params=suppress_params
                    )
                    with logger.span(log_level, f"async {func_str}", highlight=True):
                        try:
                            with _out_of_trace():
                                result = await func(*args, **kwargs)
                            result_str = "<suppressed>" if suppress_return else pretty_repr(result)
                            logger.debug(f"async {func_str} -> {result_str}", highlight=True)
                            return result
                        except Exception as e:
                            logger.error(f"async {func_str} !-> {e!r}", highlight=True)
                            raise e

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any):  # noqa: ANN202
            if _is_in_trace():
                return func(*args, **kwargs)

            if not logger.isEnabledFor(log_level):
                return func(*args, **kwargs)

            with _in_trace():
                func_str = _format_call_string(func, args, kwargs, suppress_params=suppress_params)
                with logger.span(log_level, func_str, highlight=True):
                    try:
                        with _out_of_trace():
                            result = func(*args, **kwargs)
                        result_str = "<suppressed>" if suppress_return else pretty_repr(result)
                        logger.debug(f"{func_str} -> {result_str}", highlight=True)
                        return result
                    except Exception as e:
                        logger.error(f"{func_str} !-> {e!r}", highlight=True)
                        raise e

        return sync_wrapper

    return decorator


def _locate_function(func: Callable) -> tuple[Any, str]:
    module = inspect.getmodule(func)
    if module is None:
        raise ValueError(
            f"Cannot patch module for {func} Could not determine the module."
            " It might be dynamically created."
        )

    qualname = func.__qualname__
    parts = qualname.split(".")

    container = module
    for part in parts[:-1]:
        # A very extreme edge case, where a function is defined inside another function
        # and returned as a closure.
        if part == "<locals>":
            raise ValueError(f"Cannot patch {qualname}: it is a local function.")
        container = getattr(container, part)

    method_name = parts[-1]
    return container, method_name


def _patch_method_logger(target: Callable, **kwargs: Any) -> None:
    """Patch a method or function to log its calls using log_call decorator.

    This is useful to log 3rd party library methods without modifying their source code.
    """
    if getattr(target, "_is_patched_logger", False):
        logging.warning(f"Target {target.__qualname__} is already patched for logging.")
        return

    container, method_name = _locate_function(target)

    decorated = log_call(**kwargs)(target)
    decorated._is_patched_logger = True  # noqa: SLF001

    setattr(container, method_name, decorated)

    return


def _get_public_methods(container: Any) -> list[Callable]:
    """Get all public methods of a class or module."""
    methods = []
    for name, member in inspect.getmembers(container):
        if name.startswith("_"):
            continue
        if inspect.isroutine(member):
            methods.append(member)
    return methods


@contextmanager
def log_calls(  # noqa: ANN201
    *args: Callable, **kwargs: Any
):
    """Context manager to log calls to a method or function using log_call decorator.

    This is useful to log 3rd party library methods without modifying their source code
    and adding a decorator.
    """
    try:
        for target in args:
            _patch_method_logger(target, **kwargs)
        yield
    finally:
        for target in args:
            container, method_name = _locate_function(target)
            current = getattr(container, method_name)
            if getattr(current, "_is_patched_logger", False):
                setattr(container, method_name, target)


@contextmanager
def log_public_api(  # noqa: ANN201
    *args: Any, **kwargs: Any
):
    """Context manager to log calls to all public methods of a class or module.

    This is useful to log 3rd party library methods without modifying their source code
    and adding a decorator.
    """
    methods = []
    for container in args:
        methods.extend(_get_public_methods(container))
    with log_calls(*methods, **kwargs):
        yield


def get_logger(name: str) -> TestLogger:
    """Return a logger customized for our tests.

    :param name: Name of the logger, typically __name__
    """
    logger = logging.getLogger(name)
    return TestLogger(logger)
