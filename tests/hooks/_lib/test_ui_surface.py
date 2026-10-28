from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.ui_surface import Surface, content_surface, may_be_tui, path_surface  # noqa: E402


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("src/components/Button.tsx", Surface.WEB),
        ("public/index.html", Surface.WEB),
        ("src/lib/theme.ts", Surface.WEB),
        ("lib/screens/home.dart", Surface.MOBILE),
        ("ios/App/SettingsView.swift", Surface.MOBILE),
        ("android/app/ui/Profile.kt", Surface.MOBILE),
        ("ui/main.qml", Surface.DESKTOP),
        ("App/MainWindow.xaml", Surface.DESKTOP),
        ("Base.lproj/Main.storyboard", Surface.DESKTOP),
        ("api/handlers.py", None),
        ("node_modules/pkg/index.css", None),
        ("src/Button.stories.tsx", None),
        ("types/global.d.ts", None),
    ],
)
def test_path_surface_classifies_each_platform(path, expected):
    # Arrange
    candidate = path

    # Act
    result = path_surface(candidate)

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    ("path", "text"),
    [
        ("app/screen.py", "from textual.app import App\n"),
        ("cli/view.py", "import curses\n"),
        ("cli/ui.js", "const blessed = require('blessed')\n"),
        ("cli/app.ts", "import { render } from 'ink'\n"),
        ("cmd/main.go", 'import tea "github.com/charmbracelet/bubbletea"\n'),
        ("src/main.rs", "use ratatui::prelude::*;\n"),
        ("src/main.c", "#include <ncurses.h>\n"),
    ],
)
def test_content_surface_finds_terminal_ui_imports(path, text):
    # Arrange
    source = text

    # Act
    result = content_surface(path, source)

    # Assert
    assert result == Surface.TUI


@pytest.mark.parametrize(
    ("path", "text"),
    [
        ("app/models.py", "import json\n"),
        ("tests/test_screen.py", "from textual.app import App\n"),
        ("cmd/view_test.go", 'import "github.com/charmbracelet/bubbletea"\n'),
        ("docs/notes.md", "import curses\n"),
    ],
)
def test_content_surface_ignores_tests_and_non_tui_sources(path, text):
    # Arrange
    source = text

    # Act
    result = content_surface(path, source)

    # Assert
    assert result is None


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("cli/app.py", True),
        ("dist/app.js", False),
        ("src/app.spec.ts", False),
        ("README.md", False),
    ],
)
def test_may_be_tui_limits_content_reads_to_shipped_sources(path, expected):
    # Arrange
    candidate = path

    # Act
    result = may_be_tui(candidate)

    # Assert
    assert result is expected
