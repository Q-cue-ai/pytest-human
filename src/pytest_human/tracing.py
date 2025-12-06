"""Custom tracing utilities for pytest-human."""

from __future__ import annotations

import functools
import inspect
import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional, overload

from rich.pretty import pretty_repr

from pytest_human.log import _TRACED_TAG, _add_stacklevel, _get_internal_logger

_log_local = threading.local()


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


def _format_call_string(  # noqa: PLR0913
    func: Callable,
    args: tuple,
    kwargs: dict,
    suppress_params: bool = False,
    suppress_self: bool = True,
    suppress_none: bool = False,
    truncate_values: bool = True,
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
        default_repr = _is_default_repr(value)

        if name == "self" and default_repr:
            params.append(f"{name}")
            continue

        if suppress_none and value is None:
            continue

        if _is_default_repr(value):
            params.append(f"{name}=<{type(value).__name__}>")
            continue

        if not truncate_values:
            params.append(f"{name}={pretty_repr(value)}")
            continue

        params.append(f"{name}={_truncated_prepr(value)}")

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


# use as @traced()
@overload
def traced(
    func: Callable,
    *,
    log_level: int = logging.INFO,
    suppress_return: bool = False,
    suppress_params: bool = False,
    suppress_self: bool = True,
    suppress_none: bool = False,
    truncate_values: bool = True,
) -> Callable: ...


# use as @traced
@overload
def traced(
    func: None = None,
    *,
    log_level: int = logging.INFO,
    suppress_return: bool = False,
    suppress_params: bool = False,
    suppress_self: bool = True,
    suppress_none: bool = False,
    truncate_values: bool = True,
) -> Callable[[Callable], Callable]: ...


def traced(  # noqa: PLR0913
    func: Optional[Callable] = None,
    *,
    log_level: int = logging.INFO,
    suppress_return: bool = False,
    suppress_params: bool = False,
    suppress_self: bool = True,
    suppress_none: bool = False,
    truncate_values: bool = True,
) -> Callable[[Callable], Callable]:
    """Decorate log method calls with parameters and return values.

    :param log_level: The log level that will be used for logging.
                      Errors are always logged with ERROR level.
    :param suppress_return: If True, do not log the return value.
    :param suppress_params: If True, do not log the parameters.
    :param suppress_self: If True, do not log the 'self' parameter for methods. True by default.
    :param suppress_none: If True, do not log parameters with None value.
    :param truncate_values: If True, do not truncate long values.
    """

    def decorator(func: Callable) -> Callable:
        is_async = inspect.iscoroutinefunction(func)
        extra = {_TRACED_TAG: True}
        logger = _get_internal_logger("tracing.functions")

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
                        suppress_none=suppress_none,
                        truncate_values=truncate_values,
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
                            result_str = _format_result(result, suppress_return, truncate_values)
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
                    func,
                    args,
                    kwargs,
                    suppress_params=suppress_params,
                    suppress_self=suppress_self,
                    suppress_none=suppress_none,
                    truncate_values=truncate_values,
                )
                # account for context manager and wrapper frames
                log_kwargs = _add_stacklevel({}, 2)
                log_kwargs.setdefault("extra", {}).update(extra)
                with logger.span.emit(log_level, func_str, highlight=True, **log_kwargs):
                    log_kwargs = _add_stacklevel({}, 1)
                    try:
                        with _out_of_trace():
                            result = func(*args, **kwargs)
                        result_str = _format_result(result, suppress_return, truncate_values)
                        logger.debug(f"{func_str} -> {result_str}", highlight=True, **log_kwargs)
                        return result
                    except Exception as e:
                        logger.error(f"{func_str} !-> {e!r}", highlight=True, **log_kwargs)
                        raise e

        return sync_wrapper

    if func is not None:
        return decorator(func)

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


def _is_default_repr(obj: object) -> bool:
    """Check if the object's __repr__ is the default one from object."""
    return type(obj).__repr__ is object.__repr__


def _truncated_prepr(obj: Any) -> str:
    """Get a truncated pretty representation of an object."""
    return pretty_repr(obj, max_string=512, max_depth=3, max_length=10)


def _format_result(obj: Any, suppress_result: bool = False, truncate_values: bool = True) -> str:
    """Format the result for logging."""
    if suppress_result:
        return "<suppressed>"

    if _is_default_repr(obj):
        cls = type(obj)
        return f"<{cls.__qualname__}>"

    if not truncate_values:
        return pretty_repr(obj)

    return _truncated_prepr(obj)


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
    :param suppress_none: If True, do not log parameters with None value.
    :param truncate_values: If True, do not truncate long values.
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
    :param suppress_none: If True, do not log parameters with None value.
    :param truncate_values: If True, do not truncate long values.
    """
    methods = []
    for container in args:
        methods.extend(_get_public_methods(container))
    with trace_calls(*methods, **kwargs):
        yield
