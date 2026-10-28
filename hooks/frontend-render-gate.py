#!/usr/bin/env python3
import dataclasses
import json
import os
import re
import subprocess
import sys
from typing import cast

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lib.bypass import is_bypassed  # noqa: E402
from _lib.hook_input import read_hook_payload  # noqa: E402
from _lib.commit_scope import repo_dir  # noqa: E402
from _lib.git_invocation import strip_git_global_options  # noqa: E402
from _lib.image_dimensions import read_dimensions  # noqa: E402
from _lib.publish_commands import (  # noqa: E402
    PULL_REQUEST_CHANNELS,
    Channel,
    Publication,
    publications,
    tracker_publication,
)
from _lib.ui_evidence import (  # noqa: E402
    Action,
    Change,
    MIN_LONGER_SIDE_PX,
    Verdict,
    evidence_verdict,
    format_changes,
    needs_before,
    proposal_verdict,
    surfaces_of,
)
from _lib.ui_surface import (  # noqa: E402
    Surface,
    content_surface,
    may_be_tui,
    path_surface,
)

RENDER_LEVEL_CHECK = re.compile(
    r"(^|/)(e2e|acceptance|integration_test|playwright|cypress|puppeteer|maestro|patrol)(/|$)"
    r"|\.e2e\.[cm]?[jt]sx?$"
    r"|(^|/)[^/]*UITests?(/|\.swift$)"
    r"|(^|/)androidTest(/|$)"
    r"|(^|/)[^/]*(accessibility|a11y|axe|visual|screenshot)[^/]*\.[cm]?[jt]sx?$"
    r"|(^|/)[^/]*(accessibility|a11y|golden|integration)[^/]*_test\.dart$"
    r"|(^|/)(playwright|cypress|percy|chromatic|lighthouserc)\.[^/]*$"
    r"|\.flow\.ya?ml$"
    r"|(^|/)(__snapshots__|snapshots)/"
    r"|\.(snap|golden|svg\.snap)$"
    r"|(^|/)tst_[^/]+\.(cpp|py|qml)$",
    re.IGNORECASE,
)

GIT_COMMIT_INVOCATION = re.compile(r"\bgit\s+(?:-\S+\s+|--\S+(?:=\S+)?\s+)*commit\b")
DEFAULT_BASES = ("origin/HEAD", "origin/main", "origin/master", "main", "master")

MAX_LISTED = 10
MAX_CONTENT_FILES = 60
CONTENT_READ_LIMIT = 256 * 1024
GIT_TIMEOUT_SECONDS = 10
GIT_UNAVAILABLE = -1
BYPASS_ENV = "FRONTEND_RENDER_GATE_DISABLE"

WEB_GUIDANCE = (
    "  agent-browser open <url>\n"
    "  agent-browser eval \"document.querySelector('<sel>').focus();\n"
    "    const s = getComputedStyle(document.activeElement);\n"
    '    JSON.stringify({ outline: s.outlineWidth, shadow: s.boxShadow })"\n'
    "  agent-browser snapshot -i\n"
)

MOBILE_GUIDANCE = (
    "  A widget test is the jsdom tier: it proves structure, not paint and not\n"
    "  the platform accessibility tree. The device tier is an integration_test\n"
    "  suite on a simulator or emulator; xcrun simctl and adb are both present.\n"
)

DESKTOP_GUIDANCE = (
    "  Drive the window with the toolkit's own test runner, such as QTest,\n"
    "  pytest-qt, or WinAppDriver, and assert on the rendered widget tree.\n"
)

TUI_GUIDANCE = (
    "  Snapshot the rendered terminal: textual's snap_compare, bubbletea's\n"
    "  teatest golden files, or ratatui's TestBackend with insta snapshots.\n"
)

COMMIT_GUIDANCE = {
    Surface.WEB: WEB_GUIDANCE,
    Surface.MOBILE: MOBILE_GUIDANCE,
    Surface.DESKTOP: DESKTOP_GUIDANCE,
    Surface.TUI: TUI_GUIDANCE,
}

BLOCK_MESSAGE = (
    "BLOCKED: this commit changes rendered output with no render-level check.\n\n"
    "{files}\n\n"
    "Cascade outcome, paint order, the accessibility tree, focus order, and\n"
    "anything inside a third-party frame are invisible in source and absent\n"
    "from a DOM emulation. A class-name assertion restates the diff rather\n"
    "than testing what a visitor perceives.\n\n"
    "{guidance}\n"
    "Extend the browser-driven or simulator suite this project already has,\n"
    "asserting the computed result on the element in question. When the\n"
    "surface is genuinely unreachable, say so explicitly rather than\n"
    "reporting the change as verified.\n\n"
    "Rule: rules/frontend-render-gate.md\n"
    f"Bypass for a genuine false positive: export {BYPASS_ENV}=1"
)

CAPTURE_RECIPES = {
    Surface.WEB: (
        "  web:     agent-browser set viewport 1440 900 2\n"
        "           agent-browser open <url> && agent-browser screenshot after.png\n"
    ),
    Surface.MOBILE: (
        "  iOS:     xcrun simctl io booted screenshot after.png\n"
        "  Android: adb exec-out screencap -p > after.png\n"
    ),
    Surface.DESKTOP: (
        "  desktop: screencapture -o -l <window-id> after.png  (Retina, 2x)\n"
    ),
    Surface.TUI: (
        "  TUI:     asciinema rec --headless --window-size 100x30 -c '<command>' run.cast\n"
        "           agg --font-size 32 run.cast run.gif\n"
        "           magick 'run.gif[-1]' after.png\n"
    ),
}

EVIDENCE_MESSAGE = (
    "BLOCKED: {channel} publishes a visible interface change without\n"
    "high-resolution before and after screenshots.\n\n"
    "Interface changes in this branch:\n{changes}\n\n"
    "Problems:\n{problems}\n\n"
    "Capture at a device scale of 2 or more; the longer side must reach\n"
    f"{MIN_LONGER_SIDE_PX} px.\n{{recipes}}\n"
    "{before_hint}"
    "Attach with labeled alt text:\n"
    "  gh pr create --attach 'before.png#Before: <what>' "
    "--attach 'after.png#After: <what>'\n"
    "A thread reply cannot attach: upload with gh pr edit <n> --attach, read the\n"
    "URL back with gh pr view <n> --json body, and embed it as\n"
    "![After: <what>](<url>).\n\n"
    "Rule: rules/frontend-render-gate.md\n"
    f"Bypass for a genuine false positive: export {BYPASS_ENV}=1"
)

BEFORE_HINT = (
    "Capture Before from the base commit with the same data, viewport, theme,\n"
    "and locale: git worktree add ../before <base>, run it, and shoot the same\n"
    "screen.\n\n"
)

ASK_MESSAGE = (
    "{channel}: {reason}. Attach a high-resolution image of the current state\n"
    "labeled Before:, and one labeled After: for the change or its mockup.\n"
    "Approve only when no visible interface is involved.\n"
    "Rule: rules/frontend-render-gate.md"
)
UNKNOWN_DIFF = Verdict(
    Action.ASK,
    (
        "the branch diff against its base could not be read, so a visible change "
        "cannot be ruled out",
    ),
)
DIFF_CHANNELS = PULL_REQUEST_CHANNELS - {Channel.THREAD_REPLY}


def _git(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    command = ["git", "-C", repo, *args]
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError) as error:
        print(f"frontend-render-gate: git {args[0]} failed: {error}", file=sys.stderr)
        return subprocess.CompletedProcess(command, GIT_UNAVAILABLE, "", str(error))


def staged_files(repo: str) -> list[str] | None:
    result = _git(repo, "diff", "--cached", "--name-only", "--diff-filter=ACMR")
    if result.returncode == GIT_UNAVAILABLE:
        return None
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def file_text(repo: str, revision_path: str) -> str:
    result = _git(repo, "show", revision_path)
    return result.stdout[:CONTENT_READ_LIMIT] if result.returncode == 0 else ""


def any_render_level_check(paths: list[str]) -> bool:
    return any(RENDER_LEVEL_CHECK.search(path) for path in paths)


def format_file_list(paths: list[str]) -> str:
    listed = "\n".join(f"  {path}" for path in paths[:MAX_LISTED])
    if len(paths) > MAX_LISTED:
        listed += f"\n  ... and {len(paths) - MAX_LISTED} more"
    return listed


def _commit_command(payload: dict[str, object]) -> str | None:
    if payload.get("tool_name") != "Bash":
        return None
    tool_input = cast("dict[str, object]", payload["tool_input"])
    command = str(tool_input.get("command") or "")
    if not GIT_COMMIT_INVOCATION.search(strip_git_global_options(command)):
        return None
    return command


def _block_message(ui_files: list[tuple[str, Surface]]) -> str:
    surfaces = sorted({surface for _, surface in ui_files}, key=lambda s: s.value)
    guidance = "".join(COMMIT_GUIDANCE[surface] for surface in surfaces)
    paths = [path for path, _ in ui_files]
    return BLOCK_MESSAGE.format(files=format_file_list(paths), guidance=guidance)


def surfaces_by_path(
    repo: str, paths: list[tuple[str, str]]
) -> list[tuple[str, Surface]]:
    by_path = [(path, path_surface(path)) for path, _ in paths]
    candidates = [
        (path, revision)
        for (path, revision), (_, surface) in zip(paths, by_path)
        if surface is None and may_be_tui(path)
    ][:MAX_CONTENT_FILES]
    by_content = [
        (path, content_surface(path, file_text(repo, f"{revision}:{path}")))
        for path, revision in candidates
    ]
    return [(path, s) for path, s in [*by_path, *by_content] if s is not None]


def check_commit(command: str, cwd: str) -> int:
    repo = repo_dir(command, cwd)
    paths = staged_files(repo)
    if paths is None:
        print(
            "BLOCKED: frontend-render-gate could not list the staged files in time. "
            f"Retry the commit; export {BYPASS_ENV}=1 for a known outage.",
            file=sys.stderr,
        )
        return 2
    ui_files = surfaces_by_path(repo, [(path, "") for path in paths])
    if not ui_files or any_render_level_check(paths):
        return 0
    print(_block_message(ui_files), file=sys.stderr)
    return 2


def resolve_base(repo: str, requested: str) -> str | None:
    candidates = (f"origin/{requested}", requested) if requested else DEFAULT_BASES
    for candidate in candidates:
        result = _git(repo, "merge-base", candidate, "HEAD")
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return None


def branch_changes(repo: str, base: str) -> list[Change] | None:
    result = _git(repo, "diff", "--name-status", "--no-renames", f"{base}..HEAD")
    if result.returncode != 0:
        return None
    rows = [line.partition("\t") for line in result.stdout.splitlines() if line]
    statuses = {path: status[:1] for status, _, path in rows}
    revisions = [
        (path, base if status == "D" else "HEAD") for path, status in statuses.items()
    ]
    return [
        Change(path=path, status=statuses[path], surface=surface)
        for path, surface in surfaces_by_path(repo, revisions)
    ]


def _same_repo(repo: str, slug: str) -> bool:
    if not slug:
        return True
    url = _git(repo, "remote", "get-url", "origin").stdout.strip().removesuffix(".git")
    wanted = slug.removesuffix(".git").split("://")[-1].split("github.com/")[-1]
    return url == wanted or url.endswith((f"/{wanted}", f":{wanted}"))


def ui_changes(publication: Publication, repo: str) -> list[Change] | None:
    if not _same_repo(repo, publication.repo):
        return None
    base = resolve_base(repo, publication.base)
    if base is None:
        return None
    return branch_changes(repo, base)


def _absolute(path: str, repo: str) -> str:
    expanded = os.path.expanduser(path)
    return expanded if os.path.isabs(expanded) else os.path.join(repo, expanded)


def _resolve_attachments(publication: Publication, repo: str) -> Publication:
    attachments = tuple(
        dataclasses.replace(a, path=_absolute(a.path, repo))
        for a in publication.attachments
    )
    return dataclasses.replace(publication, attachments=attachments)


def judge(publication: Publication, repo: str) -> tuple[Verdict, list[Change]]:
    changes = ui_changes(publication, repo)
    if changes is None and publication.channel in DIFF_CHANNELS:
        return UNKNOWN_DIFF, []
    if not changes:
        return proposal_verdict(publication), []
    resolved = _resolve_attachments(publication, repo)
    return evidence_verdict(resolved, changes, read_dimensions), changes


def _evidence_message(
    publication: Publication, verdict: Verdict, changes: list[Change]
) -> str:
    recipes = "".join(CAPTURE_RECIPES[surface] for surface in surfaces_of(changes))
    return EVIDENCE_MESSAGE.format(
        channel=publication.channel.value,
        changes=format_changes(changes),
        problems="\n".join(f"  - {problem}" for problem in verdict.problems),
        recipes=recipes,
        before_hint=BEFORE_HINT if needs_before(changes) else "",
    )


def _ask(publication: Publication, verdict: Verdict) -> int:
    decision = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": ASK_MESSAGE.format(
                channel=publication.channel.value, reason="; ".join(verdict.problems)
            ),
        }
    }
    print(json.dumps(decision))
    return 0


def check_publications(found: list[Publication], repo: str) -> int:
    for publication in found:
        verdict, changes = judge(publication, repo)
        if verdict.action is Action.BLOCK:
            print(_evidence_message(publication, verdict, changes), file=sys.stderr)
            return 2
        if verdict.action is Action.ASK:
            return _ask(publication, verdict)
    return 0


def _publications(
    payload: dict[str, object], cwd: str
) -> tuple[list[Publication], str]:
    tool_input = cast("dict[str, object]", payload["tool_input"])
    tracked = tracker_publication(str(payload.get("tool_name", "")), tool_input)
    if tracked is not None:
        return [tracked], cwd
    if payload.get("tool_name") != "Bash":
        return [], cwd
    command = str(tool_input.get("command", ""))
    repo = repo_dir(command, cwd)
    return publications(command, repo), repo


def main() -> int:
    if os.environ.get(BYPASS_ENV) == "1":
        return 0
    if is_bypassed("frontend-render-gate"):
        return 0
    payload = read_hook_payload("frontend-render-gate")
    raw_cwd = payload.get("cwd")
    cwd = raw_cwd if isinstance(raw_cwd, str) else ""
    command = _commit_command(payload)
    if command is not None and check_commit(command, cwd) != 0:
        return 2
    found, repo = _publications(payload, cwd)
    return check_publications(found, repo)


if __name__ == "__main__":
    sys.exit(main())
