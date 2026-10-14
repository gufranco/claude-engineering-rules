from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.guard_runner import Edit  # noqa: E402
from _lib.idempotency_detectors import applies_to, find  # noqa: E402

BLOCKED: list[tuple[str, str, str]] = [
    ("install.sh", 'mkdir "$HOME/.config/app"\n', "`mkdir -p`"),
    ("install.sh", "ln -s ~/dotfiles/zshrc ~/.zshrc\n", "`ln -sfn`"),
    ("setup.bash", "echo 'export EDITOR=vim' >> ~/.bashrc\n", "re-running appends"),
    (
        "main.tf",
        'resource "aws_s3_object" "a" {\n  etag = timestamp()\n}\n',
        "`timestamp()`",
    ),
    (
        "main.tf",
        'resource "aws_iam_user" "a" {\n  name = "u-${uuid()}"\n}\n',
        "`uuid()`",
    ),
    (
        "producer.ts",
        "const producer = kafka.producer({ idempotent: false });\n",
        "idempotent producer",
    ),
    ("producer.py", "conf = {'enable.idempotence': False}\n", "idempotent producer"),
]

ADVISORY: list[tuple[str, str, str]] = [
    ("zshrc.zsh", 'export PATH="$HOME/bin:$PATH"\n', "PATH"),
    (
        "main.tf",
        'resource "null_resource" "a" {\n  provisioner "local-exec" {\n    command = "make"\n  }\n}\n',
        "provisioner",
    ),
    ("main.tf", "lifecycle {\n  ignore_changes = all\n}\n", "ignore_changes"),
    (
        "queue.ts",
        "await queue.add('send', data, { jobId: key, removeOnComplete: true });\n",
        "removeOnComplete",
    ),
]

CLEAN: list[tuple[str, str]] = [
    ("install.sh", 'mkdir -p "$HOME/.config/app"\nln -sfn a b\n'),
    ("lock.sh", 'if mkdir "$LOCK_DIR" 2>/dev/null; then\n  run\nfi\n'),
    (
        "setup.bash",
        "grep -qxF 'export EDITOR=vim' ~/.bashrc || echo 'export EDITOR=vim' >> ~/.bashrc\n",
    ),
    ("zshrc.zsh", 'typeset -U path\nexport PATH="$HOME/bin:$PATH"\n'),
    (
        "paths.sh",
        'case ":$PATH:" in\n  *":$HOME/bin:"*) ;;\n  *) export PATH="$HOME/bin:$PATH" ;;\nesac\n',
    ),
    (
        "main.tf",
        'resource "time_static" "a" {}\noutput "t" { value = plantimestamp() }\n',
    ),
    ("notes.sh", "# mkdir build\n"),
]


def _edit(path: str, text: str) -> Edit:
    return Edit(path=f"/repo/{path}", text=text, full_file=True)


@pytest.mark.parametrize(("path", "text", "expected"), BLOCKED)
def test_blocks(path, text, expected):
    # Arrange
    edit = _edit(path, text)

    # Act
    hits = find(edit)

    # Assert
    assert [(hit.blocking, expected in hit.message) for hit in hits] == [
        (True, True)
    ], (path, hits)


@pytest.mark.parametrize(("path", "text", "expected"), ADVISORY)
def test_advises(path, text, expected):
    # Arrange
    edit = _edit(path, text)

    # Act
    hits = find(edit)

    # Assert
    assert [(hit.blocking, expected in hit.message) for hit in hits] == [
        (False, True)
    ], (path, hits)


@pytest.mark.parametrize(("path", "text"), CLEAN)
def test_allows(path, text):
    # Arrange
    edit = _edit(path, text)

    # Act
    hits = find(edit)

    # Assert
    assert hits == (), (path, hits)


def test_applies_to_dotfiles_scripts_and_terraform_only():
    # Arrange
    paths = (
        "/h/.zshrc",
        "/h/.bashrc",
        "/r/a.sh",
        "/r/a.tf",
        "/r/a.ts",
        "/r/a.md",
        "/r/tests/a.bats",
        "/r/a.test.ts",
    )

    # Act
    verdicts = tuple(applies_to(path) for path in paths)

    # Assert
    assert verdicts == (True, True, True, True, True, False, False, False)


def test_commented_out_kafka_setting_is_ignored():
    # Arrange
    edit = _edit("producer.ts", "// const p = kafka.producer({ idempotent: false });\n")

    # Act
    hits = find(edit)

    # Assert
    assert hits == ()
