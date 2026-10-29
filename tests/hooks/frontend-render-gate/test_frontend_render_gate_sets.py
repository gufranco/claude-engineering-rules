from __future__ import annotations

from _ui_evidence_support import GH, decision, png, repo_with_branch, run_gate

PAGE = "src/app/redemptions/page.tsx"
SOURCE = "export default function Page() { return null }\n"
FULL_DESKTOP = (2880, 7000)
FULL_MOBILE = (2880, 35091)


def _new_page(tmp_path):
    return repo_with_branch(tmp_path, {}, {PAGE: SOURCE})


def test_images_of_different_widths_in_one_set_are_blocked(tmp_path):
    # Arrange
    repo = _new_page(tmp_path)
    png(repo / "desktop.png", FULL_DESKTOP)
    png(repo / "mobile.png", (640, 7798))
    command = (
        f"{GH} pr create -b x --attach 'desktop.png#After: Desktop 1440 px, queue' "
        "--attach 'mobile.png#After: Mobile 320 px, queue'"
    )

    # Act
    result = run_gate({"command": command}, repo)

    # Assert
    assert result.returncode == 2
    assert "differ in width (desktop.png 2880 px, mobile.png 640 px)" in result.stderr
    assert "sips --resampleWidth 2880" in result.stderr


def test_a_set_scaled_to_one_width_with_device_labels_passes(tmp_path):
    # Arrange
    repo = _new_page(tmp_path)
    png(repo / "desktop.png", FULL_DESKTOP)
    png(repo / "mobile.png", FULL_MOBILE)
    command = (
        f"{GH} pr create -b x --attach 'desktop.png#After: Desktop 1440 px, queue' "
        "--attach 'mobile.png#After: Mobile 320 px, queue'"
    )

    # Act
    result = run_gate({"command": command}, repo)

    # Assert
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_a_label_without_device_and_viewport_is_blocked_when_another_names_one(
    tmp_path,
):
    # Arrange
    repo = _new_page(tmp_path)
    png(repo / "desktop.png", FULL_DESKTOP)
    png(repo / "mobile.png", FULL_MOBILE)
    command = (
        f"{GH} pr create -b x --attach 'desktop.png#After: Desktop 1440 px, queue' "
        "--attach 'mobile.png#After: queue on a phone'"
    )

    # Act
    result = run_gate({"command": command}, repo)

    # Assert
    assert result.returncode == 2
    assert "'After: queue on a phone': name the device and the viewport width" in (
        result.stderr
    )


def test_a_capture_exactly_one_viewport_tall_asks_for_a_full_page(tmp_path):
    # Arrange
    repo = _new_page(tmp_path)
    png(repo / "after.png", (2880, 1800))

    # Act
    result = run_gate(
        {"command": f"{GH} pr create -b x --attach 'after.png#After: queue'"}, repo
    )

    # Assert
    assert (result.returncode, decision(result)) == (0, "ask")
    assert "exactly a 1440x900 viewport at scale 2" in result.stdout
    assert "fullPage" in result.stdout


def test_attachments_resolve_through_a_cd_and_a_variable_set_in_the_command(
    tmp_path,
):
    # Arrange
    repo = _new_page(tmp_path)
    shots = tmp_path / "shots"
    shots.mkdir()
    png(shots / "after.png", FULL_DESKTOP)
    (shots / "body.md").write_text("New page.", encoding="utf-8")
    command = (
        f"S={shots}; cd $S && {GH} pr edit 7 --body-file body.md "
        '--attach "$S/after.png#After: queue"'
    )

    # Act
    result = run_gate({"command": command}, repo)

    # Assert
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_a_variable_the_command_never_sets_is_named_in_the_block(tmp_path):
    # Arrange
    repo = _new_page(tmp_path)

    # Act
    result = run_gate(
        {"command": f"{GH} pr create -b x --attach '$UNSET_SHOTS/a.png#After: x'"},
        repo,
    )

    # Assert
    assert result.returncode == 2
    assert "$UNSET_SHOTS/a.png: names a shell variable this check cannot expand" in (
        result.stderr
    )
