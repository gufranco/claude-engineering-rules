from __future__ import annotations

import sys
from pathlib import Path

import pytest
from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from _lib.image_dimensions import Dimensions, ImageFailure  # noqa: E402
from _lib.publish_commands import Attachment, Channel, Publication  # noqa: E402
from _lib.ui_evidence import (  # noqa: E402
    Action,
    Change,
    Role,
    attachment_role,
    embedded_images,
    evidence_verdict,
    format_changes,
    mentions_ui,
    proposal_verdict,
    surfaces_of,
)
from _lib.ui_surface import Surface  # noqa: E402

fake = Faker()
Faker.seed(9203)
SHARP = Dimensions(2880, 1800)
URL = "https://github.com/user-attachments/assets/0d1e"


def _publication(
    channel: Channel = Channel.PR_CREATE,
    attachments: tuple[Attachment, ...] = (),
    text: str = "",
    unreadable: tuple[str, ...] = (),
) -> Publication:
    return Publication(channel, attachments, text, "", "", unreadable)


def _reader(sizes: dict[str, Dimensions | ImageFailure]):
    return lambda path: sizes[path]


MODIFIED = [Change("src/Button.tsx", "M", Surface.WEB)]
ADDED = [Change("src/Settings.tsx", "A", Surface.WEB)]


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Before: login", Role.BEFORE),
        ("after grid", Role.AFTER),
        ("AFTER", Role.AFTER),
        ("afterglow", None),
        ("screenshot", None),
    ],
)
def test_attachment_role_reads_the_alt_text(label, expected):
    # Arrange
    attachment = Attachment(f"{fake.word()}.png", label)

    # Act
    result = attachment_role(attachment)

    # Assert
    assert result == expected


def test_attachment_role_falls_back_to_the_file_name():
    # Arrange
    attachment = Attachment("shots/before-login.png", "")

    # Act
    result = attachment_role(attachment)

    # Assert
    assert result is Role.BEFORE


def test_both_images_at_high_resolution_allow_a_modified_surface():
    # Arrange
    publication = _publication(
        attachments=(Attachment("b.png", "Before: x"), Attachment("a.png", "After: x"))
    )
    read = _reader({"b.png": SHARP, "a.png": SHARP})

    # Act
    result = evidence_verdict(publication, MODIFIED, read)

    # Assert
    assert (result.action, result.problems) == (Action.ALLOW, ())


def test_an_added_surface_needs_only_after():
    # Arrange
    publication = _publication(attachments=(Attachment("a.png", "After: new"),))

    # Act
    result = evidence_verdict(
        publication, ADDED, _reader({"a.png": Dimensions(1170, 2532)})
    )

    # Assert
    assert result.action is Action.ALLOW


def test_missing_images_name_both_roles():
    # Arrange
    publication = _publication(attachments=(Attachment("x.png", "logo"),))

    # Act
    result = evidence_verdict(publication, MODIFIED, _reader({}))

    # Assert
    assert result.action is Action.BLOCK
    assert result.problems == (
        "no high-resolution image labeled After:",
        "no high-resolution image labeled Before:",
    )


def test_low_resolution_and_unreadable_images_are_named():
    # Arrange
    publication = _publication(
        attachments=(Attachment("b.png", "Before: x"), Attachment("a.mov", "After: x")),
        unreadable=("body.md",),
    )
    read = _reader(
        {"b.png": Dimensions(1440, 900), "a.mov": ImageFailure("not an image")}
    )

    # Act
    result = evidence_verdict(publication, MODIFIED, read)

    # Assert
    assert result.problems == (
        "body.md: body file could not be read",
        "b.png: 1440x900, longer side under 1600 px",
        "a.mov: not an image",
        "no high-resolution image labeled After:",
        "no high-resolution image labeled Before:",
    )


def test_embedded_remote_images_count_for_a_reply():
    # Arrange
    text = f'![Before: old]({URL}) and <img alt="After: new" src="{URL}">'
    publication = _publication(Channel.THREAD_REPLY, text=text)

    # Act
    result = evidence_verdict(publication, MODIFIED, _reader({}))

    # Assert
    assert result.action is Action.ALLOW


def test_a_local_reference_must_be_attached():
    # Arrange
    publication = _publication(
        attachments=(Attachment("shot.png", "After: x"),),
        text="![After: x](shot.png) ![After: y](other.png) ![logo](z.png)",
    )

    # Act
    result = evidence_verdict(publication, ADDED, _reader({"shot.png": SHARP}))

    # Assert
    assert result.problems == ("other.png: local image referenced but not attached",)


def test_embedded_images_tolerate_tags_without_attributes():
    # Arrange
    text = "<img> ![a](<https://x.test/a b.png> 'title')"

    # Act
    result = embedded_images(text)

    # Assert
    assert result == [("a", "https://x.test/a"), ("", "")]


@pytest.mark.parametrize(
    ("channel", "text", "attachments", "expected"),
    [
        (Channel.ISSUE_CREATE, "The login button overlaps the logo", (), Action.ASK),
        (Channel.ISSUE_COMMENT, "Fixed the TUI header", (), Action.ASK),
        (Channel.ISSUE_CREATE, "Rate limiter drops jobs", (), Action.ALLOW),
        (Channel.ISSUE_CREATE, f"The modal ![Before: m]({URL})", (), Action.ALLOW),
        (Channel.ISSUE_CREATE, "The modal", (Attachment("m.png", ""),), Action.ALLOW),
        (Channel.PR_CREATE, "The modal", (), Action.ALLOW),
    ],
)
def test_proposal_verdict_asks_only_for_uncaptured_interface_text(
    channel, text, attachments, expected
):
    # Arrange
    publication = _publication(channel, attachments, text)

    # Act
    result = proposal_verdict(publication)

    # Assert
    assert result.action is expected


def test_mentions_ui_needs_the_acronym_in_capitals():
    # Arrange
    text = "a gui-less build"

    # Act
    result = mentions_ui(text)

    # Assert
    assert result is False


def _many_changes() -> list[Change]:
    web = [Change(f"f{i}.tsx", "M", Surface.WEB) for i in range(11)]
    return [*web, Change("main.qml", "A", Surface.DESKTOP)]


def test_surfaces_of_lists_each_surface_once_in_name_order():
    # Arrange
    changes = _many_changes()

    # Act
    result = surfaces_of(changes)

    # Assert
    assert result == [Surface.DESKTOP, Surface.WEB]


def test_format_changes_caps_the_listing():
    # Arrange
    changes = _many_changes()

    # Act
    result = format_changes(changes)

    # Assert
    assert result.splitlines()[-1] == "  ... and 2 more"


def test_format_changes_lists_a_short_set_in_full():
    # Arrange
    changes = [Change("main.qml", "A", Surface.DESKTOP)]

    # Act
    result = format_changes(changes)

    # Assert
    assert result == "  A main.qml"
