"""Coverage for the retrieval evaluation.

Source rule: rules/knowledge-notes.md. Retrieval quality is measured, not assumed.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "retrieval-eval.py"


def load():
    spec = importlib.util.spec_from_file_location("retrieval_eval", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["retrieval_eval"] = module
    spec.loader.exec_module(module)
    return module


def note(title: str, body: str) -> str:
    return (
        "---\n"
        "date: 2026-08-18\n"
        "type: concept\n"
        "tags: [concept]\n"
        "ai-first: true\n"
        "---\n\n"
        "## For future agent\n\n"
        f"Notes about {title}.\n\n"
        f"{body}\n"
    )


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "wiki/concepts").mkdir(parents=True, exist_ok=True)
    (root / "wiki/concepts/Postgres Indexing.md").write_text(
        note("Postgres Indexing", "A partial index narrows the rows a scan touches.")
    )
    (root / "wiki/concepts/Queue Backpressure.md").write_text(
        note("Queue Backpressure", "A consumer that cannot keep up must shed load.")
    )
    (root / "wiki/concepts/Idempotency Keys.md").write_text(
        note("Idempotency Keys", "A retried write must not create a second row.")
    )
    return root


@pytest.fixture
def cases(tmp_path: Path) -> Path:
    path = tmp_path / "cases.jsonl"
    path.write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                {
                    "question": "how do partial indexes help scans",
                    "expect": ["Postgres Indexing"],
                },
                {
                    "question": "what happens when a consumer cannot keep up",
                    "expect": ["Queue Backpressure"],
                },
            ]
        )
        + "\n"
    )
    return path


def test_tokenize_drops_stopwords_and_short_tokens():
    module = load()

    assert module.tokenize("What is the A of an index?") == ["index"]


def test_tokenize_splits_on_punctuation():
    module = load()

    assert module.tokenize("partial-index, scans!") == ["partial", "index", "scans"]


def test_index_weights_the_title_above_the_body(vault):
    module = load()

    index = module.build_index(vault)

    counts = index.frequencies["Postgres Indexing"]
    assert counts["postgres"] > counts["rows"]


def test_search_ranks_the_matching_note_first(vault):
    module = load()
    index = module.build_index(vault)

    ranked = module.search(index, "how do partial indexes help scans", limit=3)

    assert ranked[0] == "Postgres Indexing"


def test_search_returns_nothing_for_an_unrelated_question(vault):
    module = load()
    index = module.build_index(vault)

    assert module.search(index, "zzzz qqqq", limit=3) == []


def test_search_respects_the_limit(vault):
    module = load()
    index = module.build_index(vault)

    assert len(module.search(index, "write row index consumer", limit=1)) <= 1


def test_load_cases_reads_every_line(cases):
    module = load()

    assert len(module.load_cases(cases)) == 2


def test_load_cases_skips_blank_lines(tmp_path):
    module = load()
    path = tmp_path / "c.jsonl"
    path.write_text('{"question": "q", "expect": ["A"]}\n\n')

    assert len(module.load_cases(path)) == 1


def test_load_cases_rejects_a_malformed_line(tmp_path):
    module = load()
    path = tmp_path / "c.jsonl"
    path.write_text("not json\n")

    with pytest.raises(SystemExit):
        module.load_cases(path)


def test_evaluate_reports_perfect_recall(vault, cases):
    module = load()

    result = module.evaluate(vault, module.load_cases(cases))

    assert result["recall_at_3"] == 1.0
    assert result["recall_at_10"] == 1.0
    assert result["cases"] == 2


def test_evaluate_reports_a_miss(vault, tmp_path):
    module = load()
    path = tmp_path / "c.jsonl"
    path.write_text(
        json.dumps({"question": "zzzz qqqq", "expect": ["Postgres Indexing"]}) + "\n"
    )

    result = module.evaluate(vault, module.load_cases(path))

    assert result["recall_at_3"] == 0.0
    assert result["misses"][0]["question"] == "zzzz qqqq"


def test_evaluate_reports_partial_recall(vault, tmp_path):
    module = load()
    path = tmp_path / "c.jsonl"
    path.write_text(
        json.dumps(
            {
                "question": "partial indexes and scans",
                "expect": ["Postgres Indexing", "Absent Note"],
            }
        )
        + "\n"
    )

    result = module.evaluate(vault, module.load_cases(path))

    assert result["recall_at_3"] == 0.5


def test_compare_flags_a_regression():
    module = load()

    verdict = module.compare({"recall_at_3": 0.5}, {"recall_at_3": 0.9})

    assert verdict["regressed"] is True


def test_compare_accepts_an_improvement():
    module = load()

    verdict = module.compare({"recall_at_3": 0.95}, {"recall_at_3": 0.9})

    assert verdict["regressed"] is False


def test_compare_tolerates_a_missing_baseline():
    module = load()

    verdict = module.compare({"recall_at_3": 0.5}, None)

    assert verdict["regressed"] is False
    assert verdict["baseline"] is None


def test_main_reports_the_numbers(vault, cases, capsys):
    module = load()

    code = module.main(["--path", str(vault), "--cases", str(cases)])

    assert code == 0
    assert "recall@3" in capsys.readouterr().out


def test_main_emits_json(vault, cases, capsys):
    module = load()

    module.main(["--path", str(vault), "--cases", str(cases), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["recall_at_3"] == 1.0


def test_main_writes_a_baseline(vault, cases, tmp_path):
    module = load()
    baseline = tmp_path / "baseline.json"

    module.main(
        [
            "--path",
            str(vault),
            "--cases",
            str(cases),
            "--baseline",
            str(baseline),
            "--record",
        ]
    )

    assert json.loads(baseline.read_text())["recall_at_3"] == 1.0


def test_main_fails_on_a_regression(vault, tmp_path):
    module = load()
    path = tmp_path / "c.jsonl"
    path.write_text(
        json.dumps({"question": "zzzz qqqq", "expect": ["Postgres Indexing"]}) + "\n"
    )
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"recall_at_3": 1.0, "recall_at_10": 1.0}))

    code = module.main(
        [
            "--path",
            str(vault),
            "--cases",
            str(path),
            "--baseline",
            str(baseline),
            "--strict",
        ]
    )

    assert code == 1


def test_main_errors_without_a_vault(tmp_path, cases, capsys):
    module = load()

    code = module.main(["--path", str(tmp_path / "absent"), "--cases", str(cases)])

    assert code == 2
    assert "not a directory" in capsys.readouterr().err.lower()


def test_main_errors_without_a_case_file(vault, tmp_path, capsys):
    module = load()

    code = module.main(
        ["--path", str(vault), "--cases", str(tmp_path / "absent.jsonl")]
    )

    assert code == 2
    assert "case file" in capsys.readouterr().err.lower()


def test_main_reports_misses_in_text_mode(vault, tmp_path, capsys):
    module = load()
    path = tmp_path / "c.jsonl"
    path.write_text(
        json.dumps({"question": "zzzz qqqq", "expect": ["Postgres Indexing"]}) + "\n"
    )

    module.main(["--path", str(vault), "--cases", str(path)])

    assert "zzzz qqqq" in capsys.readouterr().out


def test_a_note_without_a_preamble_still_indexes(vault, tmp_path):
    module = load()
    (vault / "wiki/concepts/Sparse.md").write_text(
        "---\ndate: 2026-08-18\ntype: concept\ntags: [concept]\nai-first: true\n---\n\nSharding splits a keyspace.\n"
    )

    index = module.build_index(vault)

    assert index.frequencies["Sparse"]["sharding"] > 0


def test_a_case_with_no_expected_note_is_skipped(vault, tmp_path):
    module = load()
    path = tmp_path / "c.jsonl"
    path.write_text(json.dumps({"question": "anything", "expect": []}) + "\n")

    result = module.evaluate(vault, module.load_cases(path))

    assert result["cases"] == 1
    assert result["recall_at_3"] == 0.0
    assert result["misses"] == []
