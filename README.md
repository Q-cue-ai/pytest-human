# pytest-human

[![PyPI version](https://img.shields.io/pypi/v/pytest-human.svg)](https://pypi.org/project/pytest-human)
[![Python versions](https://img.shields.io/pypi/pyversions/pytest-human.svg)](https://pypi.org/project/pytest-human)
[![License](https://img.shields.io/pypi/l/pytest-human.svg)](https://github.com/Q-cue-ai/pytest-human/blob/main/LICENSE)

![logo](assets/logo-horizontal.svg)

A pytest plugin for generating beautiful, human-readable HTML reports for individual tests with collapsible nested logging spans and syntax highlighting. Inspired by Robot Framework and Playwright reports.

Unlike other pytest HTML report plugins, **pytest-human** creates a separate HTML log file for each test, aimed at diving into specific parts of the test that are relevant for debugging.

![Screenshot](assets/test_example.png)


## Installation

Install from PyPI:

```bash
pip install pytest-human
```

## Quick Start

### Basic Usage

1. Enable the plugin when running pytest:

```bash
pytest --enable-html-log --log-level DEBUG
```

2. Use the `human` fixture in your tests:

```python
from pytest_human.log import log_call

@log_call()
def insert_db(data):
    logging.info("executing query")
    return len(data)

def test_example(human):
    """This test demonstrates pytest-human logging."""
    human.info("Established test agent connection")

    with human.span_info("Generating sample data"):
        data = [1, 2, 3, 4, 5]
        human.info(f"Loaded sample data {data=} {len(data)=}", highlight=True)
        insert_db(data)

        with human.span_debug("Validating sample"):
            result = sum(data)
            human.debug(f"Sum {result=}", highlight=True)

    assert result == 15
```

3. Find your HTML logs:

At the start and end of individual tests you will see a similar line:

```console
Test test_single_stage_ui HTML log at file:///tmp/pytest-of-john.doe/pytest-2/session_logs/test_frobulator.html
```

You can control/command-click the path to open the file, or find it in the filesystem.

By the default the logs can be found in the session temp directory under the `session_logs` directory.


## Command Line Options

### Enable HTML Logging


```bash
# To enable HTML logging support and use this plugin, pass this flag

pytest --enable-html-log
```

### Log Location

Control where HTML logs are saved:

```bash
# Save in session directory (default) with test name
pytest --enable-html-log --html-log-dir session

# Save in individual test temporary directories as test.log
pytest --enable-html-log --html-log-dir test

# Save all test logs in a custom directory specified by the user.
# The directory should exist.
pytest --enable-html-log --html-log-dir custom --html-custom-dir /path/to/logs
```

### Log Level

Control the minimum log level:

```bash
# Use pytest's global log level.
# Opt to use this setting.
pytest --enable-html-log --log-level DEBUG

# Set log level for HTML logs specifically.
# This requires the root logger to be properly configured.
pytest --enable-html-log --html-log-level INFO

```

Setting the log level is critical, especially in the root log level as a lot of human's basic features are only avilable in `INFO`/`DEBUG` levels.
Setting the root log level is taken care of by pytest `--log-level` settings.

Available log levels: `TRACE`, `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

## Logger API

### Fixtures

Two fixtures are available (they're aliases):
- `human` - Supplies a logger to the test, all log sources are displayed using the test name. For helpers/fixtures prefer using `get_logger` instead
- `test_log` - Alternative synonym for `human` fixture

### Logging Methods

```python
def test_logging_methods(human):
    # Basic logging at different levels
    human.trace("Trace level message")
    human.debug("Debug level message")
    human.info("Info level message")
    human.warning("Warning level message")
    human.error("Error level message")
    human.critical("Critical level message")
    
    # Syntax highlighting for code
    code = """
    import numpy as np

    def bark(volume: float) -> bool:
        return volume > 0.5:
    """
    human.info(code, highlight=True)
```

### Collapsible Spans

Create nested, collapsible sections in your HTML logs:

```python
def test_spans(human):
    human.info("Starting complex operation")
    
    # Top-level span
    with human.span_info("Phase 1: Initialization"):
        human.debug("Initializing resources...")
        
        # Nested span
        with human.span_debug("Loading configuration"):
            human.trace("Reading config file")
            config = load_config()
            human.debug(f"Config loaded: {config}")
        
        human.info("Initialization complete")
    
    # Another top-level span
    with human.span_info("Phase 2: Processing"):
        human.debug("Processing data...")
        process_data()
    
    human.info("Operation completed")
```

Available span methods:
- `span_trace(message)` - TRACE level span
- `span_debug(message)` - DEBUG level span
- `span_info(message)` - INFO level span
- `span_warning(message)` - WARNING level span
- `span_error(message)` - ERROR level span
- `span_critical(message)` - CRITICAL level span

## Method Tracing

```python
import logging
import time
from pytest_human.log import log_call, get_logger

@log_call()
def save_login(login):
    log = get_logger(__name__)
    log.info("a log inside save_login")
    return update_db(login)

@log_call(log_level=logging.TRACE)
def update_db(login):
    log = get_logger(__name__)
    delay_time = 2
    log.info("delaying db update by 2 seconds")    
    time.sleep(delay_time)   
    return delay_time

def test_method_tracing(human):
    delay = save_login("hello")
    assert delay == 2
```

By adding the `@log_call` decorator, the method will be
automatically logged when called and finished executing. The call
will be placed in a nested span, which will also include all further logging inside the function scope.


## TRACE Logging

pytest-human adds a custom `TRACE` log level below `DEBUG` for ultra-detailed logging:

```python
def test_trace_logging(human):
    human.trace("Very detailed trace information")
```

Run with trace level:

```bash
pytest --enable-html-log --log-level trace
```


## HTML Report Features

The generated HTML reports include:

- **Header Section**:
  - Test name and description (from docstring)
  - Timestamp
  - Searchable log viewer

- **Log Table**:
  - Timestamp for each log entry
  - Log level with color coding
  - Source (logger name)
  - Message with syntax highlighting
  - Collapsible nested spans

- **Interactive Features**:
  - Click to expand/collapse spans
  - Color-coded severity levels
  - Automatic indentation for nested content
  - Duration tracking for spans


## Configuration

### Using Standard Python Logging

pytest-human integrates with Python's standard logging system. All logs from any logger will be captured:

```python
import logging

def test_standard_logging(human):
    # pytest-human logger
    human.info("Using human fixture")
    
    # Standard Python logger - also captured in HTML
    logger = logging.getLogger(__name__)
    logger.info("Using standard logger")
```

### Programmatic Access

Get the test logger programmatically:

```python
from pytest_human.log import get_logger

def test_programmatic_logger():
    logger = get_logger(__name__)
    logger.info("Custom logger")
```


## Development

### Running Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=pytest_human
```

### Building Documentation

```bash
mkdocs serve
```


## License

Distributed under the Apache Software License 2.0. See `LICENSE` for more information.


## Links

- **PyPI**: https://pypi.org/project/pytest-human
- **Repository**: https://github.com/Q-cue-ai/pytest-human
- **Issue Tracker**: https://github.com/Q-cue-ai/pytest-human/issues

