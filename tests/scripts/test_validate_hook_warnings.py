from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from faker import Faker

from _helpers.cov_env import apply_coverage_env

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "validate-hook-warnings.py"

fake = Faker()
Faker.seed(2910)


@pytest.fixture
def module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_hook_warnings", SCRIPT)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, loaded)
    spec.loader.exec_module(loaded)
    return loaded


def _hook(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _warn_audit(name: str) -> str:
    return f'_audit(hook="{name}", decision="warn", reason="x")\n'


@pytest.mark.parametrize(
    ("relative", "text", "kind"),
    [
        (
            "hooks/a-guard.py",
            'sys.stdout.write(json.dumps({"systemMessage": report}))\n',
            "user-only channel",
        ),
        (
            "hooks/_lib/helper.py",
            "payload = {'systemMessage': text}\n",
            "user-only channel",
        ),
        ("hooks/b-guard.py", _warn_audit("b-guard"), "silent advisory"),
        (
            "hooks/c-guard.py",
            '_audit(hook="c-guard", decision="advise", reason="x")\n',
            "silent advisory",
        ),
    ],
)
def test_reports_an_advisory_the_model_cannot_see(
    module: ModuleType, tmp_path: Path, relative: str, text: str, kind: str
) -> None:
    # Arrange
    _hook(tmp_path, relative, text)

    # Act
    findings = module.findings(tmp_path)

    # Assert
    assert [(finding.path, finding.kind) for finding in findings] == [(relative, kind)]


@pytest.mark.parametrize(
    ("relative", "text"),
    [
        (
            "hooks/d-guard.py",
            "emit_warning(report)\n" + _warn_audit("d-guard"),
        ),
        (
            "hooks/e-guard.py",
            '{"additionalContext": context}\n' + _warn_audit("e-guard"),
        ),
        ("hooks/f-guard.py", '_audit(hook="f-guard", decision="block")\n'),
        (
            "hooks/_lib/hook_warning.py",
            'payload = {"systemMessage": text}\n',
        ),
        ("hooks/mutation-method-blocker.py", _warn_audit("mutation-method-blocker")),
    ],
)
def test_accepts_advisories_that_reach_the_model(
    module: ModuleType, tmp_path: Path, relative: str, text: str
) -> None:
    # Arrange
    _hook(tmp_path, relative, text)

    # Act
    findings = module.findings(tmp_path)

    # Assert
    assert findings == []


def test_check_reports_and_fails_then_passes_when_clean(
    module: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    name = f"{fake.word().lower()}-guard"
    _hook(tmp_path, f"hooks/{name}.py", _warn_audit(name))
    dirty = module.check(tmp_path)
    _hook(tmp_path, f"hooks/{name}.py", "emit_warning(x)\n" + _warn_audit(name))

    # Act
    clean = module.check(tmp_path)

    # Assert
    out = capsys.readouterr().out
    assert (dirty, clean) == (1, 0)
    assert f"hooks/{name}.py:1: silent advisory" in out
    assert "PASSED" in out


def test_main_checks_the_configured_root(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange
    _hook(tmp_path, "hooks/g-guard.py", "emit_warning(x)\n")
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    # Act
    code = module.main()

    # Assert
    assert code == 0


def test_the_script_passes_on_this_repository() -> None:
    # Arrange
    env = apply_coverage_env(dict(os.environ))

    # Act
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )

    # Assert
    assert proc.returncode == 0, proc.stdout
