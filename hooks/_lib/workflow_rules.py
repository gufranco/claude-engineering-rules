from __future__ import annotations

import re

from _lib.guard_runner import Finding

NEWEST_LTS = "ubuntu-26.04"
FIRST_PARTY_OWNERS = frozenset({"actions", "github"})

WORKFLOW_PATH = re.compile(r"(?:^|/)\.github/workflows/[^/]+\.ya?ml$")
RUNS_ON = re.compile(r"^\s*runs-on:\s*(?P<value>.+?)\s*(?:#.*)?$")
UBUNTU_LTS = re.compile(r"\bubuntu-(?P<year>\d{2})\.04\b")
USES = re.compile(r"^\s*(?:-\s+)?uses:\s*['\"]?(?P<ref>[^'\"\s#]+)")
PINNED_SHA = re.compile(r"@[0-9a-f]{40}$")
NAME_KEY = re.compile(r"^\s*(?:-\s+)?(?:name|id|if):")
FORBIDDEN_TOOL = re.compile(
    r"(?:^|[\s;&|(])(?:npm|npx|yarn)\s+\S|(?<!uv )\bpip3?\s+install\b"
)
TRIGGERED_BY_PUSH = re.compile(
    r"^\s*(?:push|pull_request)\s*:|^on:.*\b(?:push|pull_request)\b", re.MULTILINE
)
CANCELS = re.compile(
    r"^concurrency:(?:\n[ \t]+.*)*?\n[ \t]+cancel-in-progress:\s*true", re.MULTILINE
)
STEPS = re.compile(r"^\s+steps:\s*$", re.MULTILINE)
HARDEN = re.compile(r"uses:\s*['\"]?step-security/harden-runner@")

MACOS_MESSAGE = (
    f"runs-on names a macOS runner, which is slow and costly; run on {NEWEST_LTS}"
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
    "no concurrency group with cancel-in-progress, so a new push leaves the "
    "superseded run going"
)


def is_workflow(path: str) -> bool:
    return bool(WORKFLOW_PATH.search(path))


def _runner(number: int, line: str) -> list[Finding]:
    match = RUNS_ON.match(line)
    if not match:
        return []
    value = match.group("value")
    if "macos" in value:
        return [Finding(number, MACOS_MESSAGE)]
    if "-latest" in value:
        return [Finding(number, MOVING_MESSAGE)]
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


def _whole_file(text: str) -> list[Finding]:
    found: list[Finding] = []
    if TRIGGERED_BY_PUSH.search(text) and not CANCELS.search(text):
        found = [Finding(1, CONCURRENCY_MESSAGE)]
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
    per_line = [
        hit
        for number, line in enumerate(text.splitlines(), start=1)
        for check in (_runner, _action, _tool)
        for hit in check(number, line)
    ]
    return tuple([*(_whole_file(text) if full_file else []), *per_line])
