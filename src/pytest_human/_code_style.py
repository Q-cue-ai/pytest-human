from typing import ClassVar

from pygments.style import Style
from pygments.token import (
    Comment,
    Error,
    Generic,
    Keyword,
    Name,
    Number,
    Operator,
    String,
    Token,
    Whitespace,
)


class _ReportCodeStyle(Style):
    """A Pygments style that matches the report color theme."""

    name = "report-code-style"

    BACKGROUND = "#ffffff"
    FOREGROUND = "#24292e"
    HIGHLIGHT = "#f0f2f5"

    PRIMARY_BLUE = "#1667b7"
    SECONDARY_BLUE = "#0366d6"

    MEDIUM_GRAY = "#586069"
    BORDER_GRAY = "#d1d5da"

    ERROR_RED = "#d73a49"

    STRING_TEAL = "#005c5c"
    NUMBER_PURPLE = "#6f42c1"

    default_style = ""

    # Transparent background
    background_color = None  # type: ignore

    highlight_color = HIGHLIGHT

    styles: ClassVar[dict] = {
        Token: FOREGROUND,
        Whitespace: "",
        Comment: "italic " + MEDIUM_GRAY,
        Comment.Single: "italic " + MEDIUM_GRAY,
        Comment.Preproc: "nobold " + PRIMARY_BLUE,
        Keyword: "bold " + SECONDARY_BLUE,
        Keyword.Constant: "bold " + PRIMARY_BLUE,
        Keyword.Declaration: "bold " + SECONDARY_BLUE,
        Keyword.Namespace: "bold " + PRIMARY_BLUE,
        Keyword.Type: "bold " + PRIMARY_BLUE,
        Operator: SECONDARY_BLUE,
        Operator.Word: "bold " + SECONDARY_BLUE,
        Name: FOREGROUND,
        Name.Class: "bold " + PRIMARY_BLUE,
        Name.Function: "bold " + PRIMARY_BLUE,
        Name.Builtin: SECONDARY_BLUE,
        Name.Variable: FOREGROUND,
        Name.Constant: PRIMARY_BLUE,
        Name.Tag: "bold " + SECONDARY_BLUE,
        Name.Attribute: FOREGROUND,
        Name.Decorator: "bold " + PRIMARY_BLUE,
        String: STRING_TEAL,
        String.Doc: "italic " + MEDIUM_GRAY,
        String.Escape: "bold " + NUMBER_PURPLE,
        Number: NUMBER_PURPLE,
        Generic.Heading: "bold " + PRIMARY_BLUE,
        Generic.Subheading: "bold " + SECONDARY_BLUE,
        Generic.Deleted: ERROR_RED,
        Generic.Inserted: STRING_TEAL,
        Generic.Error: "bold " + ERROR_RED,
        Generic.Emph: "italic",
        Generic.Strong: "bold",
        Generic.Prompt: MEDIUM_GRAY,
        Generic.Output: MEDIUM_GRAY,
        Generic.Traceback: ERROR_RED,
        Error: "bg:" + BORDER_GRAY + " " + ERROR_RED,
    }
