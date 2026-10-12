from __future__ import annotations

import os
import re
import shlex
import subprocess
from dataclasses import dataclass

from _lib.git_invocation import GLOBAL_OPTION, SHELL_WORD, strip_git_global_options

GIT_TIMEOUT_SECONDS = 20
MAX_DOCUMENT_BYTES = 512 * 1024
MAX_STAGED_FILES = 2000
COMMAND_START = r"(?:^|[;&|(`]|\$\(|\bthen\b|\bdo\b)\s*(?:[A-Za-z_]\w*=\S*\s+)*"
COMMIT_CALL = re.compile(
    COMMAND_START + r"git\s+commit(?![\w-])(?P<args>[^;&|\n]*)", re.M
)
COMMIT_WITH_OPTIONS = re.compile(
    COMMAND_START + rf"git(?P<options>(?:\s+{GLOBAL_OPTION})*)\s+commit(?![\w-])", re.M
)
DIRECTORY_OPTION = re.compile(rf"(?:^|\s)-C\s+(?P<directory>{SHELL_WORD})")
CHANGE_DIRECTORY = re.compile(
    rf"(?:^|&&|;|\|\|)\s*cd\s+(?P<directory>{SHELL_WORD})\s*(?=&&|;)"
)


class StagedScanError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CommitRequest:
    directory: str
    include_tracked: bool


@dataclass(frozen=True, slots=True)
class StagedDocument:
    path: str
    before: str
    after: str


@dataclass(frozen=True, slots=True)
class StagedPath:
    path: str
    previous: str


def _unquote(word: str) -> str:
    try:
        parts = shlex.split(word)
    except ValueError:
        return word
    return parts[0] if parts else word


def _stages_tracked_files(arguments: str) -> bool:
    try:
        words = shlex.split(arguments)
    except ValueError:
        words = arguments.split()
    return any(
        word == "--all"
        or (word.startswith("-") and not word.startswith("--") and "a" in word[1:])
        for word in words
    )


def _commit_directory(command: str, cwd: str) -> str:
    match = COMMIT_WITH_OPTIONS.search(command)
    end = match.end() if match else len(command)
    directory = cwd
    for change in CHANGE_DIRECTORY.finditer(command[:end]):
        directory = os.path.join(directory, _unquote(change.group("directory")))
    options = match.group("options") if match else ""
    for option in DIRECTORY_OPTION.finditer(options):
        directory = os.path.join(directory, _unquote(option.group("directory")))
    return os.path.normpath(directory)


def commit_request(command: str, cwd: str) -> CommitRequest | None:
    match = COMMIT_CALL.search(strip_git_global_options(command))
    if match is None:
        return None
    return CommitRequest(
        _commit_directory(command, cwd), _stages_tracked_files(match.group("args"))
    )


def _git(directory: str, *args: str, stdin: bytes = b"") -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=directory,
        input=stdin,
        capture_output=True,
        timeout=GIT_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise StagedScanError(f"git {args[0]} failed: {detail}")
    return completed.stdout


def _repository_root(directory: str) -> str | None:
    if not os.path.isdir(directory):
        return None
    try:
        return _git(directory, "rev-parse", "--show-toplevel").decode().strip()
    except StagedScanError:
        return None


def _has_head(root: str) -> bool:
    try:
        _git(root, "rev-parse", "--verify", "-q", "HEAD")
    except StagedScanError:
        return False
    return True


def _changed_paths(root: str, *scope: str) -> list[StagedPath]:
    fields = (
        _git(root, "diff", *scope, "--name-status", "-z", "-M", "--diff-filter=ACMR")
        .decode("utf-8", "surrogateescape")
        .split("\0")
    )
    changed: list[StagedPath] = []
    index = 0
    while index < len(fields) - 1:
        status = fields[index][:1]
        if status in ("R", "C"):
            changed.append(StagedPath(fields[index + 2], fields[index + 1]))
            index += 3
            continue
        changed.append(StagedPath(fields[index + 1], fields[index + 1]))
        index += 2
    return changed


def _decode(blob: bytes | None) -> str | None:
    if blob is None or len(blob) > MAX_DOCUMENT_BYTES:
        return None
    try:
        return blob.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _read_objects(root: str, specs: list[str]) -> list[bytes | None]:
    output = _git(
        root,
        "cat-file",
        "--batch",
        stdin="".join(f"{spec}\n" for spec in specs).encode(),
    )
    blobs: list[bytes | None] = []
    cursor = 0
    for _ in specs:
        header_end = output.index(b"\n", cursor)
        header = output[cursor:header_end].split()
        cursor = header_end + 1
        if len(header) != 3:
            blobs.append(None)
            continue
        size = int(header[2])
        blobs.append(output[cursor : cursor + size] if header[1] == b"blob" else None)
        cursor += size + 1
    return blobs


def _worktree_text(root: str, path: str) -> str | None:
    try:
        with open(os.path.join(root, path), "rb") as handle:
            return _decode(handle.read(MAX_DOCUMENT_BYTES + 1))
    except OSError:
        return None


def _documents(
    root: str, paths: list[StagedPath], from_worktree: bool
) -> list[StagedDocument]:
    head = _has_head(root)
    befores = (
        _read_objects(root, [f"HEAD:{entry.previous}" for entry in paths])
        if head
        else []
    )
    afters = (
        []
        if from_worktree
        else _read_objects(root, [f":{entry.path}" for entry in paths])
    )
    documents: list[StagedDocument] = []
    for index, entry in enumerate(paths):
        after = (
            _worktree_text(root, entry.path)
            if from_worktree
            else _decode(afters[index])
        )
        if after is None:
            continue
        before = _decode(befores[index]) if head else ""
        documents.append(StagedDocument(entry.path, before or "", after))
    return documents


def staged_documents(request: CommitRequest) -> list[StagedDocument]:
    root = _repository_root(request.directory)
    if root is None:
        return []
    staged = [
        entry for entry in _changed_paths(root, "--cached") if "\n" not in entry.path
    ]
    documents = _documents(root, staged[:MAX_STAGED_FILES], from_worktree=False)
    if not request.include_tracked:
        return documents
    tracked = [entry for entry in _changed_paths(root) if "\n" not in entry.path]
    worktree = _documents(root, tracked[:MAX_STAGED_FILES], from_worktree=True)
    replaced = {document.path for document in worktree}
    return [
        document for document in documents if document.path not in replaced
    ] + worktree
