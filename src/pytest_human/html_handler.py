"""HTML logging handler for pytest-human."""

from __future__ import annotations

import logging
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import Optional, TextIO

from pytest_human.html_format import HtmlFileFormatter
from pytest_human.log import _SPAN_END_TAG
from pytest_human.repo import Repo


class _SpanEndFilter(logging.Filter):
    """A logging filter that blocks log records marking the end of a span."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out span end log records.

        These can spam the log with non-HTML log handlers.
        """
        return not getattr(record, _SPAN_END_TAG, False)


class HtmlFileHandler(logging.Handler):
    """A logging handler that streams log records to a self-contained, collapsible HTML file.

    Because of the streaming nature, we have an issue with updating information
    we don't know in advance, such as duration and severity of a block.
    We use javascript blocks to update these fields retroactively.
    """

    def __init__(
        self,
        filename: str,
        repo: Repo,
        title: str = "Test Log",
        description: str | None = "",
    ) -> None:
        super().__init__()
        self.path = Path(filename)
        self._file: TextIO = self.path.open("w", encoding="utf-8")
        self._formatter = HtmlFileFormatter(title=title, description=description, repo=repo)
        super().setFormatter(self._formatter)
        self._file.write(self._formatter.format_header())

    def setFormatter(self, fmt: logging.Formatter | None) -> None:  # noqa: N802
        """HtmlFileHandler does not support changing the formatter."""
        raise NotImplementedError("HtmlFileHandler does not support changing the formatter.")

    def __enter__(self) -> HtmlFileHandler:
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self.close()

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.acquire()
        try:
            yield
        finally:
            self.release()

    def emit(self, record: logging.LogRecord) -> None:
        """Write a log record to the HTML file."""
        html = self._formatter.format(record)
        with self._locked():
            self._file.write(html)
            self._file.flush()

    def flush(self) -> None:
        """Flush the HTML file."""
        with self._locked():
            self._file.flush()

    def close(self) -> None:
        """Finalize and close the HTML file."""
        with self._locked():
            if not self._file or self._file.closed:
                super().close()
                return

            if hasattr(self, "_formatter"):
                self._file.write(self._formatter.format_footer())
            self._file.close()
            super().close()

    def relocate(self, new_path: str | Path) -> None:
        """Move the log file to a new location."""
        assert not self._file.closed, "Cannot relocate a closed HtmlFileHandler."
        with self._locked():
            self._file.close()
            new_path = Path(new_path)
            shutil.move(self.path, new_path)
            self.path = new_path
            self._file = self.path.open("a", encoding="utf-8")


class HtmlHandlerContext:
    """Context manager factory for HtmlFileHandler."""

    html_handler: HtmlFileHandler
    _filtered_handlers: list[logging.Handler]
    _SPAN_END_FILTER = _SpanEndFilter()

    def __init__(
        self,
        filename: Path,
        *,
        repo: Repo,
        title: str = "Test Log",
        description: str | None = "",
        level: int = logging.DEBUG,
    ) -> None:
        self._filtered_handlers = []
        self.html_handler = HtmlFileHandler(
            filename.as_posix(), title=title, description=description, repo=repo
        )
        self.html_handler.setLevel(level)

    def __enter__(self) -> HtmlFileHandler:
        root_logger = logging.getLogger()
        root_logger.addHandler(self.html_handler)

        for handler in root_logger.handlers:
            if handler is not self.html_handler:
                handler.addFilter(self._SPAN_END_FILTER)
                self._filtered_handlers.append(handler)

        return self.html_handler

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        root_logger = logging.getLogger()
        root_logger.removeHandler(self.html_handler)
        self.html_handler.close()

        for handler in self._filtered_handlers:
            handler.removeFilter(self._SPAN_END_FILTER)
