from __future__ import annotations

import re
from collections.abc import Sequence
from itertools import takewhile

from _lib.guard_runner import Finding

NEWEST_LTS = "ubuntu-26.04"
FIRST_PARTY_OWNERS = frozenset({"actions", "github"})
RELEASE_TRIGGERS = frozenset({"workflow_run", "release", "repository_dispatch"})
TAG_FILTERS = frozenset({"tags", "tags-ignore"})

WORKFLOW_PATH = re.compile(r"(?:^|/)\.github/workflows/[^/]+\.ya?ml$")
TAP_PATH = re.compile(r"(?:^|/)homebrew-[^/]+/\.github/workflows/")
MACOS_ONLY_TOOL = re.compile(
    r"Homebrew/actions/setup-homebrew@|maxim-lobanov/setup-xcode@"
    r"|\b(?:brew|xcodebuild|xcrun|xcode-select|codesign|notarytool|hdiutil"
    r"|diskutil|osascript|pkgbuild|productbuild|launchctl|plutil|sw_vers)\b"
)
RUNS_ON = re.compile(r"^\s*runs-on:\s*(?P<value>.+?)\s*(?:#.*)?$")
UBUNTU_LTS = re.compile(r"\bubuntu-(?P<year>\d{2})\.04\b")
USES = re.compile(r"^\s*(?:-\s+)?uses:\s*['\"]?(?P<ref>[^'\"\s#]+)")
PINNED_SHA = re.compile(r"@[0-9a-f]{40}$")
NAME_KEY = re.compile(r"^\s*(?:-\s+)?(?:name|id|if):")
FORBIDDEN_TOOL = re.compile(
    r"(?:^|[\s;&|(])(?:npm|npx|yarn)\s+\S|(?<!uv )\bpip3?\s+install\b"
)
ON_KEY = re.compile(r"^['\"]?on['\"]?:\s*(?P<inline>[^#]*?)\s*(?:#.*)?$")
YAML_KEY = re.compile(r"^(?P<indent>[ \t]*)(?P<name>[A-Za-z_][\w-]*)\s*:")
TRIGGER_NAME = re.compile(r"[A-Za-z_][\w-]*")
CANCELS = re.compile(
    r"^concurrency:(?:\n[ \t]+.*)*?\n[ \t]+cancel-in-progress:\s*true", re.MULTILINE
)
ANY_CANCEL = re.compile(r"^[ \t]*cancel-in-progress:\s*true\b", re.MULTILINE)
STEPS = re.compile(r"^\s+steps:\s*$", re.MULTILINE)
HARDEN = re.compile(r"uses:\s*['\"]?step-security/harden-runner@")

MACOS_MESSAGE = (
    "runs-on names a macOS runner, which is slow and costly; keep it only for a "
    f"job that needs macOS, and run everything else on {NEWEST_LTS}"
)
MOVING_MESSAGE = (
    f"runs-on uses a moving label that changes image without a commit; pin {NEWEST_LTS}"
)
UNPINNED_MESSAGE = (
    "uses {ref}: a third-party action must be pinned to a full 40-character "
    "commit SHA with the version in a trailing comment"
)
TOOL_MESSAGE = (
    "this step runs npm, npx, yarn or pip; use pnpm or uv with the committed lockfile"
)
CONCURRENCY_MESSAGE = (
    "no top-level concurrency group with cancel-in-progress, so a new push leaves "
    "the superseded run going; a job that must finish, such as a release, "
    "belongs in its own workflow"
)
MIXED_MESSAGE = (
    "this workflow checks pushes and also releases, so cancelling superseded runs "
    "stops a release halfway; move the release to its own workflow on "
    "workflow_run, release, repository_dispatch or a tag push"
)
RELEASE_MESSAGE = (
    "a release workflow sets cancel-in-progress: true, so a newer run stops a "
    "release halfway; set cancel-in-progress: false"
)

Triggers = dict[str, tuple[str, ...]]


def is_workflow(path: str) -> bool:
    return bool(WORKFLOW_PATH.search(path))


def needs_macos(path: str, text: str) -> bool:
    return bool(TAP_PATH.search(path) or MACOS_ONLY_TOOL.search(text))


def _runner(number: int, line: str, macos_needed: bool) -> list[Finding]:
    match = RUNS_ON.match(line)
    if not match:
        return []
    value = match.group("value")
    if "-latest" in value:
        return [Finding(number, MOVING_MESSAGE)]
    if "macos" in value:
        return [] if macos_needed else [Finding(number, MACOS_MESSAGE, blocking=False)]
    lts = UBUNTU_LTS.search(value)
    newest = int(NEWEST_LTS.split("-")[1].split(".")[0])
    if lts and int(lts.group("year")) < newest:
        message = f"runs-on: {lts.group(0)} is older than {NEWEST_LTS}, the newest LTS"
        return [Finding(number, message, blocking=False)]
    return []


def _action(number: int, line: str) -> list[Finding]:
    match = USES.match(line)
    if not match:
        return []
    ref = match.group("ref")
    if ref.startswith(("./", "docker://")) or PINNED_SHA.search(ref):
        return []
    if ref.split("/", 1)[0] in FIRST_PARTY_OWNERS:
        return []
    return [Finding(number, UNPINNED_MESSAGE.format(ref=ref))]


def _tool(number: int, line: str) -> list[Finding]:
    if NAME_KEY.match(line) or USES.match(line) or line.lstrip().startswith("#"):
        return []
    return [Finding(number, TOOL_MESSAGE)] if FORBIDDEN_TOOL.search(line) else []


def _nested(line: str) -> bool:
    return not line.strip() or line[0] in " \t" or line.lstrip().startswith("#")


def _children(lines: Sequence[str]) -> Triggers:
    keys = [
        (len(match.group("indent")), match.group("name"), index)
        for index, line in enumerate(lines)
        if (match := YAML_KEY.match(line))
    ]
    if not keys:
        return {}
    depth = min(indent for indent, _name, _index in keys)
    starts = [(name, index) for indent, name, index in keys if indent == depth]
    ends = [*(index for _name, index in starts[1:]), len(lines)]
    return {
        name: tuple(lines[index + 1 : end])
        for (name, index), end in zip(starts, ends, strict=True)
    }


def _triggers(text: str) -> Triggers:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = ON_KEY.match(line)
        if not match:
            continue
        inline = match.group("inline")
        if inline:
            return {name: () for name in TRIGGER_NAME.findall(inline)}
        return _children(tuple(takewhile(_nested, lines[index + 1 :])))
    return {}


def _kinds(text: str) -> tuple[bool, bool]:
    triggers = _triggers(text)
    push = triggers.get("push")
    filters = frozenset(_children(push or ()))
    tag_push = bool(filters) and filters <= TAG_FILTERS
    checks = "pull_request" in triggers or (push is not None and not tag_push)
    releases = tag_push or not RELEASE_TRIGGERS.isdisjoint(triggers)
    return checks, releases


def _concurrency(text: str) -> list[Finding]:
    checks, releases = _kinds(text)
    if checks and releases:
        return [Finding(1, MIXED_MESSAGE)]
    if checks and not CANCELS.search(text):
        return [Finding(1, CONCURRENCY_MESSAGE)]
    if releases and ANY_CANCEL.search(text):
        return [Finding(1, RELEASE_MESSAGE)]
    return []


def _whole_file(text: str) -> list[Finding]:
    found = _concurrency(text)
    jobs, hardened = len(STEPS.findall(text)), len(HARDEN.findall(text))
    if hardened < jobs:
        message = (
            f"{jobs} jobs run steps and {hardened} starts with "
            "step-security/harden-runner"
        )
        found = [*found, Finding(1, message, blocking=False)]
    return found


def find(path: str, text: str, full_file: bool) -> tuple[Finding, ...]:
    if not is_workflow(path):
        return ()
    macos = needs_macos(path, text)
    per_line = [
        hit
        for number, line in enumerate(text.splitlines(), start=1)
        for hit in (
            *_runner(number, line, macos),
            *_action(number, line),
            *_tool(number, line),
        )
    ]
    return tuple([*(_whole_file(text) if full_file else []), *per_line])
