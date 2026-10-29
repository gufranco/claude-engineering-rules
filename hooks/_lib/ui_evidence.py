from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from _lib.change_marker import (
    MARKER_HEX,
    MIN_MARKER_PIXELS,
    SAMPLE_WIDTH_PX,
    MarkerCount,
    MarkerFailure,
)
from _lib.image_dimensions import Dimensions, ImageFailure
from _lib.publish_commands import Attachment, Channel, Publication
from _lib.ui_surface import Surface

MIN_LONGER_SIDE_PX = 1600
UNEXPANDED = (
    "names a shell variable this check cannot expand, and a command "
    "substitution counts as one; assign a literal path earlier in the same "
    "command or pass the literal path"
)
UNREADABLE_BODY = (
    "body file could not be read; a relative path resolves against the "
    "directory a cd moved into"
)
MAX_LISTED = 10

IMAGE_MARKDOWN = re.compile(r"!\[([^\]]*)\]\(\s*<?([^)\s>]+)>?[^)]*\)")
IMAGE_HTML = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
HTML_ALT = re.compile(r"\balt\s*=\s*(['\"])(.*?)\1", re.IGNORECASE | re.DOTALL)
HTML_SRC = re.compile(r"\bsrc\s*=\s*(['\"])(.*?)\1", re.IGNORECASE | re.DOTALL)
LABEL = re.compile(r"^\s*(before|after)(?![a-z])", re.IGNORECASE)
REMOTE = re.compile(r"^https?://", re.IGNORECASE)
UI_VOCABULARY = re.compile(
    r"\b(?:screens?|screenshots?|buttons?|layouts?|modals?|dialogs?|colou?rs?"
    r"|fonts?|icons?|css|styles?|styling|themes?|dark mode|light mode|navbar"
    r"|sidebar|menus?|tooltips?|toolbar|pixels?|viewport|responsive|render(?:s|ed|ing)?"
    r"|widgets?|components?|forms?|pages?|tabs?|cards?|banners?|spacing|padding"
    r"|margins?|alignment|animations?)\b",
    re.IGNORECASE,
)
UI_ACRONYM = re.compile(r"\b(?:UI|UX|GUI|TUI)\b")
DEVICE_WORD = re.compile(
    r"\b(?:desktop|laptop|mobile|phone|tablet|ios|android)\b", re.IGNORECASE
)
VIEWPORT_WIDTH = re.compile(r"\b\d{3,4}\s?px\b", re.IGNORECASE)
LABEL_EXAMPLE = "After: Mobile 320 px, default queue"
COMMON_VIEWPORTS = (
    (1280, 720),
    (1280, 800),
    (1366, 768),
    (1440, 900),
    (1536, 864),
    (1600, 900),
    (1680, 1050),
    (1920, 1080),
    (2560, 1440),
    (768, 1024),
    (820, 1180),
    (1024, 1366),
    (320, 568),
    (360, 800),
    (375, 667),
    (375, 812),
    (390, 844),
    (393, 852),
    (412, 915),
    (414, 896),
    (430, 932),
)
DEVICE_SCALES = (1, 2, 3)
VIEWPORT_CAPTURES = {
    (width * scale, height * scale): (width, height, scale)
    for width, height in COMMON_VIEWPORTS
    for scale in DEVICE_SCALES
}
PROPOSAL_ADVICE = (
    "Attach a high-resolution image of the current state labeled Before:, and "
    "one labeled After: for the change or its mockup. Approve only when no "
    "visible interface is involved."
)
FULL_PAGE_ADVICE = (
    "Capture the whole page: with Playwright, pass fullPage and first set every "
    "scrolling ancestor to height: auto, never overflow: visible. Approve only "
    "when the page fits inside one viewport."
)


class Role(str, Enum):
    BEFORE = "before"
    AFTER = "after"


class Action(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class Change:
    path: str
    status: str
    surface: Surface


@dataclass(frozen=True, slots=True)
class Verdict:
    action: Action
    problems: tuple[str, ...]
    advice: str = ""


ALLOWED = Verdict(Action.ALLOW, ())
ISSUE_CHANNELS = frozenset(
    {
        Channel.ISSUE_CREATE,
        Channel.ISSUE_EDIT,
        Channel.ISSUE_COMMENT,
        Channel.API_ISSUE_COMMENT,
        Channel.GLAB_ISSUE_CREATE,
        Channel.GLAB_ISSUE_NOTE,
        Channel.TRACKER_ISSUE,
        Channel.TRACKER_COMMENT,
        Channel.THREAD_REPLY,
    }
)

DimensionReader = Callable[[str], "Dimensions | ImageFailure"]
MarkerReader = Callable[[str], "MarkerCount | MarkerFailure"]


def role_of(label: str) -> Role | None:
    match = LABEL.match(label)
    return Role(match.group(1).lower()) if match else None


def attachment_role(attachment: Attachment) -> Role | None:
    label = attachment.alt or os.path.splitext(os.path.basename(attachment.path))[0]
    return role_of(label)


def embedded_images(text: str) -> list[tuple[str, str]]:
    found = [(m.group(1), m.group(2)) for m in IMAGE_MARKDOWN.finditer(text)]
    for tag in IMAGE_HTML.finditer(text):
        alt = HTML_ALT.search(tag.group(0))
        src = HTML_SRC.search(tag.group(0))
        found = [*found, (alt.group(2) if alt else "", src.group(2) if src else "")]
    return found


def needs_before(changes: list[Change]) -> bool:
    return any(change.status != "A" for change in changes)


Measured = list[tuple[str, Dimensions]]


def _measure(path: str, size: Dimensions | ImageFailure) -> Dimensions | str:
    if isinstance(size, ImageFailure):
        return f"{path}: {size.reason}"
    if size.longer_side < MIN_LONGER_SIDE_PX:
        return (
            f"{path}: {size.width}x{size.height}, longer side "
            f"under {MIN_LONGER_SIDE_PX} px"
        )
    return size


def marker_problem(path: str, found: MarkerCount | MarkerFailure) -> str | None:
    if isinstance(found, MarkerFailure):
        return f"{path}: cannot check the change marker: {found.reason}"
    if found.pixels >= MIN_MARKER_PIXELS:
        return None
    return (
        f"{path}: no {MARKER_HEX} change marker visible at {SAMPLE_WIDTH_PX} px "
        f"wide, {found.pixels} of {MIN_MARKER_PIXELS} pixels"
    )


def _check_attachment(
    path: str, role: Role, read: DimensionReader, marked: MarkerReader
) -> tuple[Dimensions | None, list[str]]:
    if "$" in path:
        return None, [f"{path}: {UNEXPANDED}"]
    size = _measure(path, read(path))
    if isinstance(size, str):
        return None, [size]
    if role is not Role.AFTER:
        return size, []
    unmarked = marker_problem(path, marked(path))
    return size, [] if unmarked is None else [unmarked]


def _attachment_findings(
    publication: Publication, read: DimensionReader, marked: MarkerReader
) -> tuple[set[Role], list[str], Measured]:
    roles: set[Role] = set()
    problems: list[str] = []
    measured: Measured = []
    for attachment in publication.attachments:
        role = attachment_role(attachment)
        if role is None:
            continue
        size, found = _check_attachment(attachment.path, role, read, marked)
        problems = [*problems, *found]
        if size is None:
            continue
        measured = [*measured, (attachment.path, size)]
        roles = roles | {role}
    return roles, problems, measured


def _embedded_findings(
    publication: Publication, attached: set[str]
) -> tuple[set[Role], list[str]]:
    roles: set[Role] = set()
    problems: list[str] = []
    for alt, src in embedded_images(publication.text):
        role = role_of(alt)
        if role is None:
            continue
        if not REMOTE.match(src) and src not in attached:
            problems = [*problems, f"{src}: local image referenced but not attached"]
            continue
        roles = roles | {role}
    return roles, problems


def width_problems(measured: Measured) -> list[str]:
    widths = {size.width for _, size in measured}
    if len(widths) < 2:
        return []
    listed = ", ".join(f"{os.path.basename(p)} {s.width} px" for p, s in measured)
    target = max(widths)
    return [
        f"images in one set differ in width ({listed}); scale each in proportion "
        f"to {target} px, for example sips --resampleWidth {target} <file>, "
        "never pad onto a canvas"
    ]


def _names_device_and_viewport(label: str) -> bool:
    return bool(DEVICE_WORD.search(label) and VIEWPORT_WIDTH.search(label))


def label_problems(labels: list[str]) -> list[str]:
    if not any(DEVICE_WORD.search(label) for label in labels):
        return []
    return [
        f"{label!r}: name the device and the viewport width, as in {LABEL_EXAMPLE!r}"
        for label in labels
        if not _names_device_and_viewport(label)
    ]


def viewport_only(path: str, size: Dimensions) -> str | None:
    match = VIEWPORT_CAPTURES.get((size.width, size.height))
    if match is None:
        return None
    width, height, scale = match
    return (
        f"{path}: {size.width}x{size.height} is exactly a {width}x{height} "
        f"viewport at scale {scale}, so the page may not be captured in full"
    )


def _labels(publication: Publication) -> list[str]:
    attached = [
        attachment.alt or os.path.basename(attachment.path)
        for attachment in publication.attachments
        if attachment_role(attachment) is not None
    ]
    embedded = [
        alt for alt, _ in embedded_images(publication.text) if role_of(alt) is not None
    ]
    return [*attached, *embedded]


def _missing_roles(roles: set[Role], changes: list[Change]) -> list[str]:
    missing: list[str] = []
    if Role.AFTER not in roles:
        missing = [*missing, "no high-resolution image labeled After:"]
    if needs_before(changes) and Role.BEFORE not in roles:
        missing = [*missing, "no high-resolution image labeled Before:"]
    return missing


def evidence_verdict(
    publication: Publication,
    changes: list[Change],
    read: DimensionReader,
    marked: MarkerReader,
) -> Verdict:
    attached_roles, attached_problems, measured = _attachment_findings(
        publication, read, marked
    )
    attached = {attachment.path for attachment in publication.attachments}
    embedded_roles, embedded_problems = _embedded_findings(publication, attached)
    unreadable = [f"{path}: {UNREADABLE_BODY}" for path in publication.unreadable]
    problems = [
        *unreadable,
        *attached_problems,
        *embedded_problems,
        *_missing_roles(attached_roles | embedded_roles, changes),
        *width_problems(measured),
        *label_problems(_labels(publication)),
    ]
    if problems:
        return Verdict(Action.BLOCK, tuple(problems))
    partial = [found for path, size in measured if (found := viewport_only(path, size))]
    return Verdict(Action.ASK, tuple(partial), FULL_PAGE_ADVICE) if partial else ALLOWED


def mentions_ui(text: str) -> bool:
    return bool(UI_VOCABULARY.search(text) or UI_ACRONYM.search(text))


def proposal_verdict(publication: Publication) -> Verdict:
    if publication.channel not in ISSUE_CHANNELS:
        return ALLOWED
    if publication.attachments or embedded_images(publication.text):
        return ALLOWED
    if not mentions_ui(publication.text):
        return ALLOWED
    return Verdict(
        Action.ASK,
        ("the text describes an interface and carries no screenshot",),
        PROPOSAL_ADVICE,
    )


def surfaces_of(changes: list[Change]) -> list[Surface]:
    return sorted({change.surface for change in changes}, key=lambda s: s.value)


def format_changes(changes: list[Change]) -> str:
    listed = "\n".join(f"  {c.status} {c.path}" for c in changes[:MAX_LISTED])
    if len(changes) > MAX_LISTED:
        listed += f"\n  ... and {len(changes) - MAX_LISTED} more"
    return listed
