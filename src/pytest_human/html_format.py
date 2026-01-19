"""HTML log file formatter for pytest-human."""

from __future__ import annotations

import html
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import jinja2
import pygments
import pygments.formatters
from pygments import lexers
from pygments.formatter import Formatter as PygmentsFormatter
from pygments.lexer import Lexer as PygmentsLexer

from pytest_human import repo
from pytest_human._code_style import _ReportCodeStyle
from pytest_human.log import (
    _LOCATION_TAG,
    _SPAN_END_TAG,
    _SPAN_START_TAG,
    _SYNTAX_HIGHLIGHT_TAG,
)


@dataclass
class _BlockData:
    """Internal structure representing an open collapsible block."""

    start_time: float
    id: str
    duration_id: str

    severity_max: int = 0


class HtmlRecordFormatter(logging.Formatter):
    """Formatter to convert log records into HTML fragments."""

    # The minimum log level that will be propagated to parent loggers
    MINIMUM_PROPAGATION_LEVEL = logging.ERROR
    DATE_FMT = "%H:%M:%S.%f"

    def __init__(
        self,
        code_formatter: PygmentsFormatter,
        code_lexer: PygmentsLexer,
        repo: repo.Repo,
        jinja_env: jinja2.Environment,
    ) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._block_stack: list[_BlockData] = []
        self._block_id_counter: int = 0
        self._code_formatter = code_formatter
        self._code_lexer = code_lexer
        self._repo = repo
        self._jinja_env = jinja_env

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as an HTML fragment."""
        # Check for special attributes set by our adapter
        with self._lock:
            if hasattr(record, _SPAN_START_TAG):
                return self._start_block(record)

            if hasattr(record, _SPAN_END_TAG):
                return self._end_block()

            return self._format_log_record(record)

    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:  # noqa: N802
        """Unimplemented override from base class, use local method _format_time instead."""
        raise NotImplementedError("formatTime is unimplemented, use _format_time instead.")

    def _format_time(self, record: logging.LogRecord) -> str:
        """Format the time of the log record."""
        timestamp = datetime.fromtimestamp(record.created)
        formatted = timestamp.strftime(self.DATE_FMT)
        with_ms = formatted[:-3]
        return html.escape(with_ms)

    def _get_file_in_repo(self, record: logging.LogRecord) -> tuple[str, int]:
        """Get the log record path relative to the git repo root, if possible."""
        path, lineno = self._get_file_lines(record)
        relative_path = self._repo.relative_to_repo(Path(path))
        return str(relative_path), lineno

    def _get_file_lines(self, record: logging.LogRecord) -> tuple[str, int]:
        """Get the start and end lines of the log record if available."""
        location = getattr(record, _LOCATION_TAG, {})
        line_no = location.get("lineno", record.lineno)
        path_name = location.get("pathname", record.pathname)

        return path_name, line_no

    def _get_source_link(self, record: logging.LogRecord) -> str:
        """Get the source of the log record as a link."""
        log_path, line_no = self._get_file_in_repo(record)
        full_location = f"{log_path}:{line_no}"
        file_location = f"{Path(log_path).name}:{line_no}"
        full_path, _ = self._get_file_lines(record)

        url = self._repo.create_github_url(Path(full_path), line_no)

        if url is None:
            return (
                f'<span class="source-text" title="{html.escape(full_location)}">'
                f"{html.escape(file_location)}</span>"
            )

        return (
            f'<a href="{html.escape(url)}"'
            f' class="source-link source-text" target="_blank" rel="noopener noreferrer"'
            f' title="{html.escape(full_location)}">'
            f"{html.escape(file_location)}</a>"
        )

    def _format_log_record(self, record: logging.LogRecord) -> str:
        timestamp = self._format_time(record)
        escaped_source_link = self._get_source_link(record)
        escaped_message = self._get_message_html(record)

        template = self._jinja_env.get_template("record.html")
        result = template.render(
            record=record,
            timestamp=html.escape(timestamp),
            escaped_source_link=escaped_source_link,
            escaped_message=escaped_message,
        )

        if record.levelno >= self.MINIMUM_PROPAGATION_LEVEL and self._block_stack:
            parent = self._block_stack[-1]
            parent.severity_max = max(parent.severity_max, record.levelno)

        return result

    def _get_message_html(self, record: logging.LogRecord) -> str:
        syntax_highlight = getattr(record, _SYNTAX_HIGHLIGHT_TAG, False)
        if syntax_highlight:
            return pygments.highlight(record.getMessage(), self._code_lexer, self._code_formatter)

        return html.escape(super().format(record))

    def _start_block(self, record: logging.LogRecord) -> str:
        self._block_id_counter += 1
        block_id = f"block_{self._block_id_counter}"
        duration_id = f"duration_{self._block_id_counter}"
        self._block_stack.append(
            _BlockData(
                start_time=time.monotonic(),
                id=block_id,
                duration_id=duration_id,
                severity_max=record.levelno,
            )
        )

        timestamp = self._format_time(record)
        escaped_source_link = self._get_source_link(record)
        escaped_msg = self._get_message_html(record)

        template = self._jinja_env.get_template("block_start.html")
        return template.render(
            record=record,
            block_id=block_id,
            duration_id=duration_id,
            timestamp=timestamp,
            escaped_source_link=escaped_source_link,
            escaped_msg=escaped_msg,
        )

    def _log_level_to_css_class(self, level: int) -> str:
        return f"log-level-{logging.getLevelName(level).lower()}"

    def _end_block(self) -> str:
        if not self._block_stack:
            return ""
        block = self._block_stack.pop()
        duration_ms = (time.monotonic() - block.start_time) * 1000

        parent = None
        if self._block_stack:
            parent = self._block_stack[-1]

        if parent and block.severity_max >= self.MINIMUM_PROPAGATION_LEVEL:
            parent.severity_max = max(parent.severity_max, block.severity_max)

        level_class = self._log_level_to_css_class(block.severity_max)

        template = self._jinja_env.get_template("block_end.html")
        return template.render(
            block_id=block.id,
            duration_id=block.duration_id,
            duration_ms=duration_ms,
            css_class=level_class,
        )

    def end_all_blocks(self) -> str:
        """End all open spans and return the HTML fragments."""
        result = ""
        with self._lock:
            while self._block_stack:
                result += self._end_block()
        return result


class HtmlFileFormatter(logging.Formatter):
    """Formats log records into a complete HTML document.

    This deviates a bit from the logging.Formatter by adding a format_header and format_footer
    methods that should be called at the start and end of the file.
    """

    def __init__(
        self, repo: repo.Repo, title: str = "Test Log", description: str | None = ""
    ) -> None:
        super().__init__()
        self._code_formatter = pygments.formatters.HtmlFormatter(
            style=_ReportCodeStyle, nowrap=True
        )
        self._code_lexer = lexers.get_lexer_by_name("python")
        self._title = title
        self._description = description
        self._repo = repo
        self._jinja_env = jinja2.Environment(
            loader=jinja2.PackageLoader("pytest_human", "templates"),
            autoescape=jinja2.select_autoescape(["html"]),
        )
        self._record_formatter = HtmlRecordFormatter(
            code_formatter=self._code_formatter,
            code_lexer=self._code_lexer,
            repo=self._repo,
            jinja_env=self._jinja_env,
        )

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as an HTML fragment."""
        return self._record_formatter.format(record)

    def format_header(self) -> str:
        """Format the header of the HTML document."""
        template = self._jinja_env.get_template("header.html")
        return template.render(
            title=self._title,
            description=self._description,
            code_style_defs=self._code_formatter.get_style_defs(".msg-cell"),
        )

    def format_footer(self) -> str:
        """Format the footer of the HTML document."""
        result = ""
        result += self._record_formatter.end_all_blocks()
        template = self._jinja_env.get_template("footer.html")
        result += template.render()
        return result
