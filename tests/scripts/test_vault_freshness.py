"""Coverage for the vault-freshness linter.

Source rule: rules/knowledge-notes.md, the freshness policy.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "vault-freshness.py"
TODAY = "2026-08-18"


def load():
    spec = importlib.util.spec_from_file_location("vault_freshness", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["vault_freshness"] = module
    spec.loader.exec_module(module)
    return module


def note(body: str) -> str:
    return (
        "---\n"
        "date: 2026-08-18\n"
        "type: concept\n"
        "tags: [concept]\n"
        "ai-first: true\n"
        "---\n\n"
        "## For future agent\n\n"
        "Why this note exists.\n\n"
        f"{body}\n"
    )


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    for sub in ("wiki/concepts", "daily", "_trash"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def audit(vault: Path, window: int = 7):
    module = load()
    return module.audit(vault, window=window, today=module.parse_date(TODAY))


def test_a_timeless_note_reports_nothing(vault):
    (vault / "wiki/concepts/A.md").write_text(note("Invoices are issued monthly."))

    assert audit(vault) == []


def test_reports_an_undated_volatile_claim(vault):
    (vault / "wiki/concepts/A.md").write_text(note("The pipeline has 13 open deals."))

    findings = audit(vault)

    assert [f.code for f in findings] == ["FRESH-1"]
    assert findings[0].severity == "error"


def test_a_fresh_stamp_reports_nothing(vault):
    (vault / "wiki/concepts/A.md").write_text(
        note("The pipeline has 13 open deals (as of 2026-08-15).")
    )

    assert audit(vault) == []


def test_reports_a_stamp_past_the_window(vault):
    (vault / "wiki/concepts/A.md").write_text(
        note("The pipeline has 13 open deals (as of 2026-07-01).")
    )

    findings = audit(vault)

    assert [f.code for f in findings] == ["FRESH-2"]
    assert findings[0].severity == "warning"


def test_the_window_is_configurable(vault):
    (vault / "wiki/concepts/A.md").write_text(
        note("The pipeline has 13 open deals (as of 2026-07-01).")
    )

    assert audit(vault, window=365) == []


def test_a_dated_note_is_exempt(vault):
    (vault / "daily/2026-07-01.md").write_text(
        note("The pipeline has 13 open deals (as of 2026-07-01).")
    )

    assert audit(vault) == []


def test_a_dated_heading_exempts_the_lines_under_it(vault):
    (vault / "wiki/concepts/A.md").write_text(
        note("## 2026-07-01\n\nThe pipeline has 13 open deals.")
    )

    assert audit(vault) == []


def test_reports_a_pointer_without_a_target(vault):
    (vault / "wiki/concepts/A.md").write_text(note("Where truth lives: the CRM board."))

    findings = audit(vault)

    assert [f.code for f in findings] == ["FRESH-3"]
    assert findings[0].severity == "error"


def test_a_pointer_with_a_url_is_valid(vault):
    (vault / "wiki/concepts/A.md").write_text(
        note("Where truth lives: https://crm.example.com/pipeline")
    )

    assert audit(vault) == []


def test_a_pointer_with_a_typed_id_is_valid(vault):
    (vault / "wiki/concepts/A.md").write_text(
        note("Where truth lives: linear:TICKET-123")
    )

    assert audit(vault) == []


def test_a_fenced_block_is_ignored(vault):
    (vault / "wiki/concepts/A.md").write_text(
        note("```\nThe pipeline has 13 open deals.\n```")
    )

    assert audit(vault) == []


def test_the_trash_folder_is_ignored(vault):
    (vault / "_trash/Old.md").write_text(note("The pipeline has 13 open deals."))

    assert audit(vault) == []


def test_a_stamp_with_month_precision_is_understood(vault):
    (vault / "wiki/concepts/A.md").write_text(
        note("Revenue is 4 records wide (as of 2026-06).")
    )

    findings = audit(vault)

    assert [f.code for f in findings] == ["FRESH-2"]


def test_main_returns_zero_without_strict(vault, capsys):
    (vault / "wiki/concepts/A.md").write_text(note("The pipeline has 13 open deals."))
    module = load()

    code = module.main(["--path", str(vault), "--today", TODAY])

    assert code == 0
    assert "FRESH-1" in capsys.readouterr().out


def test_main_returns_one_with_strict_and_errors(vault):
    (vault / "wiki/concepts/A.md").write_text(note("The pipeline has 13 open deals."))
    module = load()

    assert module.main(["--path", str(vault), "--today", TODAY, "--strict"]) == 1


def test_main_returns_zero_with_strict_and_only_warnings(vault):
    (vault / "wiki/concepts/A.md").write_text(
        note("The pipeline has 13 open deals (as of 2026-07-01).")
    )
    module = load()

    assert module.main(["--path", str(vault), "--today", TODAY, "--strict"]) == 0


def test_main_emits_json(vault, capsys):
    (vault / "wiki/concepts/A.md").write_text(note("The pipeline has 13 open deals."))
    module = load()

    module.main(["--path", str(vault), "--today", TODAY, "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"]["error"] == 1
    assert payload["findings"][0]["code"] == "FRESH-1"


def test_main_reports_a_clean_vault(vault, capsys):
    (vault / "wiki/concepts/A.md").write_text(note("Invoices are issued monthly."))
    module = load()

    assert module.main(["--path", str(vault), "--today", TODAY]) == 0
    assert "clean" in capsys.readouterr().out.lower()


def test_main_errors_when_the_vault_is_missing(tmp_path, capsys):
    module = load()

    assert module.main(["--path", str(tmp_path / "absent")]) == 2
    assert "not a directory" in capsys.readouterr().err.lower()


def test_main_defaults_today_to_the_current_date(vault):
    (vault / "wiki/concepts/A.md").write_text(note("Invoices are issued monthly."))
    module = load()

    assert module.main(["--path", str(vault)]) == 0


def test_parse_date_rejects_a_malformed_value():
    module = load()

    with pytest.raises(SystemExit):
        module.main(["--path", ".", "--today", "not-a-date"])
