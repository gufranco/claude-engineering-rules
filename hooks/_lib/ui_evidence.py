from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from _lib.image_dimensions import Dimensions, ImageFailure
from _lib.publish_commands import Attachment, Channel, Publication
from _lib.ui_surface import Surface

MIN_LONGER_SIDE_PX = 1600
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


def _attachment_findings(
    publication: Publication, read: DimensionReader
) -> tuple[set[Role], list[str]]:
    roles: set[Role] = set()
    problems: list[str] = []
    for attachment in publication.attachments:
        role = attachment_role(attachment)
        if role is None:
            continue
        size = read(attachment.path)
        if isinstance(size, ImageFailure):
            problems = [*problems, f"{attachment.path}: {size.reason}"]
            continue
        if size.longer_side < MIN_LONGER_SIDE_PX:
            problems = [
                *problems,
                f"{attachment.path}: {size.width}x{size.height}, longer side "
                f"under {MIN_LONGER_SIDE_PX} px",
            ]
            continue
        roles = roles | {role}
    return roles, problems


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


def _missing_roles(roles: set[Role], changes: list[Change]) -> list[str]:
    missing: list[str] = []
    if Role.AFTER not in roles:
        missing = [*missing, "no high-resolution image labeled After:"]
    if needs_before(changes) and Role.BEFORE not in roles:
        missing = [*missing, "no high-resolution image labeled Before:"]
    return missing


def evidence_verdict(
    publication: Publication, changes: list[Change], read: DimensionReader
) -> Verdict:
    attached_roles, attached_problems = _attachment_findings(publication, read)
    attached = {attachment.path for attachment in publication.attachments}
    embedded_roles, embedded_problems = _embedded_findings(publication, attached)
    unreadable = [
        f"{path}: body file could not be read" for path in publication.unreadable
    ]
    problems = [
        *unreadable,
        *attached_problems,
        *embedded_problems,
        *_missing_roles(attached_roles | embedded_roles, changes),
    ]
    return Verdict(Action.BLOCK, tuple(problems)) if problems else ALLOWED


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
        Action.ASK, ("the text describes an interface and carries no screenshot",)
    )


def surfaces_of(changes: list[Change]) -> list[Surface]:
    return sorted({change.surface for change in changes}, key=lambda s: s.value)


def format_changes(changes: list[Change]) -> str:
    listed = "\n".join(f"  {c.status} {c.path}" for c in changes[:MAX_LISTED])
    if len(changes) > MAX_LISTED:
        listed += f"\n  ... and {len(changes) - MAX_LISTED} more"
    return listed
