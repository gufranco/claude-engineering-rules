"""Tests for `hooks/notify-webhook.py`.


Observable behavior:
- Exits 0 silently when `CLAUDE_NOTIFY_WEBHOOK` is unset.
- POSTs the notification payload when the env var is set.
- Network errors do not propagate (exit 0 always).
- Bypass via env or file registry skips the POST.
"""

from __future__ import annotations

import http.server
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / "hooks" / "notify-webhook.py"
sys.path.insert(0, str(ROOT / "hooks"))

from _lib.bypass_writer import set_bypass  # noqa: E402

_TESTS_DIR = ROOT / "tests"
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
from _helpers.cov_env import apply_coverage_env  # noqa: E402


class _CapturingHandler(http.server.BaseHTTPRequestHandler):
    posts: list[bytes] = []

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        self.posts.append(self.rfile.read(length))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *_args: object) -> None:
        pass


@pytest.fixture()
def webhook() -> tuple[str, list[bytes]]:
    _CapturingHandler.posts = []
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = http.server.HTTPServer(("127.0.0.1", port), _CapturingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/hook", _CapturingHandler.posts
    finally:
        server.shutdown()
        server.server_close()


def _run(env: dict) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.update(env)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input="",
        capture_output=True,
        text=True,
        env=apply_coverage_env(merged),
        timeout=5,
    )


def test_exits_silently_when_webhook_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.delenv("CLAUDE_NOTIFY_WEBHOOK", raising=False)
    # Act
    result = _run({"CLAUDE_NOTIFY_WEBHOOK": ""})
    # Assert
    assert result.returncode == 0
    assert result.stdout == ""


def test_posts_payload_when_webhook_set(webhook: tuple[str, list[bytes]]) -> None:
    # Arrange
    url, posts = webhook
    # Act
    result = _run({"CLAUDE_NOTIFY_WEBHOOK": url})
    # Assert
    assert result.returncode == 0
    assert len(posts) == 1
    assert b"Claude Code" in posts[0]
    assert b"Response complete" in posts[0]


def test_network_failure_swallowed() -> None:
    # Arrange
    # Act
    result = _run({"CLAUDE_NOTIFY_WEBHOOK": "http://127.0.0.1:1/never-listens"})
    # Assert
    assert result.returncode == 0


def test_env_disable_suppresses_post(webhook: tuple[str, list[bytes]]) -> None:
    # Arrange
    url, posts = webhook
    # Act
    result = _run({"CLAUDE_NOTIFY_WEBHOOK": url, "NOTIFY_WEBHOOK_DISABLE": "1"})
    # Assert
    assert result.returncode == 0
    assert posts == []


def test_file_bypass_suppresses_post(
    webhook: tuple[str, list[bytes]], tmp_path: Path
) -> None:
    # Arrange
    url, posts = webhook
    state = tmp_path / "state.json"
    set_bypass("notify-webhook", ttl_seconds=120, state_path=state)
    # Act
    result = _run({"CLAUDE_NOTIFY_WEBHOOK": url, "CLAUDE_BYPASS_STATE": str(state)})
    # Assert
    assert result.returncode == 0
    assert posts == []
