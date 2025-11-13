"""HTML log file formatter for pytest-human."""

from __future__ import annotations

import html
import logging
import shutil
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Optional, TextIO

import pygments
import pygments.formatters
from pygments import lexers
from pygments.formatter import Formatter as PygmentsFormatter
from pygments.lexer import Lexer as PygmentsLexer

from pytest_human._code_style import _ReportCodeStyle
from pytest_human.log import _SPAN_END_TAG, _SPAN_START_TAG, _SYNTAX_HIGHLIGHT_TAG


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

    def __init__(self, code_formatter: PygmentsFormatter, code_lexer: PygmentsLexer) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._block_stack: list[_BlockData] = []
        self._block_id_counter: int = 0
        self._code_formatter = code_formatter
        self._code_lexer = code_lexer

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
        return with_ms

    def _format_log_record(self, record: logging.LogRecord) -> str:
        timestamp = self._format_time(record)
        escaped_source = html.escape(record.name)
        escaped_message = self._get_message_html(record)

        result = f"""
        <tr class="log-level-{record.levelname.lower()}">
            <td></td>
            <td class="time-cell">{html.escape(timestamp)}</td>
            <td class="level-cell">{html.escape(record.levelname)}</td>
            <td class="source-cell">{escaped_source}</td>
            <td colspan="2" class="msg-cell">{escaped_message}</td>
        </tr>
        """
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
        escaped_source = html.escape(record.name)
        escaped_msg = self._get_message_html(record)

        return f"""
        <tr id="header_{block_id}" class="log-level-{record.levelname.lower()}">
            <td class="toggle-cell" onclick="toggle('{block_id}')">
                <button id="toggle-{block_id}">[+]</button>
            </td>
            <td class="time-cell">{timestamp}</td>
            <td class="level-cell">{record.levelname}</td>
            <td class="source-cell" title="{escaped_source}">{escaped_source}</td>
            <td class="msg-cell">{escaped_msg}</td>
            <td class="duration-cell" id="{duration_id}">...</td>
        </tr>
        <tr id="{block_id}" class="nested-block" style="display: none;">
            <td colspan="6">
                <table class="log-table">
        """

    def _log_level_to_css_class(self, level: int) -> str:
        return f"log-level-{logging.getLevelName(level).lower()}"

    def _end_block(self) -> str:
        if not self._block_stack:
            return ""
        block = self._block_stack.pop()
        duration_ms = (time.monotonic() - block.start_time) * 1000

        result = "</table></td></tr>"
        result += (
            f"<script>finalizeSpan('{block.id}', '{block.duration_id}', {duration_ms});</script>"
        )

        parent = None
        if self._block_stack:
            parent = self._block_stack[-1]

        if parent and block.severity_max >= self.MINIMUM_PROPAGATION_LEVEL:
            parent.severity_max = max(parent.severity_max, block.severity_max)

        css_class = self._log_level_to_css_class(block.severity_max)
        result += f"<script>setSpanSeverity('{block.id}', '{css_class}');</script>"
        return result

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

    def __init__(self, title: str = "Test Log", description: str | None = "") -> None:
        super().__init__()
        self._code_formatter = pygments.formatters.HtmlFormatter(
            style=_ReportCodeStyle, nowrap=True
        )
        self._code_lexer = lexers.get_lexer_by_name("python")
        self._title = title
        self._description = description
        self._record_formatter = HtmlRecordFormatter(
            code_formatter=self._code_formatter, code_lexer=self._code_lexer
        )

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as an HTML fragment."""
        return self._record_formatter.format(record)

    def format_header(self) -> str:
        """Format the header of the HTML document."""
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>{html.escape(self._title)}</title>
            <style>{self._get_css()}</style>
            <style>{self._code_formatter.get_style_defs(".msg-cell")}</style>
            <script>{self._get_javascript()}</script>
        </head>
        <body>
            <div class="report-header">
                <div class="header-main">
                    <h1>{html.escape(self._title)}</h1>
                    {self._format_description_if_present()}
                </div>
                <div class="search-container">
                    <svg class="search-icon" viewBox="0 0 512 512">
                        <path d="M221.09 64a157.09 157.09 0 10157.09 157.09A157.1 157.1 0 00221.09 64z"
                          fill="none" stroke="currentColor" stroke-miterlimit="10" stroke-width="32"/>
                        <path fill="none" stroke="currentColor" stroke-linecap="round" stroke-miterlimit="10"
                          stroke-width="32" d="M338.29 338.29L448 448"/>
                    </svg>
                    <input type="text" id="search-input"
                           placeholder="Press / to search (regex)"
                           oninput="searchLogs()"
                           onfocus="this.select()">
                    <button id="clear-search-btn" onclick="clearSearchText()" title="Clear search">
                        <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor">
                           <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.75.75 0 1 1 1.06 1.06L9.06 8l3.22 3.22a.75.75 0 1 1-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 0 1-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"></path>
                        </svg>
                    </button>
                    <span id="search-counter">0 / 0</span>
                    <div class="search-controls">
                        <button onclick="prevResult()" title="Previous result" id="search-prev">
                            <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor">
                                <path d="M3.22 10.72a.75.75 0 0 0 1.06 0L8 7.06l3.72 3.66a.75.75 0 1 0 1.06-1.06l-4.25-4.15a.75.75 0 0 0-1.06 0L3.22 9.66a.75.75 0 0 0 0 1.06Z">
                                </path>
                            </svg>
                        </button>
                        <button onclick="nextResult()" title="Next result" id="search-next">
                            <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor">
                                <path d="M12.78 5.28a.75.75 0 0 0-1.06 0L8 8.94l-3.72-3.66a.75.75 0 0 0-1.06 1.06l4.25 4.15a.75.75 0 0 0 1.06 0l4.25-4.15a.75.75 0 0 0 0-1.06Z">
                                </path>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
            <div class="log-container">
                <table class="log-table">
        """  # noqa: E501

    def format_footer(self) -> str:
        """Format the footer of the HTML document."""
        result = ""
        result += self._record_formatter.end_all_blocks()
        result += "</table></div>"
        result += "</body></html>"
        return result

    def _format_description_if_present(self) -> str:
        if self._description:
            return f'<p class="description">{html.escape(self._description)}</p>\n'
        return ""

    @staticmethod
    def _get_css() -> str:
        return r"""
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                  Roboto, Helvetica, Arial, sans-serif;
                background-color: #f0f2f5;
                color: #24292e;
                margin: 0;
                padding: 0;
                font-size: 14px;
            }
            .report-header {
                background-color: #1667b7;
                color: #f6f8fa;
                padding: 16px 24px;
                border-bottom: 1px solid #d1d5da;
                position: sticky;
                top: 0;
                z-index: 10;
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
            }
            .header-main {
                flex-grow: 1;
            }
            .report-header h1 {
                margin: 0;
                font-size: 22px;
                font-weight: 600;
            }
            .report-header p {
                margin: 4px 0 0;
                font-size: 13px;
                opacity: 0.8;
            }

            .search-container {
                display: flex;
                align-items: center;
                background-color: #ffffff;
                border: 1px solid #d0d7de;
                border-radius: 30px;
                padding: 5px 12px;
                min-width: 380px;
                transition: all 0.2s ease-in-out;
                box-shadow: 0 1px 2px rgba(27,31,35,0.075);
            }
            .search-container:focus-within {
                border-color: #0969da;
                box-shadow: 0 0 0 3px rgba(9, 105, 218, 0.3);
            }
            .search-icon {
                width: 18px;
                height: 18px;
                flex-shrink: 0;
                color: #57606a;
                margin-right: 8px;
            }
            #search-input {
                flex-grow: 1;
                border: none;
                outline: none;
                background-color: transparent;
                color: #24292e;
                font-size: 14px;
                padding: 4px;
                margin-right: 8px;
            }
            #search-input::placeholder {
                color: #57606a;
            }
            #search-input.search-error {
                color: #e14b4b;
            }
            .search-controls {
                display: flex;
                align-items: center;
                margin-left: 8px;
            }
            .search-controls button {
                display: flex;
                align-items: center;
                justify-content: center;
                background-color: #f6f8fa;
                border: 1px solid #d0d7de;
                color: #57606a;
                width: 24px;
                height: 24px;
                border-radius: 6px;
                cursor: pointer;
                margin: 0 2px;
                padding: 0;
                transition: background-color 0.2s;
            }
            .search-controls button:hover {
                background-color: #eef1f4;
            }
            #clear-search-btn {
                display: flex;
                visibility: hidden;
                align-items: center;
                justify-content: center;
                background: transparent;
                border: none;
                color: #57606a;
                width: 24px;
                height: 24px;
                border-radius: 50%;
                cursor: pointer;
                padding: 0;
                margin: 0 4px;
                flex-shrink: 0;
            }
            #clear-search-btn:hover {
                background-color: #eef1f4;
            }
            #search-counter {
               font-size: 13px;
               font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                Roboto, Helvetica, Arial, sans-serif;
               color: #57606a;
               padding-left: 10px;
               margin-left: 8px;
               border-left: 1px solid #d8dee4;
               white-space: nowrap;
               line-height: 1;
               min-width: 55px;
               text-align: center;
            }

            .highlight {
                background-color: yellow;
                color: black;
                white-space: nowrap;
            }

            .highlight.highlight-start {
                border-top-left-radius: 2px;
                border-bottom-left-radius: 2px;
                padding-left: 1px;
            }

            .highlight.highlight-end {
                border-top-right-radius: 2px;
                border-bottom-right-radius: 2px;
                padding-right: 1px;
            }

            .highlight.active {
                background-color: orange;
            }

            .log-container {
                margin: 20px;
                border: 1px solid #d1d5da;
                background-color: #fff;
                box-shadow: 0 1px 5px rgba(27,31,35,0.08);
                border-radius: 6px;
                overflow: hidden;
            }
            .log-table {
                width: 100%;
                border-collapse: collapse;
                table-layout: fixed;
            }
            .log-table td {
                padding: 8px 12px;
                border-bottom: 1px solid #e1e4e8;
                text-align: left;
                vertical-align: top;
                font-size: 13px;
            }
            .log-table td:nth-child(1) { width: 25px; }   /* Toggle */
            .log-table td:nth-child(2) { width: 90px; }   /* Timestamp */
            .log-table td:nth-child(3) { width: 80px; }   /* Level */
            .log-table td:nth-child(4) { width: 220px; }  /* Source */
            .log-table td:nth-child(6) { width: 80px; text-align: right; } /* Duration */

            .log-table tr:last-child td { border-bottom: none; }

            .time-cell {
                font-variant-numeric: tabular-nums;
            }

            .toggle-cell {
                cursor: pointer;
                user-select: none;
                font-weight: bold;
                color: #0366d6;
                font-size: 16px;
            }

            .toggle-cell button {
                all: unset;
                cursor: pointer;
                outline: revert;
                outline-offset: 3px;
            }

            .source-cell {
                color: #586069;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }

            .msg-cell {
                word-break: break-all;
                font-family: Consolas, "SFMono-Regular", Menlo, Monaco,
                    "Liberation Mono", "Courier New", monospace;
                white-space: pre-wrap;
            }
            .nested-block td {
                padding-left: 30px;
                border-left: 2px solid #f6f8fa;
            }

            .log-level-trace td:nth-child(3) { color: #838383; }
            .log-level-debug td:nth-child(3) { color: #0366d6; }
            .log-level-info { /* Default text color */ }
            .log-level-warning { background-color: #fffbdd; }
            .log-level-warning td:nth-child(3) { font-weight: 600; color: #5c4000; }
            .log-level-error { background-color: #ffeef0; font-weight: 600; }
            .log-level-error td:nth-child(3) { font-weight: 600; color: #d73a49; }
            .log-level-critical { background-color: pink; color: #000000; font-weight: 600; }
        """

    @staticmethod
    def _get_javascript() -> str:
        return r"""
                let searchResults = [];
                let currentResultIndex = -1;

                document.addEventListener('keydown', function (event) {
                    const searchInput = document.getElementById('search-input');
                    if (event.key === '/') {
                        event.preventDefault();
                        searchInput.focus();
                    } else if (event.key === 'Escape') {
                        searchInput.blur();
                    } else if (event.key === 'Enter' && document.activeElement === searchInput) {
                        event.preventDefault();
                        if (event.shiftKey) {
                            prevResult();
                        } else {
                            nextResult();
                        }
                    }
                });

                function removeHighlights(rootElement) {
                    const highlights = rootElement.querySelectorAll('.highlight');
                    for (let i = highlights.length - 1; i >= 0; i--) {
                        const highlight = highlights[i];
                        const parent = highlight.parentNode;
                        while (highlight.firstChild) {
                            parent.insertBefore(highlight.firstChild, highlight);
                        }
                        parent.removeChild(highlight);
                        parent.normalize();
                    }
                }

                function getTextNodes(rootElement) {
                    const walker = document.createTreeWalker(rootElement, NodeFilter.SHOW_TEXT, null, false);
                    const textNodes = [];
                    let currentNode;
                    while (currentNode = walker.nextNode()) {
                        const isSearchableCell = currentNode.parentNode.closest('td.msg-cell, td.source-cell, td.level-cell, td.time-cell');
                        if (currentNode.nodeValue.length > 0 && isSearchableCell) {
                            textNodes.push(currentNode);
                        }
                    }

                    return textNodes;
                }

                function runSearchRegex(query, fullText) {
                    // Replace spaces with \s to handle all whitespace types (spaces, &nbsp;, etc.)
                    const finalPattern = query.replace(/ /g, '\\s');
                    const regex = new RegExp(finalPattern, 'gi');

                    let match;
                    const matches = [];
                    while ((match = regex.exec(fullText)) !== null) {
                        if (match[0].length === 0) continue;
                        matches.push({
                            start: match.index,
                            end: match.index + match[0].length,
                        });
                    }

                    return matches;
                }

                function searchLogs() {
                    clearSearchState();
                    const searchInput = document.getElementById('search-input');
                    const query = searchInput.value;

                    if (query.length > 0) {
                        document.getElementById('clear-search-btn').style.visibility = 'visible';
                    } else {
                        document.getElementById('clear-search-btn').style.visibility = 'hidden';
                    }

                    if (query.length < 2) {
                        updateSearchCounter();
                        return;
                    }

                    try {
                        const logContainer = document.querySelector('.log-container');
                        const textNodes = getTextNodes(logContainer);
                        const fullText = textNodes.map(node => node.nodeValue).join('');
                        const matches = runSearchRegex(query, fullText);

                        searchResults = highlightMatches(matches, textNodes);

                        if (searchResults.length > 0) {
                            currentResultIndex = 0;
                            scrollToResult(searchResults[0]);
                        }
                        updateSearchCounter();
                    }
                    catch (e) {
                        console.error("Search Error:", e);
                        searchInput.classList.add('search-error');
                    } finally {
                        updateSearchCounter();
                    }
                }

              function clearSearchText() {
                    const searchInput = document.getElementById('search-input');
                    const clearButton = document.getElementById('clear-search-btn');
                    searchInput.value = '';
                    clearButton.style.display = 'none';
                    clearSearchState();
                    updateSearchCounter();
                    searchInput.focus();
                }

                function clearSearchState() {
                    document.getElementById('search-input').classList.remove('search-error');
                    searchResults = [];
                    currentResultIndex = -1;
                    const logContainer = document.querySelector('.log-container');
                    removeHighlights(logContainer);
                }

                function highlightMatches(matches, textNodes) {
                    let textOffset = 0;
                    const nodePositions = textNodes.map(node => {
                        const start = textOffset;
                        textOffset += node.nodeValue.length;
                        return { node, start, end: textOffset };
                    });

                    // Process matches in reverse to avoid DOM modification issues
                    for (let i = matches.length - 1; i >= 0; i--) {
                        const currentMatch = matches[i];
                        const affectedNodes = nodePositions.filter(pos =>
                            pos.start < currentMatch.end && pos.end > currentMatch.start
                        );

                        const matchFragments = [];

                        affectedNodes.forEach((pos, index) => {
                            const node = pos.node;
                            const parent = node.parentNode;
                            const highlightStart = Math.max(0, currentMatch.start - pos.start);
                            const highlightEnd = Math.min(node.nodeValue.length, currentMatch.end - pos.start);

                            if (highlightStart >= highlightEnd) return;

                            const middlePart = node.splitText(highlightStart);
                            middlePart.splitText(highlightEnd - highlightStart);

                            const highlight = document.createElement('span');
                            highlight.className = 'highlight';
                            highlight.dataset.matchId = i; // Group fragments of the same match
                            highlight.appendChild(middlePart.cloneNode(true));
                            parent.replaceChild(highlight, middlePart);

                            if (index === 0) {
                                highlight.classList.add('highlight-start');
                            }
                            if (index === affectedNodes.length - 1) {
                                highlight.classList.add('highlight-end');
                            }
                            matchFragments.unshift(highlight);
                        });

                        if (matchFragments.length > 0) {
                            searchResults.unshift(matchFragments[0]);
                        }
                    }
                    return searchResults;
                }

                function updateSearchCounter() {
                    const counter = document.getElementById('search-counter');
                    if (searchResults.length > 0) {
                        counter.textContent = `${currentResultIndex + 1} / ${searchResults.length}`;
                    } else if (document.getElementById('search-input').value.length >= 2) {
                        counter.textContent = `0 / 0`;
                    } else {
                        counter.textContent = '';
                    }
                }

                function expandParents(element) {
                    let current = element;
                    while (current && current !== document.body) {
                        if (current.classList.contains('nested-block') && current.style.display === 'none') {
                            const header = document.getElementById('header_' + current.id);
                            if (header) {
                                const toggleButton = header.querySelector('.toggle-cell');
                                if (toggleButton) {
                                    toggle(current.id);
                                }
                            }
                        }
                        current = current.parentElement;
                    }
                }

                function removeActiveHighlights() {
                    const previouslyActive = document.querySelectorAll('.highlight.active');
                    previouslyActive.forEach(el => el.classList.remove('active'));
                }

                function scrollToResult(element) {
                    expandParents(element);
                    removeActiveHighlights();

                    const matchId = element.dataset.matchId;
                    if (matchId) {
                        const allFragmentsForMatch = document.querySelectorAll(`.highlight[data-match-id='${matchId}']`);
                        allFragmentsForMatch.forEach(el => el.classList.add('active'));
                    }

                    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    updateSearchCounter();
                }

                function nextResult() {
                    if (searchResults.length > 0) {
                        currentResultIndex = (currentResultIndex + 1) % searchResults.length;
                        scrollToResult(searchResults[currentResultIndex]);
                    }
                }

                function prevResult() {
                    if (searchResults.length > 0) {
                        currentResultIndex = (currentResultIndex - 1 + searchResults.length) % searchResults.length;
                        scrollToResult(searchResults[currentResultIndex]);
                    }
                }

                function toggle(id) {
                    const e = document.getElementById(id);
                    const t = document.getElementById('toggle-' + id);
                    if (e.style.display === 'none') {
                        e.style.display = 'table-row';
                        // endash for width consistency
                        t.textContent = '[–]';
                    } else {
                        e.style.display = 'none';
                        t.textContent = '[+]';
                    }
                }

                function formatDuration(ms) {
                    if (ms < 1000) {
                        return `${Math.round(ms)} ms`;
                    }
                    const seconds = ms / 1000;
                    if (seconds < 60) {
                        return `${seconds.toFixed(1)} s`;
                    }
                    const minutes = seconds / 60;
                    if (minutes < 60) {
                        return `${minutes.toFixed(1)} m`;
                    }
                    const hours = minutes / 60;
                    return `${hours.toFixed(1)} h`;
                }

                function finalizeSpan(blockId, durationId, durationMs) {
                    const durationCell = document.getElementById(durationId);
                    if (durationCell) {
                        durationCell.textContent = formatDuration(durationMs);
                    }

                    const contentRow = document.getElementById(blockId);
                    if (!contentRow) return;

                    const innerTable = contentRow.querySelector('table.log-table');
                    if (innerTable && innerTable.rows.length === 0) {
                        const headerRow = contentRow.previousElementSibling;
                        if (headerRow) {
                            const toggleCell = headerRow.querySelector('.toggle-cell');
                            if (toggleCell) {
                                toggleCell.style.visibility = 'hidden';
                                toggleCell.style.cursor = 'default';
                            }
                        }
                    }
                }

                function setSpanSeverity(blockId, cssClass) {
                    const headerRow = document.getElementById('header_' + blockId);
                    if (!headerRow) return;
                    const classesToRemove = Array.from(headerRow.classList).filter(c => c.startsWith('log-level-'));
                    for (const c of classesToRemove) {
                        headerRow.classList.remove(c);
                    }
                    headerRow.classList.add(cssClass);
                }
        """  # noqa: E501, RUF001


class HtmlFileHandler(logging.Handler):
    """A logging handler that streams log records to a self-contained, collapsible HTML file.

    Because of the streaming nature, we have an issue with updating information
    we don't know in advance, such as duration and severity of a block.
    We use javascript blocks to update these fields retroactively.
    """

    def __init__(
        self, filename: str, title: str = "Test Log", description: str | None = ""
    ) -> None:
        super().__init__()
        self.path = Path(filename)
        self._file: TextIO = self.path.open("w", encoding="utf-8")
        self._formatter = HtmlFileFormatter(title=title, description=description)
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
            if self._file and not self._file.closed:
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
