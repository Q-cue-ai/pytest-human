"""Custom logging utilities for pytest-human."""

from __future__ import annotations

import functools
import inspect
import logging
import threading
from collections.abc import Callable, Iterator, MutableMapping
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import Any, Optional

from rich.pretty import pretty_repr

TRACE_LEVEL_NUM = logging.NOTSET + 5

_SPAN_START_TAG = "span_start"
_SPAN_END_TAG = "span_end"
_SYNTAX_HIGHLIGHT_TAG = "syntax"
_HIGHLIGHT_EXTRA = {_SYNTAX_HIGHLIGHT_TAG: True}

_log_local = threading.local()


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
        # account for this method and contextmanager frames
        _add_stacklevel(kwargs, added=2)
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

            # account for this method and Adapter.log frames
            _add_stacklevel(kwargs, 2)

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
    func: Callable,
    args: tuple,
    kwargs: dict,
    suppress_params: bool = False,
    suppress_self: bool = True,
) -> str:
    sig = inspect.signature(func)
    bound_args = sig.bind(*args, **kwargs)
    bound_args.apply_defaults()

    class_name = _get_class_name(func)
    func_name = func.__name__
    params = []
    param_str = ""
    for name, value in bound_args.arguments.items():
        if suppress_self and name == "self":
            continue
        params.append(f"{name}={value!r}")

    if not suppress_params:
        param_str = ", ".join(params)

    return f"{class_name}.{func_name}({param_str})"


def _is_in_trace() -> bool:
    """Return whether we are currently already tracing a @traced."""
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


def traced(
    *,
    log_level: int = logging.INFO,
    suppress_return: bool = False,
    suppress_params: bool = False,
    suppress_self: bool = True,
) -> Callable[[Callable], Callable]:
    """Decorate log method calls with parameters and return values.

    :param log_level: The log level that will be used for logging.
                      Errors are always logged with ERROR level.
    :param suppress_return: If True, do not log the return value.
    :param suppress_params: If True, do not log the parameters.
    :param suppress_self: If True, do not log the 'self' parameter for methods. True by default.
    """

    def decorator(func: Callable) -> Callable:
        logger = get_logger(func.__module__)
        is_async = inspect.iscoroutinefunction(func)
        extra = {"_traced": True}

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any):  # noqa: ANN202
                if _is_in_trace():
                    return await func(*args, **kwargs)

                if not logger.isEnabledFor(log_level):
                    return await func(*args, **kwargs)

                with _in_trace():
                    func_str = _format_call_string(
                        func,
                        args,
                        kwargs,
                        suppress_params=suppress_params,
                        suppress_self=suppress_self,
                    )
                    # account for context manager and wrapper frames
                    log_kwargs = _add_stacklevel({}, 2)
                    log_kwargs.setdefault("extra", {}).update(extra)
                    with logger.span.emit(
                        log_level, f"async {func_str}", highlight=True, **log_kwargs
                    ):
                        try:
                            log_kwargs = _add_stacklevel({}, 1)
                            with _out_of_trace():
                                result = await func(*args, **kwargs)
                            result_str = "<suppressed>" if suppress_return else pretty_repr(result)
                            logger.debug(
                                f"async {func_str} -> {result_str}", highlight=True, **log_kwargs
                            )
                            return result
                        except Exception as e:
                            logger.error(
                                f"async {func_str} !-> {e!r}", highlight=True, **log_kwargs
                            )
                            raise e

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any):  # noqa: ANN202
            if _is_in_trace():
                return func(*args, **kwargs)

            if not logger.isEnabledFor(log_level):
                return func(*args, **kwargs)

            with _in_trace():
                func_str = _format_call_string(
                    func, args, kwargs, suppress_params=suppress_params, suppress_self=suppress_self
                )
                # account for context manager and wrapper frames
                log_kwargs = _add_stacklevel({}, 2)
                log_kwargs.setdefault("extra", {}).update(extra)
                with logger.span.emit(log_level, func_str, highlight=True, **log_kwargs):
                    log_kwargs = _add_stacklevel({}, 1)
                    try:
                        with _out_of_trace():
                            result = func(*args, **kwargs)
                        result_str = "<suppressed>" if suppress_return else pretty_repr(result)
                        logger.debug(f"{func_str} -> {result_str}", highlight=True, **log_kwargs)
                        return result
                    except Exception as e:
                        logger.error(f"{func_str} !-> {e!r}", highlight=True, **log_kwargs)
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
    """Patch a method or function to log its calls using traced decorator.

    This is useful to log 3rd party library methods without modifying their source code.
    """
    if getattr(target, "_is_patched_logger", False):
        logging.warning(f"Target {target.__qualname__} is already patched for logging.")
        return

    container, method_name = _locate_function(target)

    decorated = traced(**kwargs)(target)
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


def get_function_location(func: Callable) -> dict[str, Any]:
    """Get the source location of a function or method.

    :param func: The function or method to get the location for.
    :return: An extra dictionary for logging
    """
    func = inspect.unwrap(func)
    try:
        _, starting_line_no = inspect.getsourcelines(func)
        if source_file := inspect.getsourcefile(func):
            pathname = Path(source_file).resolve().as_posix()
            filename = Path(source_file).name
        else:
            pathname = filename = "<unknown>"

        return {
            "filename": filename,
            "pathname": pathname,
            "lineno": starting_line_no,
            "funcName": func.__name__,
            "module": func.__module__,
        }
    except (TypeError, OSError):
        return {
            "filename": "<unknown>",
            "pathname": "<unknown>",
            "lineno": 0,
            "funcName": func.__name__,
            "module": func.__module__,
        }


@contextmanager
def trace_calls(  # noqa: ANN201
    *args: Callable, **kwargs: Any
):
    """Context manager to log calls to a method or function using traced decorator.

    This is useful to log 3rd party library methods without modifying their source code
    and adding a decorator.

    :param log_level: The log level that will be used for logging.
                      Errors are always logged with ERROR level.
    :param suppress_return: If True, do not log the return value.
    :param suppress_params: If True, do not log the parameters.
    :param suppress_self: If True, do not log the 'self' parameter for methods. True by default.
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
def trace_public_api(  # noqa: ANN201
    *args: Any, **kwargs: Any
):
    """Context manager to log calls to all public methods of a class or module.

    This is useful to log 3rd party library methods without modifying their source code
    and adding a decorator.

    :param log_level: The log level that will be used for logging.
                      Errors are always logged with ERROR level.
    :param suppress_return: If True, do not log the return value.
    :param suppress_params: If True, do not log the parameters.
    :param suppress_self: If True, do not log the 'self' parameter for methods. True by default.
    """
    methods = []
    for container in args:
        methods.extend(_get_public_methods(container))
    with trace_calls(*methods, **kwargs):
        yield


def get_logger(name: str) -> TestLogger:
    """Return a logger customized for our tests.

    :param name: Name of the logger, typically __name__
    """
    logger = logging.getLogger(name)
    return TestLogger(logger)
