from __future__ import annotations

import importlib.util
import io
import os
import subprocess
import sys
from pathlib import Path

from faker import Faker

from _helpers.cov_env import apply_coverage_env

TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "investigate"
    / "scripts"
    / "hitl_loop_template.py"
)


def run_template(stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TEMPLATE)],
        input=stdin,
        capture_output=True,
        text=True,
        env=apply_coverage_env(dict(os.environ)),
        timeout=60,
        check=False,
    )


def test_every_answer_is_printed_as_name_and_value(faker: Faker) -> None:
    # Arrange
    message = faker.sentence()

    # Act
    proc = run_template(f"\ny\n{message}\n")

    # Assert
    assert (proc.returncode, proc.stdout) == (
        0,
        "\n>>> Open the app at http://localhost:3000 and sign in.\n"
        "    [Enter when done] \n"
        ">>> Click the Export button. Did it throw an error? (y/n)\n"
        "    > \n"
        ">>> Paste the error message, or none:\n"
        "    > \n"
        "--- Captured ---\n"
        "ERRORED=y\n"
        f"ERROR_MSG={message}\n",
    )


def test_a_session_without_terminal_input_explains_how_to_run_it() -> None:
    # Arrange
    stdin = ""

    # Act
    proc = run_template(stdin)

    # Assert
    assert (proc.returncode, proc.stderr) == (
        1,
        "\nNo terminal input. Run this in your own terminal window, "
        "never through the ! prefix.\n",
    )


def test_main_reports_each_answer_when_imported(monkeypatch, capsys) -> None:
    # Arrange
    spec = importlib.util.spec_from_file_location("hitl_loop_template", TEMPLATE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr("sys.stdin", io.StringIO("\nn\nnone\n"))

    # Act
    code = module.main()

    # Assert
    assert (code, capsys.readouterr().out.splitlines()[-2:]) == (
        0,
        ["ERRORED=n", "ERROR_MSG=none"],
    )
