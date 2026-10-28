from __future__ import annotations

import re
from enum import Enum


class Surface(str, Enum):
    WEB = "web"
    MOBILE = "mobile"
    DESKTOP = "desktop"
    TUI = "tui"


WEB_SUFFIXES = (
    ".tsx",
    ".jsx",
    ".vue",
    ".svelte",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".html",
    ".htm",
)
MOBILE_SUFFIXES = (".dart",)
DESKTOP_SUFFIXES = (".qml", ".ui", ".xaml", ".axaml", ".glade", ".storyboard", ".xib")
TUI_SOURCE_SUFFIXES = (
    ".py",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".go",
    ".rs",
    ".c",
    ".h",
    ".cc",
    ".cpp",
)

NATIVE_UI_SOURCE = re.compile(
    r"(?:View|ViewController|Screen|Activity|Fragment|Composable)\.(?:swift|kt)$"
    r"|(^|/)ui/[^/]+\.(?:swift|kt)$"
)

THEME_OR_TOKEN_SOURCE = re.compile(
    r"(^|/)(theme|tokens?|palette|design-tokens|typography|colors?)\.[cm]?[jt]s$",
    re.IGNORECASE,
)

NOT_A_SHIPPED_SURFACE = re.compile(
    r"(^|/)(node_modules|dist|build|\.next|out|coverage|storybook-static)(/|$)"
    r"|(^|/)__(mocks|fixtures)__(/|$)"
    r"|\.stories\.[cm]?[jt]sx?$"
    r"|\.d\.ts$",
    re.IGNORECASE,
)

TEST_SOURCE = re.compile(
    r"(^|/)(tests?|__tests__|spec|testdata)(/|$)"
    r"|(^|/)test_[^/]*$"
    r"|[._-](test|spec)\.[^/]+$"
    r"|_test\.(go|py|rs)$",
    re.IGNORECASE,
)

TUI_IMPORT = re.compile(
    r"^\s*(?:from|import)\s+(?:textual|rich|curses|urwid|prompt_toolkit|blessed"
    r"|npyscreen|asciimatics|pytermgui)\b"
    r"|\brequire\(\s*['\"](?:blessed|blessed-contrib|ink|neo-blessed)['\"]\s*\)"
    r"|\bfrom\s+['\"](?:ink|blessed|neo-blessed)['\"]"
    r"|\"github\.com/(?:charmbracelet/(?:bubbletea|lipgloss|bubbles)"
    r"|rivo/tview|gdamore/tcell|jroimartin/gocui)[^\"]*\""
    r"|^\s*use\s+(?:ratatui|crossterm|cursive|termion)\b"
    r"|^\s*#\s*include\s*[<\"](?:n?curses|ncursesw/curses)\.h[>\"]",
    re.MULTILINE,
)


def path_surface(path: str) -> Surface | None:
    if NOT_A_SHIPPED_SURFACE.search(path):
        return None
    if path.endswith(WEB_SUFFIXES) or THEME_OR_TOKEN_SOURCE.search(path):
        return Surface.WEB
    if path.endswith(MOBILE_SUFFIXES) or NATIVE_UI_SOURCE.search(path):
        return Surface.MOBILE
    if path.endswith(DESKTOP_SUFFIXES):
        return Surface.DESKTOP
    return None


def may_be_tui(path: str) -> bool:
    return (
        path.endswith(TUI_SOURCE_SUFFIXES)
        and not NOT_A_SHIPPED_SURFACE.search(path)
        and not TEST_SOURCE.search(path)
    )


def content_surface(path: str, text: str) -> Surface | None:
    if may_be_tui(path) and TUI_IMPORT.search(text):
        return Surface.TUI
    return None
